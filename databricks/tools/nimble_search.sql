/*
 * tools/nimble_search.sql — wraps Nimble's web Search API as a UC SQL function.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_search(query, max_results, focus, search_depth)
 *             RETURNS ARRAY<STRUCT<...>>
 * Prereq:     01_setup.sql has run successfully.
 * Runtime:    ~5 seconds to create; ~1-15s per call (depends on focus + search_depth).
 *
 * API docs:   https://docs.nimbleway.com/api-reference/search/search
 *
 * The COMMENT below is the LLM-facing description. Genie / Mosaic-AI agents
 * read it to decide whether to call this function. Keep it accurate.
 *
 * Notes on parameters:
 *   - max_results:  1..100, server may return fewer; default 10.
 *   - focus:        general | news | location | coding | geo | shopping |
 *                   social | academic. NULL leaves the server-side default.
 *   - search_depth: lite (metadata only) | fast (~2K chars per result) |
 *                   deep (full page scrape). Cost and latency grow
 *                   accordingly. NOTE: `fast` and `deep` are only valid
 *                   when focus = 'general' (or focus omitted). Other
 *                   focus modes (news / shopping / social / ...) ignore
 *                   search_depth and use their own retrieval policy.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_search(
    query        STRING  COMMENT 'Natural-language search query, e.g. "best wireless headphones 2026" or "AI agent frameworks news".',
    max_results  INT     DEFAULT 10
        COMMENT 'Maximum number of results to return (1-100). Server may return fewer.',
    focus        STRING  DEFAULT NULL
        COMMENT 'Focus mode: general | news | location | coding | geo | shopping | social | academic. NULL = server default (general).',
    search_depth STRING  DEFAULT NULL
        COMMENT 'Result detail: lite | fast (~2K chars per result) | deep (full page scrape). NULL = server default. fast/deep require focus=general (or focus omitted).'
)
RETURNS ARRAY<STRUCT<
    title:       STRING,
    description: STRING,
    url:         STRING,
    content:     STRING
>>
COMMENT 'Live web search via the Nimble Search API. Returns a list of relevant pages for the given natural-language query, optionally focused on news / shopping / social / academic / coding / geo / location verticals. Useful when the user asks about CURRENT events, trends, public web content, news headlines, product listings across sites, or any question whose answer lives on the live web. Each call hits the live web through Nimble, so results reflect the moment of the query.'
RETURN (
    -- The Search API responds with a JSON object. We extract the `results`
    -- array; each item has title, description, url, and (when search_depth
    -- is fast/deep) content.
    SELECT COALESCE(
        from_json(
            response.text,
            'STRUCT<results: ARRAY<STRUCT<title STRING, description STRING, url STRING, content STRING>>>'
        ).results,
        ARRAY()
    )
    FROM (
        SELECT http_request(
            conn    => 'nimble_api',
            method  => 'POST',
            path    => '/v1/search',
            headers => map('Content-Type', 'application/json'),
            json    => to_json(named_struct(
                'query',        query,
                'max_results',  max_results,
                'focus',        focus,
                'search_depth', search_depth
            ))
        ) AS response
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT size(nimble_integration.tools.nimble_search('AI agent frameworks news', 5, 'news')) AS n;
