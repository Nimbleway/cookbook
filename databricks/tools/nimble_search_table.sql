/*
 * tools/nimble_search_table.sql — Genie-friendly TABLE wrapper around nimble_search.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_search_table(query, max_results, focus, search_depth)
 *             RETURNS TABLE(...)
 * Prereq:     01_setup.sql and tools/nimble_search.sql have run successfully.
 * Runtime:    ~5 seconds to create; ~1-15s per call.
 *
 * Why a separate TABLE wrapper?
 *   Databricks Genie can only register tools that are TABLE functions
 *   (`RETURNS TABLE(...)`). The scalar nimble_search() returns
 *   ARRAY<STRUCT<...>>, which Genie won't pick up. This wrapper exposes
 *   the same data row-by-row so Genie / Mosaic-AI agents can call it.
 *
 *   Direct SQL callers can pick either:
 *     SELECT * FROM nimble_integration.tools.nimble_search_table('AI agent news', 5, 'news');
 *     -- vs --
 *     WITH r AS (SELECT nimble_integration.tools.nimble_search('AI agent news', 5, 'news') AS items)
 *     SELECT item.* FROM r LATERAL VIEW EXPLODE(items) t AS item;
 *
 * The COMMENT is intentionally long and example-rich: Genie reads it
 * verbatim to decide when to call this function. Keep the example
 * questions current with real user phrasing.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_search_table(
    query        STRING  COMMENT 'Natural-language search query, e.g. "best wireless headphones 2026" or "AI agent frameworks news 2026".',
    max_results  INT     DEFAULT 10
        COMMENT 'Maximum number of results (1-100). Server may return fewer.',
    focus        STRING  DEFAULT NULL
        COMMENT 'Optional focus mode: general | news | location | coding | geo | shopping | social | academic. NULL = server default (general). Pick `news` for recent news, `shopping` for product pages, `academic` for papers, etc.',
    search_depth STRING  DEFAULT NULL
        COMMENT 'Result detail: lite | fast (~2K chars per result) | deep (full page scrape). NULL = server default. NOTE: fast and deep only apply when focus=general (or focus omitted); other focus modes ignore search_depth.'
)
RETURNS TABLE(
    title       STRING  COMMENT 'Page title from the search result',
    description STRING  COMMENT 'Meta description or short snippet preview',
    url         STRING  COMMENT 'Full URL of the result page',
    content     STRING  COMMENT 'Extracted page content; only populated when search_depth = fast or deep'
)
COMMENT 'Live web search results for a natural-language query, returned as rows.
Use this function whenever the user asks about CURRENT, LIVE, or RECENT
web content — news, articles, papers, product pages, blog posts, social
discussions, code snippets, locations, anything indexable on the live
web. Each call hits the live web via the Nimble Search API, so results
reflect the moment of the query. Pick a `focus` mode to bias the
sub-agent pool (news / shopping / social / academic / coding / geo /
location). Use `search_depth = deep` when the answer needs full article
bodies, `fast` for snippets, `lite` for cheap link inventories. Example
questions this answers:
"What are the top news stories about AI agent frameworks this week?",
"Find recent academic papers about retrieval-augmented generation.",
"Show me product pages selling stand-up desks under $400.",
"What are people saying on social media about a new running-shoe launch?",
"Give me the 5 most relevant articles on Snowflake Cortex Agents."'
RETURN (
    WITH raw AS (
        SELECT nimble_integration.tools.nimble_search(query, max_results, focus, search_depth) AS arr
    )
    SELECT item.*
    FROM raw
    LATERAL VIEW EXPLODE(arr) items AS item
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT * FROM nimble_integration.tools.nimble_search_table('AI agent frameworks news', 5, 'news') LIMIT 3;
