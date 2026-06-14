/*
 * tools/nimble_agent_describe.sql — wraps Nimble's GET /v1/agents/{agent_name}
 * endpoint as a UC table function. Returns one row per INPUT PROPERTY of a
 * single agent — the exact param names, types, and required/localization/
 * pagination flags you need to build a valid nimble_agent_run params_json.
 *
 * Why this exists: nimble_agent_list() tells you which agents exist, but not
 * how to call them. Param names differ across agents (Amazon search wants
 * `keyword`, not `query`) and localization is per-agent — so discover inputs at
 * runtime, never hardcode. Output FIELDS are intentionally NOT returned here
 * (they are large and best discovered from a real call): run the agent once and
 * inspect `to_json(parsing[0])` to see the emitted fields.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema; READ on secret('nimble','api_key').
 * Creates:    nimble_integration.tools._nimble_agent_describe(...) RETURNS TABLE  (Python UDTF)
 *             nimble_integration.tools.nimble_agent_describe(...)   RETURNS TABLE  (public wrapper)
 * Prereq:     01_setup.sql has run; the `nimble` secret scope + `api_key` exist;
 *             the workspace Preview "Enable networking for isolated workloads in
 *             Serverless SQL Warehouses" is ON and the warehouse was cold-restarted.
 * Runtime:    ~5 seconds to create; ~1-3s per call.
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/get-agent-details
 *             (append `.md` to the URL for the plain-text spec)
 *
 * Design (UDTF-only):
 *   Databricks Genie registers TABLE functions as tools, so every capability
 *   ships as a table function — no scalar / `_table` twin to maintain.
 *     - _nimble_agent_describe : LANGUAGE PYTHON UDTF. eval() does requests.get
 *                                and yields one row per input property, with the
 *                                agent-level vertical/entity_type/domain and the
 *                                localization/pagination feature flags repeated on
 *                                each row. `import`s live INSIDE eval(). Yields
 *                                zero rows on error (or for an unknown agent).
 *     - nimble_agent_describe  : thin SQL RETURNS TABLE wrapper that injects the
 *                                API key via secret().
 *
 * Notes on parameters:
 *   - agent_name: the agent name from nimble_agent_list, e.g. "amazon_serp".
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools._nimble_agent_describe(
    agent_name STRING,
    api_key    STRING
)
RETURNS TABLE(
    agent_name               STRING,
    param_name               STRING,
    required                 BOOLEAN,
    type                     STRING,
    description              STRING,
    is_localization_param    BOOLEAN,
    is_pagination_param      BOOLEAN,
    default_value            STRING,
    examples_json            STRING,
    vertical                 STRING,
    entity_type              STRING,
    domain                   STRING,
    is_localization_supported BOOLEAN,
    is_pagination_supported   BOOLEAN
)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind nimble_agent_describe(). Call the public nimble_agent_describe() wrapper instead.'
AS $$
class Handler:
    def eval(self, agent_name, api_key):
        import json
        import requests

        def as_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() == "true"
            return None

        if not agent_name:
            return

        headers = {
            "Authorization": "Bearer " + (api_key or ""),
            "Content-Type": "application/json",
            "X-Client-Source": "nimble-dbx-udtf",
        }
        try:
            resp = requests.get(
                "https://sdk.nimbleway.com/v1/agents/" + agent_name,
                headers=headers,
                timeout=30,
            )
            data = resp.json() if 200 <= resp.status_code < 300 else {}
        except Exception:
            data = {}

        if not isinstance(data, dict) or not data:
            return

        vertical = data.get("vertical")
        entity_type = data.get("entity_type")
        domain = data.get("domain")
        flags = data.get("feature_flags") or {}
        loc_supported = as_bool(flags.get("is_localization_supported"))
        pag_supported = as_bool(flags.get("is_pagination_supported"))

        props = data.get("input_properties") or []
        for p in props:
            if not isinstance(p, dict):
                continue
            examples = p.get("examples")
            examples_json = json.dumps(examples) if examples is not None else None
            default_val = p.get("default")
            default_value = None if default_val is None else str(default_val)
            yield (
                agent_name,
                p.get("name"),
                as_bool(p.get("required")),
                p.get("type"),
                p.get("description"),
                as_bool(p.get("is_localization_param")),
                as_bool(p.get("is_pagination_param")),
                default_value,
                examples_json,
                vertical,
                entity_type,
                domain,
                loc_supported,
                pag_supported,
            )
$$;

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_describe(
    agent_name STRING
        COMMENT 'Agent name from nimble_agent_list, e.g. "amazon_serp". Required.'
)
RETURNS TABLE(
    agent_name                STRING  COMMENT 'The agent that was described.',
    param_name                STRING  COMMENT 'Input parameter name to put in nimble_agent_run params_json, e.g. "keyword".',
    required                  BOOLEAN COMMENT 'Whether this parameter is required.',
    type                      STRING  COMMENT 'Parameter type, e.g. string, integer.',
    description               STRING  COMMENT 'What the parameter does.',
    is_localization_param     BOOLEAN COMMENT 'TRUE if this param localizes results (e.g. zip_code); set localization=TRUE on nimble_agent_run to use it.',
    is_pagination_param       BOOLEAN COMMENT 'TRUE if this param paginates results (e.g. page).',
    default_value             STRING  COMMENT 'Default value for the parameter, if any (as a string).',
    examples_json             STRING  COMMENT 'Example values as a JSON array string, if provided.',
    vertical                  STRING  COMMENT 'Agent vertical / category, e.g. Ecommerce. Repeated on every row.',
    entity_type               STRING  COMMENT 'Entity the agent targets, e.g. Product Detail Page (PDP). Repeated on every row.',
    domain                    STRING  COMMENT 'Primary target domain, e.g. www.amazon.com. Repeated on every row.',
    is_localization_supported BOOLEAN COMMENT 'Whether the agent supports localization at all. Repeated on every row.',
    is_pagination_supported   BOOLEAN COMMENT 'Whether the agent supports pagination at all. Repeated on every row.'
)
COMMENT 'Describes a single Nimble agent: one row per INPUT property (param_name, required, type, localization/pagination flags, default, examples), with the agent vertical/entity_type/domain and feature flags repeated on each row. Use to learn the exact params to pass to nimble_agent_run before calling it (param names and localization differ per agent). Does NOT return output fields — discover those by running the agent once and inspecting to_json(parsing[0]). Returns zero rows on failure or unknown agent rather than raising.'
RETURN SELECT * FROM nimble_integration.tools._nimble_agent_describe(
    agent_name, secret('nimble', 'api_key')
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT param_name, required, type, is_localization_param
-- FROM nimble_integration.tools.nimble_agent_describe('amazon_pdp');
-- Expect: asin (required, string) and zip_code (is_localization_param = true).
