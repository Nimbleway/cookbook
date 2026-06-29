/*
 * cortex-agent-tools/02_nimble_extract.sql — wraps POST https://sdk.nimbleway.com/v1/extract
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(...) RETURNS VARIANT
 * Prereq:      setup/setup.sql has run successfully
 * Runtime:     ~5 seconds to create; ~3-30s per call depending on driver + render.
 *
 * API reference:  https://docs.nimbleway.com/api-reference/extract/extract
 *
 * Scalar UDF returning VARIANT — composable in SELECT and consumable by the
 * Cortex Agent in 03_cortex_agent.sql via tool_resources.<name>.type = "function".
 *
 * Signature kept to STRING / BOOLEAN params only. Cortex Agent custom tools
 * cannot accept OBJECT or VARIANT parameters, so the previous proc's `parser`
 * (OBJECT) and multi-format `formats` (ARRAY) inputs are not exposed here. For
 * custom parser recipes use the Nimble API directly; for async / heavy renders
 * use the /v1/extract/async endpoint — out of scope for this UDF.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.TOOLS;

CREATE OR REPLACE FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(
    url      STRING,
    render   BOOLEAN DEFAULT TRUE,
    format   STRING  DEFAULT 'markdown',  -- html | markdown | screenshot | headers | links
    country  STRING  DEFAULT NULL,        -- ISO Alpha-2, e.g. 'US'
    locale   STRING  DEFAULT NULL,        -- e.g. 'en-US' or 'auto'
    driver   STRING  DEFAULT 'vx6'        -- vx6 | vx8 | vx8-pro | vx10 | vx10-pro
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

NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

def main(url, render, format, country, locale, driver):
    token = _snowflake.get_generic_secret_string("cred")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Client-Source": "snowflake-cortex-agent",
    }
    body = {
        "url": url,
        "render": render,
        "driver": driver,
        "formats": [format],
    }
    if country:
        body["country"] = country
    if locale:
        body["locale"] = locale

    # Return a structured VARIANT on failure (mirrors the NIMBLE_AGENT_RUN UDTF) so a
    # transient API error degrades to a usable "tool failed" payload instead of raising
    # and aborting the calling query or Cortex Agent turn. Success path is unchanged.
    try:
        resp = requests.post(NIMBLE_EXTRACT_URL, json=body, headers=headers, timeout=90)
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

GRANT USAGE ON FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(
    STRING, BOOLEAN, STRING, STRING, STRING, STRING
) TO ROLE NIMBLE_ROLE;

-- Smoke test (uncomment to verify after deploy):
-- SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT('https://nimbleway.com'):data:markdown::STRING;
