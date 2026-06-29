/*
 * coco-skills/cmo-intelligence/sql/views.sql — resolver + analytics feature views
 *
 * Role:     NIMBLE_ROLE
 * Creates:  __DB__.__SCHEMA__.BRAND_MAP           (Cortex brand-normalization table)
 *           __DB__.__SCHEMA__.V_PRODUCT_BRAND     (focal/competitor classification)
 *           __DB__.__SCHEMA__.V_BRAND_CLASSIFIED  (the enriched shelf fact view)
 *           __DB__.__SCHEMA__.V_SHARE_OF_SHELF, V_CONTENT_HEALTH, V_ALERT_OOS,
 *           V_TREND_SOS_DAILY, V_TREND_KPI, V_SENTIMENT_SUMMARY,
 *           V_AI_SHARE_OF_ANSWER, V_AI_TOP_SOURCES, V_NEXT_BEST_ACTIONS
 * Prereq:   config.sql + ingest.sql (CFG_APP/CFG_QUERIES, RAW_SERP/RAW_PDP/RAW_VOC, GEO_*)
 *
 * These views are LIVE over the raw + config tables — editing a config row or
 * landing a new refresh updates them with no redefinition (as long as columns
 * are unchanged). The classification reads focal patterns, the focal brand
 * label, and the category from CFG_APP, so "update focal patterns" /
 * "update focal brand" is a one-row edit the views reflect immediately. Only
 * BRAND_MAP is materialized (it calls Cortex), so changing the category means
 * re-running this file's BRAND_MAP step (the skill's "re-resolve-category").
 *
 * TEMPLATE PLACEHOLDERS: __DB__ __SCHEMA__   (see config.sql)
 */

USE ROLE NIMBLE_ROLE;
USE SCHEMA __DB__.__SCHEMA__;

-- ---------------------------------------------------------------------------
-- BRAND_MAP — normalize the noisy PDP brand labels into clean tiers via Cortex.
-- Materialized (the Cortex calls run once here, not per query). The category comes
-- from CFG_APP, so this is category-agnostic.
--
-- Wrapped in REBUILD_BRAND_MAP() so it can be re-run server-side: REFRESH_SHELF
-- calls it as its last step (after RAW_PDP is populated), so BRAND_MAP refreshes
-- automatically on every seed/daily run — no manual second pass, and the cockpit
-- shows real brand tiers on first open instead of all "Other / Marketplace".
-- It reads RAW_PDP, so at provision time (empty RAW_PDP) the CALL below just
-- creates an empty placeholder that V_PRODUCT_BRAND can compile against.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE __DB__.__SCHEMA__.REBUILD_BRAND_MAP()
RETURNS STRING
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
BEGIN
    CREATE OR REPLACE TABLE __DB__.__SCHEMA__.BRAND_MAP AS
    WITH cat AS (
        SELECT category FROM __DB__.__SCHEMA__.CFG_APP WHERE app_key = '__SCHEMA__'
    ),
    freq AS (
        SELECT COALESCE(NULLIF(TRIM(brand), ''), 'UNKNOWN') AS raw_brand, COUNT(*) c
        FROM __DB__.__SCHEMA__.RAW_PDP GROUP BY 1
    ),
    top_brands AS (
        SELECT raw_brand FROM freq ORDER BY c DESC LIMIT 60
    ),
    classified AS (
        SELECT raw_brand,
            TRIM(SNOWFLAKE.CORTEX.COMPLETE('__CORTEX_MODEL__',
                'Task: normalize a retail brand label for the ' || (SELECT category FROM cat)
                || ' category by fixing only capitalization and obvious duplicate spellings. '
                || 'Rules: reply with ONLY the brand name, at most 3 words, no punctuation, no sentences, '
                || 'no explanation. Do NOT guess a parent company. If unsure return the input unchanged. Brand: '
                || raw_brand)) AS cortex_out
        FROM top_brands
    )
    SELECT raw_brand,
        CASE WHEN cortex_out IS NULL OR LENGTH(cortex_out) > 28
                  OR ARRAY_SIZE(SPLIT(TRIM(cortex_out), ' ')) > 3
                  OR cortex_out ILIKE '%the brand%' OR cortex_out ILIKE '%manufacturer%' OR cortex_out ILIKE '%.%'
             THEN INITCAP(raw_brand) ELSE INITCAP(cortex_out) END AS brand_tier
    FROM classified;
    RETURN 'BRAND_MAP rebuilt';
END;
$$;

-- Initial build (empty placeholder at provision; real tiers after the first seed).
CALL __DB__.__SCHEMA__.REBUILD_BRAND_MAP();

-- ---------------------------------------------------------------------------
-- V_PRODUCT_BRAND — classify each product as focal / a competitor tier / Other.
-- CONFIG-DRIVEN: focal match comes from CFG_APP.focal_patterns, the focal label
-- from CFG_APP.brand, and the category-stem exclusions from CFG_APP.category —
-- none baked into the DDL. Classification order: focal pattern → PDP brand
-- (via BRAND_MAP) → known-brand name match inside the title → Other / Marketplace.
-- Category words are excluded so the category itself is never read as a brand.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_PRODUCT_BRAND AS
WITH cfg AS (   -- single read of the one-row config; fp + stems derive from it
    SELECT brand, category, focal_patterns
    FROM __DB__.__SCHEMA__.CFG_APP WHERE app_key = '__SCHEMA__'
),
fp AS (   -- focal-brand match patterns, upper-cased
    SELECT UPPER(value::STRING) AS pat FROM cfg, LATERAL FLATTEN(INPUT => focal_patterns)
),
stems0 AS (  -- significant category words (>=4 chars)
    SELECT DISTINCT UPPER(w.value::STRING) AS stem
    FROM cfg, LATERAL SPLIT_TO_TABLE(REGEXP_REPLACE(UPPER(category), '[^A-Z0-9]+', ' '), ' ') w
    WHERE LENGTH(w.value::STRING) >= 4
),
stems AS (   -- + singular form so "cookies"/"cookie" both excluded
    SELECT stem FROM stems0
    UNION
    SELECT LEFT(stem, LENGTH(stem) - 1) FROM stems0 WHERE stem LIKE '%S'
),
st AS (
    SELECT retailer, product_id, MAX(product_name) product_name
    FROM __DB__.__SCHEMA__.RAW_SERP GROUP BY 1, 2
),
pt AS (
    SELECT retailer, product_id, MAX(brand) brand, MAX(product_title) title
    FROM __DB__.__SCHEMA__.RAW_PDP GROUP BY 1, 2
),
base AS (
    SELECT st.retailer, st.product_id, st.product_name,
        COALESCE(NULLIF(TRIM(pt.brand), ''), 'UNKNOWN') AS raw_brand,
        UPPER(COALESCE(st.product_name, '') || ' ' || COALESCE(pt.brand, '') || ' ' || COALESCE(pt.title, '')) AS match_text
    FROM st LEFT JOIN pt ON pt.retailer = st.retailer AND pt.product_id = st.product_id
),
flagged AS (   -- compute is_focal ONCE; both brand_tier and the output column reuse it
    SELECT base.*,
        EXISTS (SELECT 1 FROM fp WHERE base.match_text LIKE '%' || fp.pat || '%') AS is_focal
    FROM base
),
known AS (   -- clean brand names we can match inside a title (Target omits PDP brand)
    SELECT DISTINCT brand_tier AS b
    FROM __DB__.__SCHEMA__.BRAND_MAP
    WHERE brand_tier IS NOT NULL AND LENGTH(brand_tier) >= 3
      AND UPPER(brand_tier) NOT IN ('UNKNOWN', 'GENERIC', 'OTHER', 'OTHER / MARKETPLACE')
      AND NOT EXISTS (SELECT 1 FROM stems WHERE UPPER(brand_tier) ILIKE '%' || stems.stem || '%')
),
nm AS (
    SELECT f.retailer, f.product_id, k.b AS name_brand,
        ROW_NUMBER() OVER (PARTITION BY f.retailer, f.product_id ORDER BY LENGTH(k.b) DESC) rn
    FROM flagged f JOIN known k ON f.match_text LIKE '%' || UPPER(k.b) || '%'
),
nmf AS (SELECT retailer, product_id, name_brand FROM nm WHERE rn = 1)
SELECT f.retailer, f.product_id, f.product_name,
    CASE WHEN f.is_focal
         THEN (SELECT brand FROM cfg)
         ELSE COALESCE(
             CASE WHEN bm.brand_tier IS NOT NULL AND UPPER(bm.brand_tier) NOT IN ('UNKNOWN', 'GENERIC')
                       AND NOT EXISTS (SELECT 1 FROM stems WHERE UPPER(bm.brand_tier) ILIKE '%' || stems.stem || '%')
                  THEN bm.brand_tier END,
             nmf.name_brand, 'Other / Marketplace')
    END AS brand_tier,
    f.is_focal
FROM flagged f
LEFT JOIN __DB__.__SCHEMA__.BRAND_MAP bm ON bm.raw_brand = f.raw_brand
LEFT JOIN nmf ON nmf.retailer = f.retailer AND nmf.product_id = f.product_id;

-- ---------------------------------------------------------------------------
-- V_BRAND_CLASSIFIED — the enriched shelf fact view (SERP + PDP + brand tier).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_BRAND_CLASSIFIED AS
WITH sd AS (
    SELECT retailer, product_id, snapshot_date, MIN(position) position, MIN(product_price) product_price,
        MAX(COALESCE(product_out_of_stock::INT, 0))::BOOLEAN product_out_of_stock,
        MAX(COALESCE(sponsored::INT, 0))::BOOLEAN sponsored,
        ANY_VALUE(product_name) product_name, MAX(product_image) serp_image, MAX(product_url) serp_url
    FROM __DB__.__SCHEMA__.RAW_SERP GROUP BY 1, 2, 3
),
pd AS (
    SELECT retailer, product_id, ANY_VALUE(price) pdp_price, ANY_VALUE(unit_price_amount) unit_price_amount,
        ANY_VALUE(number_of_reviews) number_of_reviews, ANY_VALUE(average_of_reviews) average_of_reviews,
        ANY_VALUE(product_image) pdp_image, ANY_VALUE(product_url) pdp_url, ANY_VALUE(image_urls) image_urls,
        ANY_VALUE(product_description) product_description, ANY_VALUE(product_title) product_title
    FROM __DB__.__SCHEMA__.RAW_PDP GROUP BY 1, 2
)
SELECT sd.retailer, sd.snapshot_date, sd.product_id, sd.product_name, sd.position, sd.sponsored, sd.product_out_of_stock,
    COALESCE(pd.pdp_price, sd.product_price) best_price, pd.unit_price_amount, pb.brand_tier, pb.is_focal,
    COALESCE(pd.pdp_image, sd.serp_image) product_image, COALESCE(pd.pdp_url, sd.serp_url) product_url,
    pd.number_of_reviews, pd.average_of_reviews, pd.product_description, pd.image_urls, pd.product_title
FROM sd
LEFT JOIN pd ON pd.retailer = sd.retailer AND pd.product_id = sd.product_id
LEFT JOIN __DB__.__SCHEMA__.V_PRODUCT_BRAND pb ON pb.retailer = sd.retailer AND pb.product_id = sd.product_id;

-- ---------------------------------------------------------------------------
-- V_SHARE_OF_SHELF — brand-tier share, sponsored share, avg price per retailer/day.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_SHARE_OF_SHELF AS
WITH t AS (
    SELECT retailer, snapshot_date, COUNT(*) total FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED GROUP BY 1, 2
)
SELECT bc.retailer, bc.snapshot_date, bc.brand_tier, COUNT(*) products_in_serp,
    ROUND(COUNT(*) / NULLIF(t.total, 0) * 100, 1) share_of_shelf_pct,
    ROUND(SUM(IFF(bc.sponsored, 1, 0)) / NULLIF(COUNT(*), 0) * 100, 1) sponsored_share_pct,
    ROUND(AVG(bc.best_price), 2) avg_price, ROUND(AVG(bc.unit_price_amount), 1) avg_unit_price
FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED bc
JOIN t ON t.retailer = bc.retailer AND t.snapshot_date = bc.snapshot_date
GROUP BY bc.retailer, bc.snapshot_date, bc.brand_tier, t.total;

-- ---------------------------------------------------------------------------
-- V_CONTENT_HEALTH — 0-100 listing-content score + A-F grade + the top gap.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_CONTENT_HEALTH AS
WITH scored AS (
    SELECT retailer, snapshot_date, product_id, product_name, brand_tier, is_focal, position,
        product_image, product_url, average_of_reviews, number_of_reviews, product_description, image_urls,
        COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(image_urls)), 0) image_count,
        CASE WHEN average_of_reviews >= 4.5 THEN 25 WHEN average_of_reviews >= 4.0 THEN 20 WHEN average_of_reviews >= 3.5 THEN 12 WHEN average_of_reviews >= 3.0 THEN 6 WHEN average_of_reviews IS NOT NULL THEN 2 ELSE 0 END rating_score,
        CASE WHEN number_of_reviews >= 5000 THEN 25 WHEN number_of_reviews >= 1000 THEN 20 WHEN number_of_reviews >= 500 THEN 15 WHEN number_of_reviews >= 100 THEN 10 WHEN number_of_reviews >= 10 THEN 5 WHEN number_of_reviews >= 1 THEN 2 ELSE 0 END review_volume_score,
        CASE WHEN LENGTH(product_description) >= 600 THEN 20 WHEN LENGTH(product_description) >= 350 THEN 15 WHEN LENGTH(product_description) >= 150 THEN 10 WHEN LENGTH(product_description) >= 50 THEN 5 WHEN LENGTH(product_description) >= 1 THEN 2 ELSE 0 END description_score,
        CASE WHEN COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(image_urls)), 0) >= 8 THEN 15 WHEN COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(image_urls)), 0) >= 5 THEN 12 WHEN COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(image_urls)), 0) >= 3 THEN 8 WHEN COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(image_urls)), 0) >= 1 THEN 4 ELSE 0 END image_score,
        CASE WHEN LENGTH(COALESCE(product_title, product_name)) >= 80 THEN 15 WHEN LENGTH(COALESCE(product_title, product_name)) >= 50 THEN 11 WHEN LENGTH(COALESCE(product_title, product_name)) >= 30 THEN 7 WHEN LENGTH(COALESCE(product_title, product_name)) >= 10 THEN 3 ELSE 0 END title_score
    FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED
),
totalled AS (
    SELECT scored.*, rating_score + review_volume_score + description_score + image_score + title_score content_score FROM scored
)
SELECT retailer, snapshot_date, product_id, product_name, brand_tier, is_focal, position, product_image, product_url,
    average_of_reviews, number_of_reviews, image_count, content_score,
    CASE WHEN content_score >= 85 THEN 'A' WHEN content_score >= 70 THEN 'B' WHEN content_score >= 55 THEN 'C' WHEN content_score >= 40 THEN 'D' ELSE 'F' END content_grade,
    CASE WHEN description_score < 10 THEN 'Expand product description (thin content)'
         WHEN image_score < 8 THEN 'Add more product images'
         WHEN review_volume_score < 10 THEN 'Build review volume'
         WHEN title_score < 7 THEN 'Optimize product title'
         WHEN rating_score < 12 THEN 'Improve product rating'
         ELSE 'Maintain content quality' END top_content_gap
FROM totalled;

-- ---------------------------------------------------------------------------
-- V_ALERT_OOS — focal SKUs out of stock, with severity + a revenue-risk index.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_ALERT_OOS AS
SELECT snapshot_date, retailer, product_id, product_name, brand_tier, position, sponsored, best_price, product_image, product_url,
    CASE WHEN position <= 5 THEN 'CRITICAL' WHEN position <= 24 THEN 'HIGH' WHEN position <= 48 THEN 'MODERATE' ELSE 'LOW' END severity,
    CASE WHEN position <= 5 THEN 'Immediate replenishment - top search slot at risk'
         WHEN position <= 24 THEN 'Expedite replenishment - page 1 visibility lost while out of stock'
         ELSE 'Schedule replenishment in next standard cycle' END recommended_action,
    ROUND(best_price / NULLIF(position, 0), 4) revenue_risk_index
FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED WHERE is_focal AND product_out_of_stock;

-- ---------------------------------------------------------------------------
-- V_TREND_SOS_DAILY / V_TREND_KPI — share-of-shelf over time + day-over-day deltas.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_TREND_SOS_DAILY AS
SELECT snapshot_date, brand_tier, COUNT(*) products,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY snapshot_date), 1) share_of_shelf_pct
FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED GROUP BY 1, 2;

CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_TREND_KPI AS
WITH d AS (
    SELECT snapshot_date,
        ROUND(SUM(IFF(is_focal, 1, 0)) * 100.0 / NULLIF(COUNT(*), 0), 1) share_pct,
        ROUND(AVG(IFF(is_focal, unit_price_amount, NULL)), 2) avg_unit_price,
        ROUND(AVG(IFF(is_focal, IFF(sponsored, 100.0, 0), NULL)), 1) sponsored_pct,
        SUM(IFF(is_focal AND product_out_of_stock, 1, 0)) oos
    FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED GROUP BY 1
)
SELECT snapshot_date, share_pct, avg_unit_price, sponsored_pct, oos,
    share_pct - LAG(share_pct) OVER (ORDER BY snapshot_date) d_share,
    avg_unit_price - LAG(avg_unit_price) OVER (ORDER BY snapshot_date) d_avg_unit_price,
    sponsored_pct - LAG(sponsored_pct) OVER (ORDER BY snapshot_date) d_sponsored,
    oos - LAG(oos) OVER (ORDER BY snapshot_date) d_oos
FROM d ORDER BY snapshot_date;

-- ---------------------------------------------------------------------------
-- V_SENTIMENT_SUMMARY — focal voice-of-customer themes by sentiment (from RAW_VOC).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_SENTIMENT_SUMMARY AS
WITH k AS (
    SELECT v.sentiment, v.theme, SUM(v.mention_count) mentions
    FROM __DB__.__SCHEMA__.RAW_VOC v
    JOIN (SELECT DISTINCT retailer, product_id, is_focal FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED) bc
      ON bc.retailer = v.retailer AND bc.product_id = v.product_id
    WHERE bc.is_focal AND v.theme IS NOT NULL AND v.theme <> '' AND v.sentiment IN ('positive', 'negative', 'neutral')
    GROUP BY 1, 2
)
SELECT sentiment, theme, mentions,
    ROUND(mentions * 100.0 / NULLIF(SUM(mentions) OVER (PARTITION BY sentiment), 0), 1) pct_within_sentiment,
    ROUND(mentions * 100.0 / NULLIF(SUM(mentions) OVER (), 0), 1) pct_of_all
FROM k;

-- ---------------------------------------------------------------------------
-- V_AI_SHARE_OF_ANSWER — brand citation share per answer engine, over GEO_ANSWERS.
-- CONFIG-DRIVEN brand set: the focal brand (CFG_APP.brand) + the competitor tiers
-- the data surfaces. Degrades to 0 rows until the GEO backfill populates answers.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_AI_SHARE_OF_ANSWER AS
WITH base AS (
    SELECT engine, LOWER(answer) a FROM __DB__.__SCHEMA__.GEO_ANSWERS WHERE answer IS NOT NULL
),
brands AS (   -- focal brand + the top ~6 competitor tiers by shelf presence (bounded)
    SELECT brand AS b FROM __DB__.__SCHEMA__.CFG_APP WHERE app_key = '__SCHEMA__' AND brand IS NOT NULL
    UNION
    SELECT b FROM (
        SELECT brand_tier AS b, SUM(products_in_serp) AS tot
        FROM __DB__.__SCHEMA__.V_SHARE_OF_SHELF
        WHERE brand_tier IS NOT NULL
          AND LOWER(brand_tier) NOT IN ('other / marketplace', 'private label', 'other named brand', 'unknown', 'generic', 'other')
        GROUP BY brand_tier
        ORDER BY tot DESC
        LIMIT 6
    )
)
SELECT base.engine, brands.b AS brand, COUNT(*) answers,
    SUM(IFF(base.a LIKE '%' || LOWER(brands.b) || '%', 1, 0)) mentions,
    ROUND(SUM(IFF(base.a LIKE '%' || LOWER(brands.b) || '%', 1, 0)) * 100.0 / NULLIF(COUNT(*), 0), 1) share_of_answer_pct
FROM base CROSS JOIN brands
GROUP BY base.engine, brands.b;

CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_AI_TOP_SOURCES AS
SELECT domain, SUM(citations) citations,
    ROUND(SUM(citations) * 100.0 / NULLIF(SUM(SUM(citations)) OVER (), 0), 1) share_pct
FROM __DB__.__SCHEMA__.GEO_SOURCES GROUP BY domain ORDER BY citations DESC;

-- ---------------------------------------------------------------------------
-- V_NEXT_BEST_ACTIONS — 6 prioritized, data-driven NBAs. The focal brand name is
-- read from CFG_APP (not baked), so the prose follows whatever app this is.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW __DB__.__SCHEMA__.V_NEXT_BEST_ACTIONS AS
WITH b AS (SELECT COALESCE(brand, 'the category') AS brand FROM __DB__.__SCHEMA__.CFG_APP WHERE app_key = '__SCHEMA__')  -- null-safe for category-overview mode (brand NULL)
SELECT 1 priority, 'CRITICAL' severity, 'Availability' area,
    b.brand || ' is out of stock in top search slots' headline,
    (SELECT COUNT(*) FROM __DB__.__SCHEMA__.V_ALERT_OOS WHERE position <= 10)::VARCHAR || ' SKUs out of stock at position 10 or better' metric,
    'Escalate replenishment with the retailer now - these are the most-shopped slots and every day out of stock is lost sell-through' recommended_action
FROM b
UNION ALL SELECT 2, 'HIGH', 'Pricing', b.brand || ' carries a price premium per unit',
    (SELECT retailer || ': ' || b.brand || ' ' || ROUND(AVG(IFF(is_focal, unit_price_amount, NULL))) || ' vs category ' || ROUND(AVG(IFF(NOT is_focal, unit_price_amount, NULL)))
     FROM __DB__.__SCHEMA__.V_BRAND_CLASSIFIED WHERE unit_price_amount IS NOT NULL GROUP BY retailer
     ORDER BY AVG(IFF(is_focal, unit_price_amount, NULL)) - AVG(IFF(NOT is_focal, unit_price_amount, NULL)) DESC NULLS LAST LIMIT 1),
    'Test a price or promo on hero SKUs where the per-unit gap is widest'
FROM b
UNION ALL SELECT 3, 'HIGH', 'Retail media', 'Competitors out-invest ' || b.brand || ' in sponsored placement',
    (SELECT b.brand || ' sponsored share ' || ROUND(AVG(IFF(brand_tier = b.brand, sponsored_share_pct, NULL)), 1) || '% vs set ' || ROUND(AVG(IFF(brand_tier <> b.brand, sponsored_share_pct, NULL)), 1) || '%'
     FROM __DB__.__SCHEMA__.V_SHARE_OF_SHELF),
    'Pilot retail-media on the top SKUs - paid visibility is where shoppers convert'
FROM b
UNION ALL SELECT 4, 'HIGH', 'AI visibility', b.brand || ' is under-cited in AI shopping answers',
    (SELECT b.brand || ' ' || COALESCE(ROUND(AVG(IFF(brand = b.brand, share_of_answer_pct, NULL)), 0)::VARCHAR, 'low') || '% share of AI answer'
     FROM __DB__.__SCHEMA__.V_AI_SHARE_OF_ANSWER),
    'Launch a GEO content play on the category prompts where competitors are cited and ' || b.brand || ' is not'
FROM b
UNION ALL SELECT 5, 'MEDIUM', 'Content', 'Weak listing content on SKUs you already rank for',
    (SELECT COUNT(*)::VARCHAR || ' listings graded D or F (thin titles, few images, sparse copy)' FROM __DB__.__SCHEMA__.V_CONTENT_HEALTH WHERE is_focal AND content_grade IN ('D', 'F')),
    'Fix titles, images and descriptions on the weakest listings to defend conversion'
FROM b
UNION ALL SELECT 6, 'MEDIUM', 'Voice of customer',
    COALESCE((SELECT '"' || theme || '" is the top customer complaint' FROM __DB__.__SCHEMA__.V_SENTIMENT_SUMMARY WHERE sentiment = 'negative' ORDER BY mentions DESC LIMIT 1), 'Monitor emerging review complaints'),
    COALESCE((SELECT theme || ' drives ' || mentions::VARCHAR || ' negative review mentions' FROM __DB__.__SCHEMA__.V_SENTIMENT_SUMMARY WHERE sentiment = 'negative' ORDER BY mentions DESC LIMIT 1), 'No dominant complaint yet'),
    'Address the top flagged theme - a fixable issue eroding ratings and repeat purchase'
FROM b
ORDER BY priority;
