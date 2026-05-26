/*
 * 03_nimble_extract.sql — wraps POST https://sdk.nimbleway.com/v1/extract
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(...) RETURNS STRING
 * Prereq:      01_setup.sql has run successfully
 * Runtime:     ~5 seconds to create; ~3-30s per call depending on driver + render.
 *
 * API reference:  https://docs.nimbleway.com/api-reference/extract/extract
 *
 * For high-protection sites or heavy browser_actions, use the async variant
 * (/v1/extract/async + /v1/tasks/{id}/results) — out of scope for this proc.
 * Retailer-specific PDP parsers (Amazon / Walmart / Target) are exposed by
 * Nimble as Web Search Agents at /v1/agent/run — see the recipe notebook for
 * how to do structured extraction without them (markdown + Cortex Complete).
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.TOOLS;

CREATE OR REPLACE PROCEDURE NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(
    url      STRING,
    render   BOOLEAN DEFAULT TRUE,
    parse    BOOLEAN DEFAULT FALSE,
    parser   OBJECT  DEFAULT NULL,   -- custom parser recipe; required when parse=TRUE
    formats  ARRAY   DEFAULT NULL,   -- subset of: 'html','markdown','screenshot','headers','links'
    country  STRING  DEFAULT NULL,   -- ISO Alpha-2, e.g. 'US'
    locale   STRING  DEFAULT NULL,   -- e.g. 'en-US' or 'auto'
    driver   STRING  DEFAULT 'vx6'   -- vx6 | vx8 | vx8-pro | vx10 | vx10-pro
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('requests', 'snowflake-snowpark-python')   -- required because handler takes `session` as first arg
EXTERNAL_ACCESS_INTEGRATIONS = (NIMBLE_API_ACCESS)
SECRETS = ('cred' = NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
HANDLER = 'main'
AS
$$
import _snowflake
import requests
import json

NIMBLE_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"

def main(session, url, render, parse, parser, formats, country, locale, driver):
    token = _snowflake.get_generic_secret_string("cred")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Client-Source": "snowflake-cortex-agent",
    }
    body = {
        "url": url,
        "render": render,
        "parse": parse,
        "driver": driver,
    }
    if parser:
        body["parser"] = dict(parser)
    if formats:
        body["formats"] = list(formats)
    else:
        body["formats"] = ["markdown"]
    if country:
        body["country"] = country
    if locale:
        body["locale"] = locale

    try:
        resp = requests.post(NIMBLE_EXTRACT_URL, json=body, headers=headers, timeout=90)
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

GRANT USAGE ON PROCEDURE NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT(
    STRING, BOOLEAN, BOOLEAN, OBJECT, ARRAY, STRING, STRING, STRING
) TO ROLE NIMBLE_ROLE;

-- Smoke test (uncomment to verify after deploy):
-- CALL NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT('https://nimbleway.com');
