-- Basic nimble_search patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_search.sql
--   ../tools/nimble_search_table.sql

-- 1. Simplest TABLE-form call (also what Genie uses under the hood).
SELECT *
FROM nimble_integration.tools.nimble_search_table('AI agent frameworks 2026', 5);


-- 2. Focus on news, get titles + URLs only.
SELECT title, url
FROM nimble_integration.tools.nimble_search_table('Databricks Genie launch news', 10, 'news')
ORDER BY title;


-- 3. Deep search — pulls full article bodies. More expensive; use sparingly.
-- Note: search_depth='fast'/'deep' is only valid with focus='general'
-- (or focus omitted). Other focus modes ignore search_depth.
SELECT title, url, length(content) AS content_len
FROM nimble_integration.tools.nimble_search_table(
    'retrieval augmented generation survey paper',
    3,
    'general',
    'deep'
)
ORDER BY content_len DESC;


-- 4. Scalar form for SQL composition (e.g. joining against another table).
WITH r AS (
    SELECT nimble_integration.tools.nimble_search('open-source LLM benchmarks', 10) AS items
)
SELECT item.title, item.url, substring(item.description, 1, 120) AS snippet
FROM r
LATERAL VIEW EXPLODE(items) t AS item;
