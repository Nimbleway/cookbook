/*
 * Table-driven amazon_serp: maintain a keywords table and a flattened
 * per-product results table. Each keyword is loaded with its own
 * INSERT statement so that any one query plans for a single literal
 * keyword (one http_request per statement).
 *
 * Prereqs: ../01_setup.sql, ../02_amazon_serp.sql.
 */

-- 1. Keywords table (idempotent: keyword set survives re-runs).
CREATE TABLE IF NOT EXISTS nimble_integration.examples.amazon_serp_keywords (
    keyword STRING NOT NULL
        COMMENT 'Amazon search keyword, e.g. "cookies", "wireless headphones", "coffee maker"'
)
COMMENT 'Keywords fed into nimble_integration.tools.amazon_serp for SERP monitoring.';

INSERT INTO nimble_integration.examples.amazon_serp_keywords
SELECT new_kw.keyword
FROM (VALUES ('cookies'), ('wireless headphones'), ('coffee maker')) AS new_kw(keyword)
WHERE new_kw.keyword NOT IN (SELECT keyword FROM nimble_integration.examples.amazon_serp_keywords);


-- 2. Empty results table with the full flattened schema.
DROP TABLE IF EXISTS nimble_integration.examples.amazon_serp_results;
CREATE TABLE nimble_integration.examples.amazon_serp_results (
    keyword         STRING,
    product_name    STRING,
    asin            STRING,
    price           DOUBLE,
    currency        STRING,
    rating          DOUBLE,
    product_url     STRING,
    image_url       STRING,
    prime_eligible  BOOLEAN,
    amazons_choice  BOOLEAN,
    sponsored       BOOLEAN,
    store_location  STRING,
    position        INT,
    agent_zip_code  STRING
)
COMMENT 'Flattened amazon_serp results, one row per (keyword, product).';


-- 3. One INSERT per keyword. Run these one at a time; add new ones as
-- you add keywords to amazon_serp_keywords.
INSERT INTO nimble_integration.examples.amazon_serp_results
WITH r AS (SELECT nimble_integration.tools.amazon_serp('cookies') AS items)
SELECT 'cookies', item.product_name, item.asin, item.price, item.currency, item.rating,
       item.product_url, item.image_url, item.prime_eligible, item.amazons_choice,
       item.sponsored, item.store_location, item.position, item.agent_zip_code
FROM r LATERAL VIEW EXPLODE(items) t AS item;

INSERT INTO nimble_integration.examples.amazon_serp_results
WITH r AS (SELECT nimble_integration.tools.amazon_serp('wireless headphones') AS items)
SELECT 'wireless headphones', item.product_name, item.asin, item.price, item.currency, item.rating,
       item.product_url, item.image_url, item.prime_eligible, item.amazons_choice,
       item.sponsored, item.store_location, item.position, item.agent_zip_code
FROM r LATERAL VIEW EXPLODE(items) t AS item;

INSERT INTO nimble_integration.examples.amazon_serp_results
WITH r AS (SELECT nimble_integration.tools.amazon_serp('coffee maker') AS items)
SELECT 'coffee maker', item.product_name, item.asin, item.price, item.currency, item.rating,
       item.product_url, item.image_url, item.prime_eligible, item.amazons_choice,
       item.sponsored, item.store_location, item.position, item.agent_zip_code
FROM r LATERAL VIEW EXPLODE(items) t AS item;


-- 4. Row counts per keyword.
SELECT keyword, COUNT(*) AS n
FROM nimble_integration.examples.amazon_serp_results
GROUP BY keyword
ORDER BY keyword;
