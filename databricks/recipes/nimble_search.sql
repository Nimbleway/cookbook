-- Basic nimble_search patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_search.sql
--
-- nimble_search is a table function (UDTF) — call it in the FROM clause.

-- 1. Simplest call (also what Genie uses under the hood).
SELECT *
FROM nimble_integration.tools.nimble_search('AI agent frameworks 2026', 5);


-- 2. Focus on news, get titles + URLs only.
SELECT title, url
FROM nimble_integration.tools.nimble_search('Databricks Genie launch news', 10, 'news')
ORDER BY title;


-- 3. Deep search — pulls full article bodies. More expensive; use sparingly.
-- Note: search_depth='fast'/'deep' is only valid with focus='general'
-- (or focus omitted). Other focus modes ignore search_depth.
SELECT title, url, length(content) AS content_len
FROM nimble_integration.tools.nimble_search(
    'retrieval augmented generation survey paper',
    3,
    'general',
    'deep'
)
ORDER BY content_len DESC;


-- 4. Compose in SQL — join search results against another table.
WITH hits AS (
    SELECT title, url, description
    FROM nimble_integration.tools.nimble_search('open-source LLM benchmarks', 10)
)
SELECT title, url, substring(description, 1, 120) AS snippet
FROM hits
ORDER BY title;
