/*
 * coco-skills/cmo-intelligence/sql/ingest.sql — UDTF-based shelf ingestion + daily Task
 *
 * Role:        NIMBLE_ROLE (must own/run the Task; see privileges note)
 * Creates:     __DB__.__SCHEMA__.RAW_SERP, RAW_PDP        — typed raw tables
 *              __DB__.__SCHEMA__.GEO_ANSWERS, GEO_SOURCES — answer-engine (Share of AI Answer) tables
 *              __DB__.__SCHEMA__.REFRESH_SHELF()          — one-call SERP+PDP refresh
 *              __DB__.__SCHEMA__.REFRESH_GEO(prompt_limit)— answer-engine batch (Perplexity/ChatGPT/Gemini)
 *              __DB__.__SCHEMA__.DAILY_SHELF_TASK         — scheduled daily shelf refresh
 *              __DB__.__SCHEMA__.GEO_SEED_TASK / WEEKLY_GEO_TASK — first-setup seed + weekly GEO refresh
 * Prereq:      config.sql (CFG_APP + CFG_QUERIES) and the NIMBLE_AGENT_RUN UDTF from the
 *              Nimble × Snowflake integration (https://github.com/Nimbleway/cookbook/tree/main/snowflake).
 *
 * Two ingestion mechanisms, matched to call volume — right tool per job:
 *   - SERP: the NIMBLE_AGENT_RUN UDTF via a LATERAL join over CFG_QUERIES — ideal
 *     for the handful of SERP queries, with per-row error isolation (a 429 yields
 *     status='http_429' and WHERE a.status='success' skips it).
 *   - PDP: a concurrent stored proc (REFRESH_PDP) — the standard pattern for
 *     high-volume fan-out (hundreds of calls): a ThreadPoolExecutor fires them
 *     concurrently, then one batched insert.
 *
 * It is config-driven: the SERP pass lateral-joins CFG_QUERIES, so adding a
 * keyword = INSERT a row (config.sql) and the next refresh ingests it. The PDP
 * pass is derived from the product ids SERP discovers — capped per retailer by
 * CFG_APP.pdp_cap — and resolves its agent/params from CFG_APP.retailer_map, so
 * geography (CFG_APP.geo_zip) is config, not a literal.
 *
 * TEMPLATE PLACEHOLDERS (substituted by the CoCo skill / provisioning step):
 *   __DB__ __SCHEMA__ __WAREHOUSE__   — see config.sql
 *   __REFRESH_CRON__                  — task schedule; rendered from CFG_APP.refresh_cron
 *                                       (default 'USING CRON 0 6 * * * America/Chicago')
 *
 * ┌─ CONFIRM ON FIRST RUN ─────────────────────────────────────────────────┐
 * │ The exact keys inside each agent's `parsing` differ per WSA and can     │
 * │ evolve. amazon_serp is verified by recipes/amazon_keyword_research      │
 * │ (asin / product_name / price / currency / rating / review_count /       │
 * │ image_url / sponsored). walmart_serp / target_serp / *_pdp keys below   │
 * │ are the documented shapes + COALESCE fallbacks; probe before trusting:  │
 * │   SELECT raw FROM TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(       │
 * │            'walmart_serp', OBJECT_CONSTRUCT('keyword','acme')));       │
 * │ then adjust the projections / COALESCE candidates to match.             │
 * └────────────────────────────────────────────────────────────────────────┘
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE __WAREHOUSE__;
USE SCHEMA __DB__.__SCHEMA__;

-- ---------------------------------------------------------------------------
-- Raw tables. Typed core + a `raw` VARIANT catch-all per row (so the views can
-- reach a field we didn't project without re-ingesting). RAW_VOC is parsed from
-- the PDP `raw` records during refresh; GEO_* are filled by REFRESH_GEO (below).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.RAW_SERP (
    retailer              STRING,
    product_id            STRING,
    product_name          STRING,
    position              INTEGER,
    sponsored             BOOLEAN,
    product_price         NUMBER(10, 2),
    currency              STRING,
    product_rating        NUMBER(5, 2),
    product_reviews_count INTEGER,
    product_out_of_stock  BOOLEAN,
    product_image         STRING,
    product_url           STRING,
    page                  INTEGER,
    snapshot_date         DATE,
    keyword               STRING,
    zipcode               STRING,
    raw                   VARIANT
);

CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.RAW_PDP (
    retailer             STRING,
    product_id           STRING,
    product_title        STRING,
    brand                STRING,
    price                NUMBER(10, 2),
    list_price           NUMBER(10, 2),
    unit_price_amount    NUMBER(10, 2),
    currency             STRING,
    size                 STRING,
    average_of_reviews   NUMBER(5, 2),
    number_of_reviews    INTEGER,
    availability         BOOLEAN,
    product_out_of_stock BOOLEAN,
    seller_name          STRING,                 -- captured for a later marketplace/seller layer
    product_image        STRING,
    product_url          STRING,
    image_urls           STRING,                 -- JSON array of image URLs; content-health reads ARRAY_SIZE(TRY_PARSE_JSON(image_urls))
    product_description  STRING,
    snapshot_date        DATE,
    raw                  VARIANT
);

-- Voice-of-customer, parsed FREE from the PDP records (no extra agent calls):
-- one row per review theme × sentiment, plus a rating-only fallback row.
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.RAW_VOC (
    retailer      STRING,
    product_id    STRING,
    theme         STRING,
    sentiment     STRING,        -- positive | negative | neutral | rating_only
    mention_count INTEGER,
    ai_summary    STRING,
    star_pct_5    INTEGER,       -- % of reviews at 5 stars
    recommend_pct NUMBER(5, 1),  -- % who would recommend
    snapshot_date DATE
);

-- Answer-engine citations (Share of AI Answer). Created empty; REFRESH_GEO
-- (below) backfills them via the answer-engine agents, after which V_AI_* light
-- up. Until then the cockpit shows a "being generated" placeholder (see has_ai /
-- ai_pending in cockpit_template.py), not a bare 0%.
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.GEO_ANSWERS (
    engine        STRING,
    prompt        STRING,
    prompt_type   STRING,        -- template family: recommendation | comparison | sentiment | value | …
    answer        STRING,
    num_sources   INTEGER,
    snapshot_date DATE
);
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.GEO_SOURCES (
    engine        STRING,
    domain        STRING,
    citations     INTEGER,
    snapshot_date DATE
);

-- ---------------------------------------------------------------------------
-- REFRESH_PDP() — concurrent PDP enrichment (the standard pattern for bulk
-- fan-out). PDP is hundreds of HTTP calls, so a ThreadPoolExecutor fires them
-- concurrently (I/O-bound → threads), then writes RAW_PDP in one batched insert.
-- SERP stays on the UDTF lateral join, which suits its handful of calls. Reads
-- CFG_APP.retailer_map + geo_zip + pdp_cap and the product ids today's SERP found.
--
-- Confirm the PDP `parsing` field names per agent on first run (they vary).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE __DB__.__SCHEMA__.REFRESH_PDP()
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('requests', 'snowflake-snowpark-python')
HANDLER = 'run'
EXTERNAL_ACCESS_INTEGRATIONS = (NIMBLE_API_ACCESS)
SECRETS = ('cred' = NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
EXECUTE AS CALLER
AS
$$
import _snowflake, requests, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from snowflake.snowpark.types import (StructType, StructField, StringType, FloatType,
                                       IntegerType, BooleanType, VariantType)
from snowflake.snowpark.functions import current_date

URL = "https://sdk.nimbleway.com/v1/agents/run"
S = "__DB__.__SCHEMA__"

def ff(v):
    try: return float(str(v).replace("$", "").replace(",", "")) if v not in (None, "") else None
    except Exception: return None
def fu(v):
    # unit price varies by retailer: numeric, "$0.42", or "$0.42/Fl Oz" — extract the leading number
    if v in (None, ""): return None
    m = re.search(r"[0-9]+\.?[0-9]*", str(v).replace(",", ""))
    return float(m.group()) if m else None
def ii(v):
    try: return int(float(v)) if v not in (None, "") else None
    except Exception: return None
def bb(v):
    return None if v in (None, "") else str(v).lower() in ("true", "1", "yes")
def sv(v, n=16000):
    if v is None: return None
    if isinstance(v, (list, dict)): return json.dumps(v)[:n]
    return str(v)[:n]
def g(d, *ks):
    for k in ks:
        x = d.get(k)
        if x not in (None, "", [], {}): return x
    return None

def call_pdp(token, agent, params):
    try:
        r = requests.post(URL, json={"agent": agent, "params": params},
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                   "X-Client-Source": "snowflake-cortex-agent"}, timeout=120)
        if r.status_code >= 400:
            return None
        ad = (r.json() or {}).get("data") or {}
        p = ad.get("parsing")
        if isinstance(p, list):
            p = p[0] if p else None
        return p if isinstance(p, dict) else None
    except Exception:
        return None

def run(session):
    token = _snowflake.get_generic_secret_string("cred")
    cfg = session.sql("SELECT retailer_map, geo_zip, pdp_cap FROM " + S + ".CFG_APP WHERE app_key = '__SCHEMA__'").collect()
    if not cfg:
        return {"pdp_rows": 0, "note": "no CFG_APP row"}
    rmap = cfg[0][0]
    if isinstance(rmap, str):
        rmap = json.loads(rmap)
    geo, cap = cfg[0][1], int(cfg[0][2] or 50)

    # Focal-FIRST within the per-retailer cap: in a dense category the focal brand
    # ranks below pdp_cap, so a pure-position order never enriches it (no reviews /
    # description / images -> empty content health). Order focal products ahead of
    # competitors, then by position, so the focal brand always gets PDP coverage.
    pids = session.sql(
        "SELECT retailer, product_id FROM ("
        "  SELECT s.retailer, s.product_id,"
        "    ROW_NUMBER() OVER (PARTITION BY s.retailer"
        "      ORDER BY MAX(IFF(pb.is_focal, 1, 0)) DESC, MIN(s.position)) rn"   # focal first, then by position
        "  FROM " + S + ".RAW_SERP s"
        "  LEFT JOIN " + S + ".V_PRODUCT_BRAND pb ON pb.retailer = s.retailer AND pb.product_id = s.product_id"
        "  WHERE s.snapshot_date = CURRENT_DATE() AND s.product_id IS NOT NULL"
        "  GROUP BY s.retailer, s.product_id) WHERE rn <= " + str(cap)).collect()

    tasks = []
    for row in pids:
        ret, pid = row[0], row[1]
        m = rmap.get(ret) if isinstance(rmap, dict) else None
        if not m or not m.get("pdp_agent") or not m.get("id_key"):
            continue                                   # unmapped retailer → skip explicitly
        params = {m["id_key"]: pid}
        if m.get("zip_key"):
            params[m["zip_key"]] = geo
        tasks.append((ret, pid, m["pdp_agent"], params))

    out, failed = [], {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = {ex.submit(call_pdp, token, a, p): (ret, pid) for (ret, pid, a, p) in tasks}
        for fut in as_completed(futs):
            ret, pid = futs[fut]
            d = fut.result()
            if not d:
                failed[ret] = failed.get(ret, 0) + 1   # surfaced in the return value, not swallowed
                continue
            out.append((
                ret, sv(pid), sv(d.get("product_title")), sv(d.get("brand")),
                ff(d.get("price") or d.get("web_price")), ff(d.get("list_price")),
                fu(g(d, "unit_price_amount", "price_per_unit", "unit_price")),  # Amazon uses price_per_unit (a "$x/oz" string)
                sv(d.get("currency")), sv(d.get("size")),
                ff(d.get("average_of_reviews") or d.get("rating")), ii(d.get("number_of_reviews") or d.get("review_count")),
                bb(d.get("availability")), bb(d.get("product_out_of_stock")), sv(d.get("seller_name")),
                sv(g(d, "product_image", "main_image", "image", "image_url")), sv(g(d, "product_url", "url", "link")),
                sv(g(d, "image_urls", "images", "product_images")),
                sv(g(d, "product_description", "description", "about_this_item", "feature_bullets")),
                d,
            ))

    session.sql("DELETE FROM " + S + ".RAW_PDP WHERE snapshot_date = CURRENT_DATE()").collect()
    if out:
        cols = [("RETAILER", StringType()), ("PRODUCT_ID", StringType()), ("PRODUCT_TITLE", StringType()),
                ("BRAND", StringType()), ("PRICE", FloatType()), ("LIST_PRICE", FloatType()),
                ("UNIT_PRICE_AMOUNT", FloatType()), ("CURRENCY", StringType()), ("SIZE", StringType()),
                ("AVERAGE_OF_REVIEWS", FloatType()), ("NUMBER_OF_REVIEWS", IntegerType()),
                ("AVAILABILITY", BooleanType()), ("PRODUCT_OUT_OF_STOCK", BooleanType()), ("SELLER_NAME", StringType()),
                ("PRODUCT_IMAGE", StringType()), ("PRODUCT_URL", StringType()), ("IMAGE_URLS", StringType()),
                ("PRODUCT_DESCRIPTION", StringType()), ("RAW", VariantType())]
        df = session.create_dataframe(out, schema=StructType([StructField(c, t) for c, t in cols]))
        df = df.with_column("SNAPSHOT_DATE", current_date())
        df.write.mode("append").save_as_table(S + ".RAW_PDP", column_order="name")
    return {"pdp_rows": len(out), "attempted": len(tasks), "failed": sum(failed.values()), "failed_by_retailer": failed}
$$;

-- ---------------------------------------------------------------------------
-- REFRESH_GEO() — Share of AI Answer. Asks the answer engines (Perplexity,
-- ChatGPT, Gemini) a deterministic set of category prompts via Nimble's LLM
-- agents (same /v1/agents/run endpoint the SERP/PDP calls use), then writes:
--   GEO_ANSWERS — one row per (engine, prompt): the synthesized answer text
--                 (V_AI_SHARE_OF_ANSWER matches brand names against it)
--   GEO_SOURCES — citations per (engine, domain), parsed from each answer's sources
-- Concurrent (ThreadPoolExecutor) like REFRESH_PDP — it's ~prompts×3 slow LLM
-- calls, so it runs on its OWN (weekly) cadence, not the daily shelf refresh.
--
-- Answer/source field names vary per engine (perplexity: answer+sources;
-- chatgpt/gemini: text/response + links) — the getters below are tolerant.
-- Confirm shapes on first run per engine.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE __DB__.__SCHEMA__.REFRESH_GEO(prompt_limit INTEGER DEFAULT 0)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('requests', 'snowflake-snowpark-python')
HANDLER = 'run'
EXTERNAL_ACCESS_INTEGRATIONS = (NIMBLE_API_ACCESS)
SECRETS = ('cred' = NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
EXECUTE AS CALLER
AS
$$
import _snowflake, requests, json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from snowflake.snowpark.types import StructType, StructField, StringType, IntegerType
from snowflake.snowpark.functions import current_date

URL = "https://sdk.nimbleway.com/v1/agents/run"
S = "__DB__.__SCHEMA__"
ENGINES = ["perplexity", "chatgpt", "gemini"]
GENERIC = {"other / marketplace", "private label", "other named brand", "unknown", "generic", "n/a", "other"}

def g(d, *ks):
    for k in ks:
        x = d.get(k)
        if x not in (None, "", [], {}): return x
    return None

def domain_of(url):
    try:
        net = (urlparse(url).netloc or "").lower()
        return net[4:] if net.startswith("www.") else (net or None)
    except Exception:
        return None

def call_engine(token, engine, prompt):
    try:
        r = requests.post(URL, json={"agent": engine, "params": {"prompt": prompt}},
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                   "X-Client-Source": "snowflake-cortex-agent"}, timeout=180)
        if r.status_code >= 400:
            return None
        ad = (r.json() or {}).get("data") or {}
        p = ad.get("parsing")
        if isinstance(p, list):
            p = p[0] if p else None
        return p if isinstance(p, dict) else None
    except Exception:
        return None

def build_prompts(session, limit=0):
    """Deterministic templated prompts (no LLM) so the set is stable week-over-week."""
    app = session.sql("SELECT COALESCE(brand, ''), category FROM " + S + ".CFG_APP WHERE app_key = '__SCHEMA__'").collect()
    focal = (app[0][0] if app else "") or ""
    category = ((app[0][1] if app else "") or "products")
    tiers = session.sql(
        "SELECT brand_tier FROM " + S + ".V_SHARE_OF_SHELF "
        "WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM " + S + ".RAW_PDP) "
        "GROUP BY 1 ORDER BY SUM(products_in_serp) DESC").collect()
    order = [r[0] for r in tiers if r[0] and r[0].lower() not in GENERIC]
    if not focal:
        focal = order[0] if order else category
    comps = [b for b in order if b != focal][:6]
    brands = [focal] + comps
    retailers = [r[0] for r in session.sql("SELECT DISTINCT retailer FROM " + S + ".CFG_QUERIES").collect() if r[0]]
    occasions = ["a gift", "the holidays", "everyday use"]
    # High-signal families first (recommendation, comparison, focal opinion/sentiment) so a small
    # seed (prompt_limit) still captures the prompts that most drive share of AI answer; the full
    # set (limit=0) adds the long tail across every brand.
    high = [("What is the best " + category + "?", "recommendation")]
    high += [("What are the best " + category + " to buy on " + r.capitalize() + "?", "recommendation") for r in retailers]
    high += [("Compare " + focal + " and " + c + " — which is better?", "comparison") for c in comps]
    high += [("Is " + focal + " a good " + category + "?", "brand_opinion"),
             ("What are people saying about " + focal + "?", "sentiment")]
    rest = []
    for b in brands:
        rest += [("What's a good alternative to " + b + "?", "alternative"),
                 ("Is " + b + " worth the price?", "value"),
                 ("Should I buy " + b + "?", "purchase"),
                 ("Where can I buy " + b + "?", "availability")]
        if b != focal:
            rest += [("Is " + b + " a good " + category + "?", "brand_opinion"),
                     ("What are people saying about " + b + "?", "sentiment")]
    for o in occasions:
        rest += [("What " + category + " should I buy for " + o + "?", "occasion"),
                 ("Is " + focal + " a good choice for " + o + "?", "occasion_brand")]
    P = high + rest
    return P[:limit] if limit and limit > 0 else P

def run(session, prompt_limit):
    token = _snowflake.get_generic_secret_string("cred")
    # prompt_limit: 0 = full set (weekly) · <0 = seed mode (use CFG_APP.geo_seed_prompts) · >0 = top-N
    lim = int(prompt_limit or 0)
    if lim < 0:
        cap = session.sql("SELECT geo_seed_prompts FROM " + S + ".CFG_APP WHERE app_key = '__SCHEMA__'").collect()
        lim = int(cap[0][0]) if (cap and cap[0][0]) else 15
    prompts = build_prompts(session, lim)
    tasks = [(eng, text, ptype) for (text, ptype) in prompts for eng in ENGINES]

    ans_rows, src = [], {}   # src[(engine, domain)] = citation count
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = {ex.submit(call_engine, token, eng, text): (eng, text, ptype) for (eng, text, ptype) in tasks}
        for fut in as_completed(futs):
            eng, text, ptype = futs[fut]
            d = fut.result()
            if not d:
                continue
            answer = g(d, "answer", "text", "response", "markdown") or ""
            sources = g(d, "sources", "links", "citations") or []
            if not isinstance(sources, list):
                sources = []
            ans_rows.append((eng, text, ptype, str(answer)[:16000], len(sources)))
            for s in sources:
                if isinstance(s, dict):
                    u = s.get("url") or s.get("link")
                elif isinstance(s, str):
                    u = s
                else:
                    u = None
                dom = domain_of(u) if u else None
                if dom:
                    src[(eng, dom)] = src.get((eng, dom), 0) + 1

    session.sql("DELETE FROM " + S + ".GEO_ANSWERS  WHERE snapshot_date = CURRENT_DATE()").collect()
    session.sql("DELETE FROM " + S + ".GEO_SOURCES WHERE snapshot_date = CURRENT_DATE()").collect()
    if ans_rows:
        acols = [("ENGINE", StringType()), ("PROMPT", StringType()), ("PROMPT_TYPE", StringType()),
                 ("ANSWER", StringType()), ("NUM_SOURCES", IntegerType())]
        (session.create_dataframe(ans_rows, schema=StructType([StructField(c, t) for c, t in acols]))
                .with_column("SNAPSHOT_DATE", current_date())
                .write.mode("append").save_as_table(S + ".GEO_ANSWERS", column_order="name"))
    src_rows = [(eng, dom, cnt) for (eng, dom), cnt in src.items()]
    if src_rows:
        scols = [("ENGINE", StringType()), ("DOMAIN", StringType()), ("CITATIONS", IntegerType())]
        (session.create_dataframe(src_rows, schema=StructType([StructField(c, t) for c, t in scols]))
                .with_column("SNAPSHOT_DATE", current_date())
                .write.mode("append").save_as_table(S + ".GEO_SOURCES", column_order="name"))
    return {"prompts": len(prompts), "engines": len(ENGINES), "attempted": len(tasks),
            "answers": len(ans_rows), "source_rows": len(src_rows)}
$$;

-- ---------------------------------------------------------------------------
-- REFRESH_SHELF() — one call: ingest SERP (config-driven UDTF lateral join),
-- run the concurrent PDP pass (REFRESH_PDP), then parse VOC. Idempotent within a
-- day: each pass DELETEs today's rows first, so a same-day re-run REPLACEs rather
-- than double-counts. EXECUTE AS CALLER so the invoking role's grants authorize
-- the live calls. NOTE: this runs the full pipeline; the daily Task calls it
-- server-side. To seed on demand, prefer EXECUTE TASK over a blocking CALL.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE __DB__.__SCHEMA__.REFRESH_SHELF()
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    serp_n INTEGER;
    pdp_n  INTEGER;
    voc_n  INTEGER;
BEGIN
    -- ===== SERP: one statement over CFG_QUERIES =====
    DELETE FROM __DB__.__SCHEMA__.RAW_SERP WHERE snapshot_date = CURRENT_DATE();

    INSERT INTO __DB__.__SCHEMA__.RAW_SERP
        (retailer, product_id, product_name, position, sponsored, product_price,
         currency, product_rating, product_reviews_count, product_out_of_stock,
         product_image, product_url, page, snapshot_date, keyword, zipcode, raw)
    SELECT
        q.retailer,
        COALESCE(p.value:asin::STRING, p.value:product_id::STRING, p.value:tcin::STRING)        AS product_id,
        p.value:product_name::STRING                                                            AS product_name,
        p.value:position::INTEGER                                                               AS position,
        COALESCE(p.value:sponsored::BOOLEAN, p.value:is_sponsored::BOOLEAN)                      AS sponsored,
        TRY_TO_DECIMAL(REGEXP_REPLACE(COALESCE(p.value:price, p.value:product_price)::STRING, '[^0-9.]', ''), 10, 2) AS product_price,
        p.value:currency::STRING                                                                AS currency,
        TRY_TO_DECIMAL(COALESCE(p.value:rating, p.value:product_rating)::STRING, 5, 2)           AS product_rating,
        TRY_TO_NUMBER(COALESCE(p.value:review_count, p.value:product_reviews_count)::STRING)      AS product_reviews_count,
        COALESCE(p.value:product_out_of_stock::BOOLEAN, p.value:out_of_stock::BOOLEAN)            AS product_out_of_stock,
        COALESCE(p.value:image_url::STRING, p.value:product_image::STRING)                        AS product_image,
        COALESCE(p.value:url::STRING, p.value:product_url::STRING)                                AS product_url,
        p.value:page::INTEGER                                                                   AS page,
        CURRENT_DATE()                                                                          AS snapshot_date,
        q.keyword                                                                               AS keyword,
        app.geo_zip                                                                             AS zipcode,
        p.value                                                                                 AS raw
    FROM   __DB__.__SCHEMA__.CFG_QUERIES q
    JOIN   __DB__.__SCHEMA__.CFG_APP app ON app.app_key = '__SCHEMA__',
           TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
               q.agent,
               -- build params at call time: keyword + geo_zip under the retailer's zip_key (if any)
               CASE WHEN app.retailer_map[q.retailer]:zip_key IS NULL
                    THEN OBJECT_CONSTRUCT('keyword', q.keyword)
                    ELSE OBJECT_CONSTRUCT('keyword', q.keyword, app.retailer_map[q.retailer]:zip_key::STRING, app.geo_zip)
               END
           )) a,
           LATERAL FLATTEN(INPUT => a.parsing) p
    WHERE  q.active
      AND  a.status = 'success';

    -- ===== PDP: concurrent fan-out via REFRESH_PDP (the standard pattern for bulk calls) =====
    CALL __DB__.__SCHEMA__.REFRESH_PDP();

    -- ===== VOC: parsed free from the PDP `raw` records =====
    -- Review-mention arrays look like ["great taste (42)", "too sweet (8)", …];
    -- we split each into (theme, mention_count) per sentiment, plus a rating-only
    -- fallback row carrying the summary / 5-star % / recommend %.
    -- CONFIRM the PDP review field names on first run (review_mentions_with_*_sentiment,
    -- reviews_statistics_percentage_five_to_zero, recommend_count, …) — they vary per agent.
    DELETE FROM __DB__.__SCHEMA__.RAW_VOC WHERE snapshot_date = CURRENT_DATE();

    INSERT INTO __DB__.__SCHEMA__.RAW_VOC
        (retailer, product_id, theme, sentiment, mention_count, ai_summary, star_pct_5, recommend_pct, snapshot_date)
    -- Structured to stay within Snowflake's correlated-subquery rules: pull each
    -- sentiment's array into its own column, FLATTEN each column directly, UNION ALL
    -- the three, and anti-join via LEFT JOIN … IS NULL (rather than a LATERAL-in-UNION
    -- or a correlated NOT EXISTS).
    WITH p AS (
        SELECT retailer, product_id,
            COALESCE(raw:reviews_ai_summary::STRING, raw:review_summary::STRING)              AS ai_summary,
            TRY_TO_NUMBER(REGEXP_REPLACE(COALESCE(
                raw:reviews_statistics_percentage_five_to_zero:"5_star"::STRING,
                raw:reviews_statistics_percentage_five_to_zero:"5"::STRING,
                raw:reviews_statistics_percentage_five_to_zero:five_star::STRING), '[^0-9]', '')) AS star_pct_5,
            IFF(TRY_TO_DOUBLE(raw:recommend_count::STRING) IS NOT NULL
                 AND (TRY_TO_DOUBLE(raw:recommend_count::STRING) + COALESCE(TRY_TO_DOUBLE(raw:not_recommended_count::STRING), 0)) > 0,
                ROUND(TRY_TO_DOUBLE(raw:recommend_count::STRING) * 100.0
                      / (TRY_TO_DOUBLE(raw:recommend_count::STRING) + COALESCE(TRY_TO_DOUBLE(raw:not_recommended_count::STRING), 0)), 1),
                NULL)                                                                          AS recommend_pct,
            CASE WHEN IS_ARRAY(raw:review_mentions_with_positive_sentiment) THEN raw:review_mentions_with_positive_sentiment
                 ELSE TRY_PARSE_JSON(COALESCE(raw:review_mentions_with_positive_sentiment, raw:positive_review_mentions)::STRING) END AS pos_arr,
            CASE WHEN IS_ARRAY(raw:review_mentions_with_negative_sentiment) THEN raw:review_mentions_with_negative_sentiment
                 ELSE TRY_PARSE_JSON(COALESCE(raw:review_mentions_with_negative_sentiment, raw:negative_review_mentions)::STRING) END AS neg_arr,
            CASE WHEN IS_ARRAY(raw:review_mentions_with_neutral_sentiment) THEN raw:review_mentions_with_neutral_sentiment
                 ELSE TRY_PARSE_JSON(COALESCE(raw:review_mentions_with_neutral_sentiment, raw:neutral_review_mentions)::STRING) END AS neu_arr
        FROM __DB__.__SCHEMA__.RAW_PDP
        WHERE snapshot_date = CURRENT_DATE()
    ),
    m_pos AS (SELECT p.retailer, p.product_id, 'positive' AS sentiment, p.ai_summary, p.star_pct_5, p.recommend_pct,
                     TRIM(REGEXP_REPLACE(f.value::STRING, '\\s*\\(\\d+\\)\\s*$', '')) AS theme,
                     TRY_TO_NUMBER(REGEXP_SUBSTR(f.value::STRING, '\\((\\d+)\\)\\s*$', 1, 1, 'e', 1)) AS mention_count
              FROM p, LATERAL FLATTEN(INPUT => p.pos_arr) f),
    m_neg AS (SELECT p.retailer, p.product_id, 'negative', p.ai_summary, p.star_pct_5, p.recommend_pct,
                     TRIM(REGEXP_REPLACE(f.value::STRING, '\\s*\\(\\d+\\)\\s*$', '')),
                     TRY_TO_NUMBER(REGEXP_SUBSTR(f.value::STRING, '\\((\\d+)\\)\\s*$', 1, 1, 'e', 1))
              FROM p, LATERAL FLATTEN(INPUT => p.neg_arr) f),
    m_neu AS (SELECT p.retailer, p.product_id, 'neutral', p.ai_summary, p.star_pct_5, p.recommend_pct,
                     TRIM(REGEXP_REPLACE(f.value::STRING, '\\s*\\(\\d+\\)\\s*$', '')),
                     TRY_TO_NUMBER(REGEXP_SUBSTR(f.value::STRING, '\\((\\d+)\\)\\s*$', 1, 1, 'e', 1))
              FROM p, LATERAL FLATTEN(INPUT => p.neu_arr) f),
    mentions AS (SELECT * FROM m_pos UNION ALL SELECT * FROM m_neg UNION ALL SELECT * FROM m_neu),
    rated AS (SELECT DISTINCT retailer, product_id FROM mentions WHERE theme IS NOT NULL AND theme <> '')
    SELECT retailer, product_id, LEFT(theme, 120), sentiment, COALESCE(mention_count, 0),
           ai_summary, star_pct_5, recommend_pct, CURRENT_DATE()
    FROM   mentions
    WHERE  theme IS NOT NULL AND theme <> ''
    UNION ALL
    SELECT p.retailer, p.product_id, NULL, 'rating_only', 0, p.ai_summary, p.star_pct_5, p.recommend_pct, CURRENT_DATE()
    FROM   p
    LEFT JOIN rated r ON r.retailer = p.retailer AND r.product_id = p.product_id
    WHERE  r.product_id IS NULL
      AND  (p.star_pct_5 IS NOT NULL OR p.recommend_pct IS NOT NULL OR p.ai_summary IS NOT NULL);

    -- ===== Resolver: rebuild BRAND_MAP over the fresh PDP brands (no manual second pass) =====
    CALL __DB__.__SCHEMA__.REBUILD_BRAND_MAP();

    SELECT COUNT(*) INTO :serp_n FROM __DB__.__SCHEMA__.RAW_SERP WHERE snapshot_date = CURRENT_DATE();
    SELECT COUNT(*) INTO :pdp_n  FROM __DB__.__SCHEMA__.RAW_PDP  WHERE snapshot_date = CURRENT_DATE();
    SELECT COUNT(*) INTO :voc_n  FROM __DB__.__SCHEMA__.RAW_VOC  WHERE snapshot_date = CURRENT_DATE();
    RETURN OBJECT_CONSTRUCT('serp_rows', :serp_n, 'pdp_rows', :pdp_n, 'voc_rows', :voc_n, 'snapshot_date', CURRENT_DATE()::STRING);
END;
$$;

-- ---------------------------------------------------------------------------
-- Daily refresh Task. Schedule is rendered from CFG_APP.refresh_cron. Tasks are
-- created SUSPENDED — the RESUME below starts the cadence. "refresh-now" = run it
-- server-side with EXECUTE TASK (async, non-blocking) rather than a blocking CALL;
-- editing CFG_QUERIES/CFG_APP changes what the next run does.
-- Privileges: the task owner role needs EXECUTE TASK + USAGE on NIMBLE_AGENT_RUN
-- (NIMBLE_ROLE has both after setup.sql).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK
    WAREHOUSE = __WAREHOUSE__
    SCHEDULE  = '__REFRESH_CRON__'
    COMMENT   = 'Daily Nimble digital-shelf refresh for __SCHEMA__'
AS
    CALL __DB__.__SCHEMA__.REFRESH_SHELF();

ALTER TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK RESUME;

-- ---------------------------------------------------------------------------
-- Share of AI Answer (GEO) tasks — two-tier, like the PDP two-cap:
--   GEO_SEED_TASK   — one-shot, manual (no schedule); EXECUTE'd once at first setup.
--                     Runs REFRESH_GEO(-1) = a small config-sized seed
--                     (CFG_APP.geo_seed_prompts) so the cockpit populates fast (~3 min).
--   WEEKLY_GEO_TASK — full set (REFRESH_GEO()), weekly. Answer-engine data moves slowly
--                     and the full run is ~12 min / ~180 LLM calls, so it's NOT on the
--                     daily shelf cadence.
-- Either task existing is the cockpit's "being generated" pending signal.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TASK __DB__.__SCHEMA__.GEO_SEED_TASK
    WAREHOUSE = __WAREHOUSE__
    COMMENT   = 'One-shot Share-of-AI-Answer seed for __SCHEMA__ (run via EXECUTE TASK; no schedule)'
AS
    CALL __DB__.__SCHEMA__.REFRESH_GEO(-1);

CREATE OR REPLACE TASK __DB__.__SCHEMA__.WEEKLY_GEO_TASK
    WAREHOUSE = __WAREHOUSE__
    SCHEDULE  = 'USING CRON 0 8 * * 1 America/Chicago'   -- weekly (Mon 08:00); GEO data moves slowly
    COMMENT   = 'Weekly full Share-of-AI-Answer refresh for __SCHEMA__'
AS
    CALL __DB__.__SCHEMA__.REFRESH_GEO();

ALTER TASK __DB__.__SCHEMA__.WEEKLY_GEO_TASK RESUME;   -- GEO_SEED_TASK has no schedule; it only runs when EXECUTE'd

-- Seed the first snapshot immediately — server-side + non-blocking (don't CALL it
-- from the session; the SERP + concurrent PDP run blocks the client):
--   EXECUTE TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK;
-- Verify:
--   SELECT retailer, COUNT(*) FROM __DB__.__SCHEMA__.RAW_SERP WHERE snapshot_date = CURRENT_DATE() GROUP BY 1;
--   SELECT retailer, COUNT(*) FROM __DB__.__SCHEMA__.RAW_PDP  WHERE snapshot_date = CURRENT_DATE() GROUP BY 1;
