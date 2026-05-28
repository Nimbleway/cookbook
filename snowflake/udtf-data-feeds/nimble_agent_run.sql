/*
 * udtf-data-feeds/nimble_agent_run.sql — wraps POST https://sdk.nimbleway.com/v1/agents/run
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(...) RETURNS TABLE
 * Prereq:      setup/setup.sql has run successfully
 * Runtime:     ~5 seconds to create; ~5-60s per call depending on the agent
 *              (e.g. amazon_pdp ~10-20s; google_search ~3-8s).
 *
 * API reference:    https://docs.nimbleway.com/api-reference/agents/run-realtime
 * Agent gallery:    https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery
 *
 * Python tabular UDF (UDTF) that runs one Nimble Web Search Agent (WSA) per
 * input row and yields a single row of structured output per call. Designed for
 * lateral joins:
 *
 *   SELECT p.sku, a.parsing:web_price::NUMBER AS amazon_price
 *   FROM   products p,
 *          TABLE(NIMBLE_AGENT_RUN(
 *              'amazon_pdp',
 *              OBJECT_CONSTRUCT('asin', p.amazon_asin)
 *          )) a;
 *
 * UDTFs are NOT valid Cortex Agent custom tools (the agent runtime only
 * accepts scalar UDFs and stored procedures — see ../cortex-agent-tools/ for
 * those). This is purpose-built for the BI / lateral-join use case where you
 * want one typed output row per warehouse row.
 *
 * Locale, country, and other per-agent options go inside `params` per the
 * agent's input schema, e.g. OBJECT_CONSTRUCT('keyword', 'shoes', 'country', 'US').
 *
 * 4xx / 5xx responses (including 429 rate-limit) are caught and surfaced as a
 * row with `status` set to 'http_<code>' and the error body in `raw`, so a
 * single failing input row does not abort the whole lateral join.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;
USE SCHEMA NIMBLE_INTEGRATION.TOOLS;

CREATE OR REPLACE FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
    agent_name  STRING,
    params      OBJECT
)
RETURNS TABLE (
    task_id     STRING,
    status      STRING,
    status_code INTEGER,
    url         STRING,
    parsing     VARIANT,
    warnings    VARIANT,
    raw         VARIANT
)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('requests')
EXTERNAL_ACCESS_INTEGRATIONS = (NIMBLE_API_ACCESS)
SECRETS = ('cred' = NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
HANDLER = 'NimbleAgentRun'
AS
$$
import _snowflake
import requests

NIMBLE_AGENTS_RUN_URL = "https://sdk.nimbleway.com/v1/agents/run"


class NimbleAgentRun:
    def process(self, agent_name, params):
        token = _snowflake.get_generic_secret_string("cred")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Client-Source": "snowflake-cortex-agent",
        }

        # Snowflake delivers an OBJECT parameter to Python as a dict (or None if
        # the caller passed NULL). The guard below keeps the UDTF defensive against
        # unexpected runtime types should the column ever be VARIANT-typed at the
        # call site (Snowflake will silently widen, then deliver whatever's inside).
        if params is None:
            params_body = {}
        elif isinstance(params, dict):
            params_body = params
        else:
            yield (
                None,
                "invalid_input",
                None,
                None,
                None,
                None,
                {"error": f"params must be an OBJECT (got {type(params).__name__})"},
            )
            return

        body = {"agent": agent_name, "params": params_body}

        try:
            resp = requests.post(
                NIMBLE_AGENTS_RUN_URL,
                json=body,
                headers=headers,
                timeout=120,
            )
        except requests.RequestException as e:
            yield (None, "request_error", None, None, None, None, {"error": str(e)})
            return

        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except ValueError:
                err_body = {"text": resp.text}
            yield (
                None,
                f"http_{resp.status_code}",
                resp.status_code,
                None,
                None,
                None,
                err_body,
            )
            return

        data = resp.json()
        agent_data = data.get("data") or {}
        # data.parsing is the typed payload — a dict for PDP-style agents
        # (the product itself), a list for SERP-style agents (an array of
        # products). Pass it through to the VARIANT column as-is and let
        # callers project / FLATTEN per their use case.
        parsing_out = agent_data.get("parsing")

        yield (
            data.get("task_id"),
            data.get("status"),
            data.get("status_code"),
            data.get("url"),
            parsing_out,
            data.get("warnings"),
            data,
        )
$$;

GRANT USAGE ON FUNCTION NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(STRING, OBJECT)
    TO ROLE NIMBLE_ROLE;

-- Smoke tests (uncomment to verify after deploy). Two flavours, one each for
-- the two response shapes the UDTF supports:
--
--   1. PDP-style agent — single product object in parsing. The UDTF
--      yields one row; `parsing` is the typed product blob.
--
-- SELECT parsing:product_title::STRING AS title,
--        parsing:web_price::NUMBER    AS price,
--        parsing:availability::BOOLEAN AS in_stock
-- FROM   TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
--            'amazon_pdp',
--            OBJECT_CONSTRUCT('asin', 'B09B8V1LZ3')   -- Amazon US Echo Dot, stable public listing
--        ));
--
--   2. SERP-style agent — `parsing` is an array of product objects. The
--      UDTF yields one row; pair with LATERAL FLATTEN to explode the array
--      into one Snowflake row per product (the pattern used by the
--      amazon_keyword_research recipe).
--
-- SELECT p.value:position::INTEGER       AS position,
--        p.value:asin::STRING            AS asin,
--        p.value:product_name::STRING    AS title,
--        p.value:price::NUMBER(10, 2)    AS price,
--        p.value:currency::STRING        AS currency,
--        p.value:rating::NUMBER(3, 2)    AS rating
-- FROM   TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
--            'amazon_serp',
--            OBJECT_CONSTRUCT('keyword', 'noise canceling headphones')
--        )) a,
--        LATERAL FLATTEN(INPUT => a.parsing) p
-- WHERE  a.status = 'success'
-- ORDER  BY position
-- LIMIT  10;
--
-- Tip: to discover an agent's exact field names without trial-and-error, run:
--   SELECT OBJECT_KEYS(parsing[0]) AS product_fields
--   FROM   TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN('amazon_serp',
--              OBJECT_CONSTRUCT('keyword', 'noise canceling headphones')));
