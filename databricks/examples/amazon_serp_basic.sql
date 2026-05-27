-- Basic amazon_serp patterns. Prereqs: ../01_setup.sql, ../tools/amazon_serp.sql.

-- 1. Inspect the raw array result for a single keyword.
SELECT nimble_integration.tools.amazon_serp('cookies') AS results;


-- 2. Flatten rows. The function wraps http_request(), which Spark refuses
-- to evaluate inside a Generate (EXPLODE) directly; materialize the array
-- in a CTE first, then LATERAL VIEW EXPLODE on the column.
WITH r AS (
    SELECT nimble_integration.tools.amazon_serp('cookies') AS items
)
SELECT item.*
FROM r
LATERAL VIEW EXPLODE(items) t AS item;


-- 3. Top 10 cheapest non-sponsored items, sorted by price.
WITH r AS (
    SELECT nimble_integration.tools.amazon_serp('cookies') AS items
)
SELECT
    item.product_name,
    item.asin,
    item.price,
    item.rating,
    item.product_url
FROM r
LATERAL VIEW EXPLODE(items) t AS item
WHERE item.sponsored = false
  AND item.price IS NOT NULL
ORDER BY item.price ASC
LIMIT 10;
