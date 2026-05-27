/*
 * Analytics over the flattened amazon_serp_results table populated by
 * amazon_serp_keyword_table.sql.
 *
 * Prereqs:
 *   ../01_setup.sql
 *   ../tools/amazon_serp.sql
 *   amazon_serp_keyword_table.sql (run first, to populate the results)
 */

-- 1. Per-keyword price + rating summary.
SELECT
    keyword,
    COUNT(*)                            AS n_items,
    ROUND(AVG(price), 2)                AS avg_price,
    ROUND(MIN(price), 2)                AS min_price,
    ROUND(MAX(price), 2)                AS max_price,
    ROUND(AVG(rating), 2)               AS avg_rating,
    SUM(IF(prime_eligible, 1, 0))       AS prime_count,
    SUM(IF(sponsored, 1, 0))            AS sponsored_count,
    SUM(IF(amazons_choice, 1, 0))       AS amazons_choice_count
FROM nimble_integration.examples.amazon_serp_results
GROUP BY keyword
ORDER BY keyword;


-- 2. Top 5 cheapest organic (non-sponsored) results per keyword.
WITH ranked AS (
    SELECT
        keyword,
        product_name,
        price,
        rating,
        product_url,
        ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY price ASC) AS rn
    FROM nimble_integration.examples.amazon_serp_results
    WHERE sponsored = false
      AND price IS NOT NULL
)
SELECT keyword, product_name, price, rating, product_url
FROM ranked
WHERE rn <= 5
ORDER BY keyword, rn;


-- 3. Highest-rated items per keyword (rating >= 4.5), tie-broken by price.
SELECT keyword, product_name, asin, price, rating
FROM nimble_integration.examples.amazon_serp_results
WHERE rating >= 4.5
  AND price IS NOT NULL
ORDER BY keyword, rating DESC, price ASC;


-- 4. Prime-eligible share per keyword.
SELECT
    keyword,
    COUNT(*) AS total,
    SUM(IF(prime_eligible, 1, 0)) AS prime,
    ROUND(100.0 * SUM(IF(prime_eligible, 1, 0)) / COUNT(*), 1) AS prime_pct
FROM nimble_integration.examples.amazon_serp_results
GROUP BY keyword
ORDER BY keyword;
