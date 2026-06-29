# Intake — the category architect

The skill asks for as little as possible and derives the rest with Cortex; the user confirms before
anything is built.

## The three tiers

**Tier 1 — the user provides (judgment):**
- **Category** *(required)* — the shopper-facing category, e.g. `chocolate`, `coffee`, `razors`. This
  alone is enough to start.
- **Brand** *(optional)* — the focal brand. Provide one for brand-vs-competitor framing; omit it to
  run a **category-overview** app (see below), or let the architect propose the market leader.

**Tier 2 — the architect proposes (via Cortex), the user confirms/edits:**
- **Focal brand** (if not given) — the category's market leader.
- **Keywords** (~6) — SERP search terms that surface the whole category shelf, not just the focal brand.
- **Focal patterns** — brand-SKU match substrings incl. spacing variants (e.g. `ACME BAR`, `ACMEBAR`).
- **Schema name** — e.g. `ACME_CMO` (UPPER, underscores).

**Tier 3 — defaults, editable only if asked:**
- Retailers Walmart / Amazon / Target · geo US zip `75243` · daily refresh.

## The category-architect Cortex prompt

Ask Cortex for a single JSON object, then parse and present it for confirmation:

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE('__CORTEX_MODEL__',  -- resolved at Phase 0 to the latest available Sonnet
  'You are a retail category strategist. For the category below, return ONLY a JSON object with keys: '
  || 'focal_brand (the market-leading brand, or the one provided), '
  || 'keywords (array of ~6 shopper search terms covering the category shelf), '
  || 'focal_patterns (array of UPPER-CASE brand-SKU substrings incl. spacing variants), '
  || 'schema_name (UPPER snake_case, suffixed _CMO). No prose, no markdown. '
  || 'Category: ' || ? || '. Brand (optional): ' || ?);
```

Bind the category and the (possibly empty) brand. Validate the JSON; if the model returns anything but
a clean object, re-ask or fall back to sensible defaults. **Always show the proposal and get explicit
confirmation or edits** before Phase 2.

## Building the config rows from the confirmed intake

Run `config.sql`'s `CREATE TABLE` statements first, then write these (do **not** run the file's Acme
example seed):

**CFG_APP** — one row. `retailer_map` carries each retailer's `zip_key` (used for both the SERP and
PDP calls), `pdp_agent`, and `id_key`; confirm the agent names + param keys against the
[agent gallery](https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery):

```sql
INSERT INTO __DB__.__SCHEMA__.CFG_APP
  (app_key, brand, category, focal_patterns, geo_zip, pdp_cap, refresh_cron, retailer_map)
SELECT '__SCHEMA__', '__BRAND__', '__CATEGORY__',
  <focal_patterns ARRAY>, '75243', 50, '__REFRESH_CRON__',
  OBJECT_CONSTRUCT(
    'amazon',  OBJECT_CONSTRUCT('pdp_agent','amazon_pdp', 'id_key','asin',       'zip_key','zip_code'),
    'walmart', OBJECT_CONSTRUCT('pdp_agent','walmart_pdp','id_key','product_id', 'zip_key','zipcode'),
    'target',  OBJECT_CONSTRUCT('pdp_agent','target_pdp', 'id_key','product_id', 'zip_key',NULL));
```

**CFG_QUERIES** — one row per keyword × retailer (just `keyword`, `retailer`, `agent`). Geography is
**not** stored here — `REFRESH_SHELF` applies `CFG_APP.geo_zip` under each retailer's `zip_key` at
call time, so the zip lives in one place:

```sql
INSERT INTO __DB__.__SCHEMA__.CFG_QUERIES (keyword, retailer, agent)
SELECT kw.value::STRING, r.retailer, r.agent
FROM (SELECT * FROM TABLE(FLATTEN(INPUT => <keywords ARRAY>))) kw
CROSS JOIN (
  SELECT 'amazon' retailer, 'amazon_serp' agent UNION ALL
  SELECT 'walmart','walmart_serp' UNION ALL
  SELECT 'target','target_serp') r;
```

## No-brand (category-overview) mode

If the user omits a brand and doesn't want one proposed:
- Leave `CFG_APP.brand` NULL. `is_focal` is then always FALSE and `FOCAL_SHARE` is unused — the app
  runs as a category overview keyed on the keywords. The cockpit detects the null brand and leads
  with the market-leading tier (it keys its "focal" surfaces on that tier instead of `is_focal`).
- Skip `agent.sql` (the agent is brand-centric) or name it `<CATEGORY>_SHELF_ANALYST` and reword its
  instructions to a category overview.

## Retailer field-availability (expected NULLs — not bugs)

PDP `parsing` shapes differ per retailer, so some columns are legitimately empty for some retailers.
`ingest.sql` already `COALESCE`s the known variants; the table records what to expect so operators
don't chase non-bugs. Confirm on first run (`SELECT raw FROM RAW_PDP …`) and extend the COALESCE lists
in `REFRESH_PDP` if a retailer uses a different key.

| Field (`RAW_PDP`) | Amazon | Walmart | Target | Notes |
|---|---|---|---|---|
| `price` | via `web_price` | `price`/`web_price` | confirm | Amazon returns `web_price`, not `price` |
| `unit_price_amount` | via `price_per_unit` (a `"$x/oz"` string) | usually present | confirm | parsed with a leading-number regex (`fu()`), unit varies |
| `recommend_pct` | — (NULL) | from `recommend_count`/`not_recommended_count` | confirm | recommend counts are Walmart-style; Amazon/Target → NULL |
| negative review mentions | sparse | present | confirm | Amazon PDP often returns positive mentions only, so the VOC "what to fix" is thin for Amazon |
| SERP product id | `asin` | `product_id` | `tcin` | `COALESCE(asin, product_id, tcin)` in the SERP projection |
