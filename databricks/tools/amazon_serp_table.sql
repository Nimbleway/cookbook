/*
 * tools/amazon_serp_table.sql — Genie-friendly TABLE wrapper around amazon_serp.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.amazon_serp_table(keyword STRING)
 *             RETURNS TABLE(...)
 * Prereq:     01_setup.sql and tools/amazon_serp.sql have run successfully.
 * Runtime:    ~5 seconds to create; ~5-15s per call depending on Amazon.
 *
 * Why a separate TABLE wrapper?
 *   Databricks Genie can only register tools that are TABLE functions
 *   (`RETURNS TABLE(...)`). The scalar amazon_serp() returns
 *   ARRAY<STRUCT<...>>, which Genie won't pick up. This wrapper exposes
 *   the same data row-by-row so Genie / Mosaic-AI agents can call it.
 *
 *   Direct SQL callers can pick either:
 *     SELECT * FROM nimble_integration.tools.amazon_serp_table('cookies');
 *     -- vs --
 *     WITH r AS (SELECT nimble_integration.tools.amazon_serp('cookies') AS items)
 *     SELECT item.* FROM r LATERAL VIEW EXPLODE(items) t AS item;
 *
 * The COMMENT is intentionally long and example-rich: Genie uses it
 * verbatim to decide when to call this function. Keep the example
 * questions current with real user phrasing.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.amazon_serp_table(
    keyword STRING COMMENT 'Amazon search keyword, e.g. "wireless headphones", "running shoes", "coffee maker". Pass the keyword exactly as a shopper would type it into the Amazon search bar.'
)
RETURNS TABLE(
    product_name   STRING  COMMENT 'Product title as listed on Amazon',
    asin           STRING  COMMENT 'Amazon Standard Identification Number (10-character product ID)',
    price          DOUBLE  COMMENT 'Listed price in the local currency; NULL if not displayed',
    currency       STRING  COMMENT 'ISO currency code or symbol shown on the listing (e.g. "USD", "$")',
    rating         DOUBLE  COMMENT 'Average customer star rating, 0.0 to 5.0; NULL if not rated',
    product_url    STRING  COMMENT 'Canonical Amazon URL for the product detail page',
    image_url      STRING  COMMENT 'URL of the primary product thumbnail image',
    prime_eligible BOOLEAN COMMENT 'TRUE if the listing shows the Amazon Prime badge',
    amazons_choice BOOLEAN COMMENT 'TRUE if the listing carries the "Amazon''s Choice" badge',
    sponsored      BOOLEAN COMMENT 'TRUE if the listing is a paid/sponsored placement rather than organic',
    store_location STRING  COMMENT 'Seller / store location string as displayed (when present)',
    position       INT     COMMENT 'Rank of this result on the search results page (1 = top)',
    agent_zip_code STRING  COMMENT 'ZIP / postal code the Nimble agent used to localize the search'
)
COMMENT 'Live Amazon search results for a given keyword, returned as rows.
Use this function whenever the user asks about CURRENT or LIVE Amazon
listings, prices, ratings, sponsored placements, Prime eligibility,
Amazon''s Choice badges, or search-result rankings for a keyword.
Ideal for search visibility analysis, assortment tracking, competitive
price checks, and keyword-based product monitoring on Amazon. Each
call hits the Amazon SERP live via the Nimble web-data API, so results
reflect the marketplace at query time. Example questions this answers:
"What are the top 10 results for ''wireless headphones'' on Amazon?",
"How many sponsored listings appear for ''running shoes''?",
"What''s the average price of the first page of results for ''coffee maker''?",
"Which listings for ''yoga mat'' carry the Amazon''s Choice badge?".'
RETURN (
    WITH raw AS (
        SELECT nimble_integration.tools.amazon_serp(keyword) AS arr
    )
    SELECT item.*
    FROM raw
    LATERAL VIEW EXPLODE(arr) items AS item
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT * FROM nimble_integration.tools.amazon_serp_table('cookies') LIMIT 5;
