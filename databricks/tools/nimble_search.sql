/*
 * tools/nimble_search.sql — wraps Nimble's Web Search API as a UC table function.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema; READ on secret('nimble','api_key').
 * Creates:    nimble_integration.tools._nimble_search(...)  RETURNS TABLE  (Python UDTF)
 *             nimble_integration.tools.nimble_search(...)    RETURNS TABLE  (public wrapper)
 * Prereq:     01_setup.sql has run; the `nimble` secret scope + `api_key` exist;
 *             the workspace Preview "Enable networking for isolated workloads in
 *             Serverless SQL Warehouses" is ON and the warehouse was cold-restarted
 *             (Python UDF/UDTF egress needs both — see README "Prerequisites").
 * Runtime:    ~5 seconds to create; ~1-15s per call (depends on focus + search_depth).
 *
 * API docs:   https://docs.nimbleway.com/api-reference/search/search
 *
 * Design (UDTF-only):
 *   Databricks Genie registers TABLE functions as tools, so every capability
 *   ships as a table function — no scalar / `_table` twin to maintain.
 *     - _nimble_search : LANGUAGE PYTHON UDTF. eval() does requests.post and
 *                        yields one row per search result. `import`s live INSIDE
 *                        eval() (module-level imports are not visible to the
 *                        handler class in a UC Python UDTF). On any error it
 *                        yields zero rows, so a batch over many queries is never
 *                        aborted by one bad row.
 *     - nimble_search  : thin SQL RETURNS TABLE wrapper that supplies DEFAULTs
 *                        and injects the API key via secret(). The api_key never
 *                        appears at a call site.
 *
 * Notes on parameters:
 *   - focus:        general | news | location | coding | geo | shopping |
 *                   social | academic. NULL leaves the server-side default.
 *   - search_depth: lite (metadata) | fast (~2K chars) | deep (full scrape).
 *                   fast/deep require focus = general (or focus omitted).
 *   - include/exclude_domains: comma-separated; split to a list on the wire.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools._nimble_search(
    query           STRING,
    max_results     INT,
    focus           STRING,
    search_depth    STRING,
    country         STRING,
    locale          STRING,
    time_range      STRING,
    include_domains STRING,
    exclude_domains STRING,
    api_key         STRING
)
RETURNS TABLE(title STRING, description STRING, url STRING, content STRING)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind nimble_search(). Call the public nimble_search() wrapper instead.'
AS $$
class Handler:
    def eval(self, query, max_results, focus, search_depth, country, locale,
             time_range, include_domains, exclude_domains, api_key):
        import requests

        def csv(value):
            if not value:
                return None
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts or None

        body = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "country": country,
            "locale": locale,
        }
        if focus:
            body["focus"] = focus
        if time_range:
            body["time_range"] = time_range
        inc = csv(include_domains)
        if inc:
            body["include_domains"] = inc
        exc = csv(exclude_domains)
        if exc:
            body["exclude_domains"] = exc

        headers = {
            "Authorization": "Bearer " + (api_key or ""),
            "Content-Type": "application/json",
            "X-Client-Source": "nimble-dbx-udtf",
        }
        try:
            resp = requests.post("https://sdk.nimbleway.com/v1/search", json=body, headers=headers, timeout=60)
            data = resp.json() if 200 <= resp.status_code < 300 else {}
        except Exception:
            data = {}
        for r in (data.get("results") or []):
            yield (r.get("title"), r.get("description"), r.get("url"), r.get("content"))
$$;

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_search(
    query        STRING  COMMENT 'Natural-language search query, e.g. "best wireless headphones 2026" or "AI agent frameworks news".',
    max_results  INT     DEFAULT 10
        COMMENT 'Maximum number of results to return (1-100). Server may return fewer.',
    focus        STRING  DEFAULT NULL
        COMMENT 'Focus mode: general | news | location | coding | geo | shopping | social | academic. NULL = server default (general).',
    search_depth STRING  DEFAULT 'fast'
        COMMENT 'Result detail: lite | fast (~2K chars per result) | deep (full page scrape). fast/deep require focus=general (or focus omitted).',
    country      STRING  DEFAULT 'US'
        COMMENT 'ISO Alpha-2 country to search from, e.g. US, GB, DE.',
    locale       STRING  DEFAULT 'en'
        COMMENT 'Language/locale hint, e.g. en or en-US.',
    time_range   STRING  DEFAULT NULL
        COMMENT 'Restrict to a recency window: hour | day | week | month | year. NULL = no restriction.',
    include_domains STRING DEFAULT NULL
        COMMENT 'Comma-separated allowlist of domains, e.g. "amazon.com,walmart.com". NULL = no restriction.',
    exclude_domains STRING DEFAULT NULL
        COMMENT 'Comma-separated blocklist of domains, e.g. "pinterest.com,quora.com". NULL = none.'
)
RETURNS TABLE(
    title       STRING COMMENT 'Page title from the search result.',
    description STRING COMMENT 'Meta description or short snippet preview.',
    url         STRING COMMENT 'Full URL of the result page.',
    content     STRING COMMENT 'Extracted page content; populated when search_depth = fast or deep.'
)
COMMENT 'Live web search via the Nimble Search API, returned as rows (title, description, url, content). Use whenever the user asks about CURRENT, LIVE, or RECENT web content — news, articles, papers, product pages, blog posts, social discussions, code, locations. Each call hits the live web through Nimble, so results reflect the moment of the query. Pick a `focus` mode to bias the sub-agent pool (news / shopping / social / academic / coding / geo / location); use search_depth = deep for full article bodies, fast for snippets, lite for cheap link inventories. Returns zero rows on failure rather than raising, so a batch over many queries is not aborted by one bad row. Example questions: "top news on AI agent frameworks this week", "product pages selling stand-up desks under $400", "recent papers on retrieval-augmented generation".'
RETURN SELECT * FROM nimble_integration.tools._nimble_search(
    query, max_results, focus, search_depth, country, locale,
    time_range, include_domains, exclude_domains, secret('nimble', 'api_key')
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT title, url FROM nimble_integration.tools.nimble_search('AI agent frameworks news', 5, 'news');
