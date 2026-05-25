/*
 * 02_nimble_search.sql — wraps POST https://sdk.nimbleway.com/v1/search
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(...) RETURNS STRING
 * Prereq:      01_setup.sql has run successfully
 * Runtime:     ~5 seconds to create; ~1-15s per call depending on focus + search_depth.
 *
 * API reference:  https://docs.nimbleway.com/api-reference/search/search
 *
 * Returns a STRING containing the JSON response body. Callers parse with
 * PARSE_JSON(...) on the Snowflake side. This mirrors how the Cortex Agent
 * registered in 04_cortex_agent.sql consumes tool output.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.TOOLS;

CREATE OR REPLACE PROCEDURE NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(
    query           STRING,
    max_results     INTEGER DEFAULT 10,
    focus           STRING  DEFAULT NULL,    -- general | news | location | coding | geo | shopping | social | academic
    search_depth    STRING  DEFAULT 'fast',  -- lite | fast | deep
    include_answer  BOOLEAN DEFAULT FALSE,
    country         STRING  DEFAULT 'US',
    locale          STRING  DEFAULT 'en',
    include_domains ARRAY   DEFAULT NULL,
    exclude_domains ARRAY   DEFAULT NULL,
    time_range      STRING  DEFAULT NULL     -- hour | day | week | month | year
)
RETURNS STRING
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
import json

NIMBLE_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"

def main(
    session,
    query,
    max_results,
    focus,
    search_depth,
    include_answer,
    country,
    locale,
    include_domains,
    exclude_domains,
    time_range,
):
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
        "include_answer": include_answer,
        "country": country,
        "locale": locale,
    }
    if focus:
        body["focus"] = focus
    if include_domains:
        body["include_domains"] = list(include_domains)
    if exclude_domains:
        body["exclude_domains"] = list(exclude_domains)
    if time_range:
        body["time_range"] = time_range

    try:
        resp = requests.post(NIMBLE_SEARCH_URL, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        return json.dumps(resp.json())
    except requests.HTTPError as e:
        return json.dumps({
            "error": "http_error",
            "status_code": e.response.status_code,
            "body": e.response.text,
        })
    except requests.RequestException as e:
        return json.dumps({"error": "request_failed", "message": str(e)})
$$;

GRANT USAGE ON PROCEDURE NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH(
    STRING, INTEGER, STRING, STRING, BOOLEAN, STRING, STRING, ARRAY, ARRAY, STRING
) TO ROLE NIMBLE_ROLE;

-- Smoke test (uncomment to verify after deploy):
-- CALL NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH('AI agents news', 5);
