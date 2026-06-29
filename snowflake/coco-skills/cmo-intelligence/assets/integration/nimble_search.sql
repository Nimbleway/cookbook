/*
 * cortex-agent-tools/01_nimble_search.sql — wraps POST https://sdk.nimbleway.com/v1/search
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(...) RETURNS VARIANT
 * Prereq:      setup/setup.sql has run successfully
 * Runtime:     ~5 seconds to create; ~1-15s per call depending on focus + search_depth.
 *
 * API reference:  https://docs.nimbleway.com/api-reference/search/search
 *
 * Scalar UDF returning VARIANT so callers can navigate the JSON response inline
 * with `:field` syntax — no PARSE_JSON or RESULT_SCAN required. Composable in
 * SELECT, views, dbt models, and lateral joins with warehouse data. The Cortex
 * Agent registered in 03_cortex_agent.sql consumes the same VARIANT output via
 * tool_resources.<name>.type = "function".
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.TOOLS;

CREATE OR REPLACE FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(
    query           STRING,
    max_results     INTEGER DEFAULT 10,
    focus           STRING  DEFAULT NULL,    -- general | news | location | coding | geo | shopping | social | academic
    search_depth    STRING  DEFAULT 'fast',  -- lite | fast | deep
    country         STRING  DEFAULT 'US',
    locale          STRING  DEFAULT 'en',
    time_range      STRING  DEFAULT NULL,    -- hour | day | week | month | year
    include_domains STRING  DEFAULT NULL,    -- comma-separated, e.g. 'amazon.com,walmart.com'
    exclude_domains STRING  DEFAULT NULL     -- comma-separated, e.g. 'pinterest.com,quora.com'
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('requests')
EXTERNAL_ACCESS_INTEGRATIONS = (NIMBLE_API_ACCESS)
SECRETS = ('cred' = NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
HANDLER = 'main'
AS
$$
import _snowflake
import requests

NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"

def _csv(value):
    if not value:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None

def main(query, max_results, focus, search_depth, country, locale, time_range,
         include_domains, exclude_domains):
    token = _snowflake.get_generic_secret_string("cred")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Client-Source": "snowflake-cortex-agent",
    }
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
    include = _csv(include_domains)
    if include:
        body["include_domains"] = include
    exclude = _csv(exclude_domains)
    if exclude:
        body["exclude_domains"] = exclude

    # Return a structured VARIANT on failure (mirrors the NIMBLE_AGENT_RUN UDTF) so a
    # transient API error degrades to a usable "tool failed" payload instead of raising
    # and aborting the calling query or Cortex Agent turn. Success path is unchanged.
    try:
        resp = requests.post(NIMBLE_SEARCH_URL, json=body, headers=headers, timeout=60)
    except requests.RequestException as e:
        return {"status": "request_error", "error": str(e)}
    if resp.status_code >= 400:
        try:
            raw = resp.json()
        except ValueError:
            raw = {"text": resp.text}
        return {"status": f"http_{resp.status_code}", "status_code": resp.status_code,
                "error": "request failed", "raw": raw}
    try:
        return resp.json()
    except ValueError:
        return {"status": "invalid_json", "error": "response was not JSON", "raw": resp.text}
$$;

GRANT USAGE ON FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(
    STRING, INTEGER, STRING, STRING, STRING, STRING, STRING, STRING, STRING
) TO ROLE NIMBLE_ROLE;

-- Smoke test (uncomment to verify after deploy):
-- SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH('AI agents news', 5):results[0]:url::STRING;
