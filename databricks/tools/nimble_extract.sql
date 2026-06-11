/*
 * tools/nimble_extract.sql — wraps Nimble's Extract API as a UC table function.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema; READ on secret('nimble','api_key').
 * Creates:    nimble_integration.tools._nimble_extract(...)  RETURNS TABLE  (Python UDTF)
 *             nimble_integration.tools.nimble_extract(...)    RETURNS TABLE  (public wrapper)
 * Prereq:     01_setup.sql has run; the `nimble` secret scope + `api_key` exist;
 *             the workspace Preview "Enable networking for isolated workloads in
 *             Serverless SQL Warehouses" is ON and the warehouse was cold-restarted
 *             (Python UDF/UDTF egress needs both — see README "Prerequisites").
 * Runtime:    ~5 seconds to create; ~3-30s per call depending on driver + render.
 *
 * API docs:   https://docs.nimbleway.com/api-reference/extract/extract
 *
 * Design (UDTF-only):
 *   Databricks Genie registers TABLE functions as tools, so every capability
 *   ships as a table function — no scalar / `_table` twin to maintain.
 *     - _nimble_extract : LANGUAGE PYTHON UDTF. eval() does requests.post and
 *                         yields one row per requested format. `import`s live
 *                         INSIDE eval() (module-level imports are not visible to
 *                         the handler class in a UC Python UDTF). On any error it
 *                         yields zero rows, so a batch over many URLs is never
 *                         aborted by one bad row.
 *     - nimble_extract  : thin SQL RETURNS TABLE wrapper that supplies DEFAULTs
 *                         and injects the API key via secret(). The api_key never
 *                         appears at a call site.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools._nimble_extract(
    url      STRING,
    render   BOOLEAN,
    format   STRING,
    country  STRING,
    locale   STRING,
    driver   STRING,
    api_key  STRING
)
RETURNS TABLE(url STRING, format STRING, content STRING)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind nimble_extract(). Call the public nimble_extract() wrapper instead.'
AS $$
class Handler:
    def eval(self, url, render, format, country, locale, driver, api_key):
        import requests
        body = {"url": url, "render": render, "driver": driver, "formats": [format]}
        if country:
            body["country"] = country
        if locale:
            body["locale"] = locale
        headers = {
            "Authorization": "Bearer " + (api_key or ""),
            "Content-Type": "application/json",
            "X-Client-Source": "nimble-dbx-udtf",
        }
        try:
            resp = requests.post("https://sdk.nimbleway.com/v1/extract", json=body, headers=headers, timeout=90)
            data = resp.json().get("data", {}) if 200 <= resp.status_code < 300 else {}
        except Exception:
            data = {}
        content = data.get(format)
        if content is not None:
            if not isinstance(content, str):
                import json as _json
                content = _json.dumps(content)
            yield (url, format, content)
$$;

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_extract(
    url     STRING  COMMENT 'Absolute URL of the page to fetch and parse, e.g. "https://www.nimbleway.com".',
    render  BOOLEAN DEFAULT TRUE
        COMMENT 'Render JavaScript before extracting (headless browser). TRUE for SPAs / dynamic pages; FALSE is faster for static HTML.',
    format  STRING  DEFAULT 'markdown'
        COMMENT 'Output format: html | markdown | links. Markdown is the LLM-friendly default.',
    country STRING  DEFAULT NULL
        COMMENT 'ISO Alpha-2 country to fetch from, e.g. US. NULL = server default.',
    locale  STRING  DEFAULT NULL
        COMMENT 'Language/locale hint, e.g. en-US or auto. NULL = server default.',
    driver  STRING  DEFAULT 'vx6'
        COMMENT 'Fetch driver / unblocking tier: vx6 | vx8 | vx8-pro | vx10 | vx10-pro. Higher tiers unblock harder targets at higher cost.'
)
RETURNS TABLE(
    url     STRING COMMENT 'The URL that was fetched (echoed from input, so joins/CTAS keep the key).',
    format  STRING COMMENT 'The output format of the content column.',
    content STRING COMMENT 'The fetched page rendered in the requested format (markdown/html/links).'
)
COMMENT 'Fetch and parse a single web page via the Nimble Extract API, returned as a row (url, format, content). Use when you have a specific URL and need its content as markdown/html/links — e.g. enrich a table of URLs with page text. Each call fetches the live page through Nimble. Returns zero rows on fetch failure rather than raising, so a batch CTAS over many URLs is not aborted by one bad row. Example: SELECT content FROM nimble_extract("https://www.nimbleway.com").'
RETURN SELECT * FROM nimble_integration.tools._nimble_extract(
    url, render, format, country, locale, driver, secret('nimble', 'api_key')
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT length(content) AS md_len FROM nimble_integration.tools.nimble_extract('https://www.nimbleway.com');
