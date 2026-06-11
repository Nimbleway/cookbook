/*
 * tools/nimble_agent_run.sql — wraps Nimble's POST /v1/agents/run endpoint as a
 * generic UC table function. Runs ANY Nimble agent by name with caller-supplied
 * JSON params.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema; READ on secret('nimble','api_key').
 * Creates:    nimble_integration.tools._nimble_agent_run(...) RETURNS TABLE  (Python UDTF)
 *             nimble_integration.tools.nimble_agent_run(...)   RETURNS TABLE  (public wrapper)
 * Prereq:     01_setup.sql has run; the `nimble` secret scope + `api_key` exist;
 *             the workspace Preview "Enable networking for isolated workloads in
 *             Serverless SQL Warehouses" is ON and the warehouse was cold-restarted.
 * Runtime:    ~5 seconds to create; ~5-30s per call (depends on agent + target site).
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/agent-run
 *             (append `.md` to the URL for the plain-text spec)
 *
 * Design (UDTF-only):
 *   Databricks Genie registers TABLE functions as tools, so every capability
 *   ships as a table function — no scalar / `_table` twin to maintain.
 *     - _nimble_agent_run : LANGUAGE PYTHON UDTF. eval() POSTs to /v1/agents/run
 *                           and yields a single row: the response envelope plus
 *                           the parsed payload as a raw JSON STRING (parsing_json).
 *                           `import`s live INSIDE eval(). Yields zero rows on error.
 *     - nimble_agent_run  : thin SQL RETURNS TABLE wrapper that supplies DEFAULTs
 *                           and injects the API key via secret().
 *
 * Generic runner: exposes every agent, returning the per-agent payload as a raw
 * JSON STRING (`parsing_json`) the caller can parse with from_json/parse_json
 * against an agent-specific schema. For agents with a typed table function,
 * prefer that one for proper SQL types.
 *
 * Notes on parameters:
 *   - agent:        agent name from nimble_agent_list, e.g. "amazon_serp".
 *   - params_json:  raw JSON object of agent-specific params, e.g.
 *                   '{"keyword":"cookies","page":1}'. Must be a valid JSON object.
 *   - localization: optional; default FALSE. When TRUE, agents that support it
 *                   localize via zip_code / store_id.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools._nimble_agent_run(
    agent        STRING,
    params_json  STRING,
    localization BOOLEAN,
    api_key      STRING
)
RETURNS TABLE(
    status            STRING,
    status_code       INT,
    task_id           STRING,
    url               STRING,
    parsing_json      STRING,
    query_time        STRING,
    driver            STRING,
    query_duration_ms INT,
    warnings          STRING
)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind nimble_agent_run(). Call the public nimble_agent_run() wrapper instead.'
AS $$
class Handler:
    def eval(self, agent, params_json, localization, api_key):
        import json
        import requests

        def as_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        try:
            params = json.loads(params_json) if params_json else {}
        except (TypeError, ValueError):
            params = {}

        body = {"agent": agent, "localization": localization, "params": params}
        headers = {
            "Authorization": "Bearer " + (api_key or ""),
            "Content-Type": "application/json",
            "X-Client-Source": "nimble-dbx-udtf",
        }
        try:
            resp = requests.post("https://sdk.nimbleway.com/v1/agents/run", json=body, headers=headers, timeout=120)
            d = resp.json() if 200 <= resp.status_code < 300 else {}
        except Exception:
            d = {}
        if not d:
            return

        data = d.get("data") or {}
        meta = d.get("metadata") or {}
        parsing = data.get("parsing")
        if parsing is not None and not isinstance(parsing, str):
            parsing = json.dumps(parsing)

        yield (
            d.get("status"),
            as_int(d.get("status_code")),
            d.get("task_id"),
            d.get("url"),
            parsing,
            meta.get("query_time"),
            meta.get("driver"),
            as_int(meta.get("query_duration")),
            json.dumps(d.get("warnings") or []),
        )
$$;

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_run(
    agent        STRING
        COMMENT 'Agent name to execute (e.g. "amazon_serp", "linkedin_company_details"). See nimble_agent_list() for the full catalog.',
    params_json  STRING
        COMMENT 'Raw JSON object of agent-specific params, e.g. ''{"keyword":"wireless headphones","page":1}''. Schema is per-agent; see GET /v1/agents/{name} for each agent''s input_properties.',
    localization BOOLEAN DEFAULT FALSE
        COMMENT 'Optional. When TRUE, agents that support it localize via zip_code / store_id. Default FALSE.'
)
RETURNS TABLE(
    status            STRING  COMMENT 'Nimble task status, e.g. "success".',
    status_code       INT     COMMENT 'HTTP status the TARGET site returned (per the Nimble envelope), not the Nimble API status.',
    task_id           STRING  COMMENT 'Nimble task id for the run.',
    url               STRING  COMMENT 'The resolved target URL the agent fetched.',
    parsing           VARIANT COMMENT 'The parsed, per-agent payload as VARIANT. Navigate inline (e.g. parsing:entities:SearchResult) and explode arrays with LATERAL variant_explode(...); cast leaf values with ::type.',
    query_time        STRING  COMMENT 'Server-reported query timestamp.',
    driver            STRING  COMMENT 'Fetch driver used.',
    query_duration_ms INT     COMMENT 'Query duration in milliseconds.',
    warnings          STRING  COMMENT 'JSON array of warnings, if any.'
)
COMMENT 'Generic Nimble agent runner: executes any Nimble agent realtime via POST /v1/agents/run and returns one row — the response envelope plus the parsed payload as VARIANT (parsing). Navigate parsing with `:` paths and explode its arrays with LATERAL variant_explode(...). Use when there is no typed table function for the agent you need. Returns zero rows on failure rather than raising.'
RETURN SELECT
    status, status_code, task_id, url,
    parse_json(parsing_json) AS parsing,
    query_time, driver, query_duration_ms, warnings
FROM nimble_integration.tools._nimble_agent_run(
    agent, params_json, localization, secret('nimble', 'api_key')
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT status, parsing:entities AS entities FROM nimble_integration.tools.nimble_agent_run('amazon_serp', '{"keyword":"cookies","page":1}');
