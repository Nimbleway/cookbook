-- ============================================================
-- Local business universe in Databricks via Nimble agents
-- Pattern: queries -> STITCH many google_maps_search calls -> governed Delta table
--
-- google_maps_search returns ~20 results per query under
-- parsing:entities:SearchResult. nimble_agent_run is a table function whose
-- `parsing` column is a VARIANT, so we navigate it with `:` paths and explode
-- the SearchResult array with LATERAL variant_explode — one row per business —
-- then persist with CTAS.
--
-- Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_run.sql
--   Outbound networking enabled for the warehouse (see ../00_prereqs.md §1.5).
--
-- Run this in the Databricks SQL editor (Run All). The CTAS fans out one
-- google_maps_search call per query (~20 here), so it runs for a few minutes —
-- longer than the Statement Execution API's 50s sync cap, so prefer the SQL
-- editor (or submit async) over helpers/deploy_sql.py for the CTAS.
-- ============================================================

-- 1) Queries: each row becomes one google_maps_search call (~20 results each).
--    `query` is the full search string; `category` is a label you choose.
CREATE OR REPLACE TABLE nimble_integration.recipes.location_queries (
  query    STRING NOT NULL,
  category STRING
);

INSERT INTO nimble_integration.recipes.location_queries (query, category) VALUES
  ('coffee shops in Williamsburg Brooklyn',          'coffee'),
  ('coffee shops in Astoria Queens',                 'coffee'),
  ('coffee shops in Mission District San Francisco', 'coffee'),
  ('pizza restaurants in Chicago Loop',              'pizza'),
  ('pizza restaurants in North End Boston',          'pizza'),
  ('sushi restaurants in Downtown Seattle',          'sushi'),
  ('sushi restaurants in West Hollywood',            'sushi'),
  ('gyms in Austin Texas',                           'gym'),
  ('gyms in Midtown Manhattan',                      'gym'),
  ('yoga studios in Santa Monica',                   'yoga'),
  ('nail salons in Scottsdale Arizona',              'beauty'),
  ('hair salons in Nashville Tennessee',             'beauty'),
  ('auto repair shops in Denver Colorado',           'auto'),
  ('auto repair shops in Portland Oregon',           'auto'),
  ('dentists in Miami Florida',                      'dental'),
  ('dentists in Philadelphia',                       'dental'),
  ('veterinarians in Atlanta Georgia',               'vet'),
  ('bookstores in Portland Oregon',                  'retail'),
  ('florists in Charleston South Carolina',          'retail'),
  ('breweries in San Diego',                         'brewery');

-- 2) STITCH + enrich -> governed Delta table.
--    One google_maps_search per query (correlated LATERAL), explode the ~20
--    SearchResult entities (LATERAL variant_explode), one row per business.
--    The result is a managed Unity Catalog Delta table: access-controlled,
--    lineage-tracked, time-travelable.
CREATE OR REPLACE TABLE nimble_integration.recipes.local_businesses AS
SELECT
    q.query,
    q.category,
    biz:position::int                          AS position,
    biz:title::string                          AS name,
    biz:business_category[0]::string           AS business_category,
    biz:street_address::string                 AS street_address,
    biz:city::string                           AS city,
    biz:zip_code::string                       AS zip_code,
    biz:review_summary:overall_rating::double  AS rating,
    coalesce(biz:review_summary:review_count::int,
             biz:number_of_reviews::int)       AS review_count,
    biz:price_level::string                    AS price_level,
    biz:place_information:website_url::string  AS website,
    biz:business_status::string                AS business_status,
    biz:sponsored::boolean                     AS sponsored,
    biz:latitude::double                       AS latitude,
    biz:longitude::double                      AS longitude,
    biz:place_url::string                      AS maps_url,
    current_timestamp()                        AS enriched_at
FROM nimble_integration.recipes.location_queries q,
     LATERAL nimble_integration.tools.nimble_agent_run(
         'google_maps_search',
         to_json(named_struct('query', q.query))
     ) a,
     LATERAL variant_explode(a.parsing:entities:SearchResult) AS e(pos, key, biz)
WHERE a.status = 'success';

-- 3) Sanity check: how big is the universe?
SELECT count(*) AS total_businesses, count(DISTINCT query) AS queries
FROM nimble_integration.recipes.local_businesses;

-- 4) Screenshot query: the universe, ranked by popularity.
SELECT category, name, city, rating, review_count, price_level, website
FROM nimble_integration.recipes.local_businesses
ORDER BY review_count DESC NULLS LAST;

-- 5) Governance proof points (this is a real Unity Catalog Delta table):
--    DESCRIBE HISTORY nimble_integration.recipes.local_businesses;   -- time travel
--    GRANT SELECT ON TABLE nimble_integration.recipes.local_businesses TO `analysts`;
--    -- and it shows column/table lineage from location_queries -> nimble_agent_run -> here.
