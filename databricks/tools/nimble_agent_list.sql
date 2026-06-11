/*
 * tools/nimble_agent_list.sql — wraps Nimble's GET /v1/agents listing endpoint
 * as a UC table function. Returns the catalog of agents available to the
 * caller's API key, filtered by `managed_by` / `privacy`.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema; READ on secret('nimble','api_key').
 * Creates:    nimble_integration.tools._nimble_agent_list(...) RETURNS TABLE  (Python UDTF)
 *             nimble_integration.tools.nimble_agent_list(...)   RETURNS TABLE  (public wrapper)
 * Prereq:     01_setup.sql has run; the `nimble` secret scope + `api_key` exist;
 *             the workspace Preview "Enable networking for isolated workloads in
 *             Serverless SQL Warehouses" is ON and the warehouse was cold-restarted.
 * Runtime:    ~5 seconds to create; ~1-3s per call.
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/list-agents
 *             (append `.md` to the URL for the plain-text spec)
 *
 * Design (UDTF-only):
 *   Databricks Genie registers TABLE functions as tools, so every capability
 *   ships as a table function — no scalar / `_table` twin to maintain.
 *     - _nimble_agent_list : LANGUAGE PYTHON UDTF. eval() does requests.get and
 *                            yields one row per agent. `import`s live INSIDE
 *                            eval(). Yields zero rows on error.
 *     - nimble_agent_list  : thin SQL RETURNS TABLE wrapper that supplies
 *                            DEFAULTs and injects the API key via secret().
 *
 * Notes on parameters:
 *   - privacy:     public | private | all. Default `public`.
 *   - managed_by:  nimble | community | self_managed. Default `nimble` (the
 *                  typical "what agents can I call?" question). NULL disables
 *                  the filter.
 *   - max_results: 1..250, default 250 (API max).
 *   - page_offset: pagination offset, default 0.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools._nimble_agent_list(
    privacy     STRING,
    managed_by  STRING,
    max_results INT,
    page_offset INT,
    api_key     STRING
)
RETURNS TABLE(
    name         STRING,
    display_name STRING,
    description  STRING,
    vertical     STRING,
    entity_type  STRING,
    domain       STRING,
    managed_by   STRING,
    is_public    BOOLEAN
)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind nimble_agent_list(). Call the public nimble_agent_list() wrapper instead.'
AS $$
class Handler:
    def eval(self, privacy, managed_by, max_results, page_offset, api_key):
        import requests

        def as_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() == "true"
            return None

        params = {
            "privacy": privacy,
            "managed_by": managed_by,
            "limit": max_results,
            "offset": page_offset,
        }
        params = {k: v for k, v in params.items() if v is not None}
        headers = {
            "Authorization": "Bearer " + (api_key or ""),
            "Content-Type": "application/json",
            "X-Client-Source": "nimble-dbx-udtf",
        }
        try:
            resp = requests.get("https://sdk.nimbleway.com/v1/agents", params=params, headers=headers, timeout=30)
            data = resp.json() if 200 <= resp.status_code < 300 else []
        except Exception:
            data = []
        for a in (data or []):
            yield (
                a.get("name"),
                a.get("display_name"),
                a.get("description"),
                a.get("vertical"),
                a.get("entity_type"),
                a.get("domain"),
                a.get("managed_by"),
                as_bool(a.get("is_public")),
            )
$$;

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_list(
    privacy     STRING DEFAULT 'public'
        COMMENT 'Privacy filter: public | private | all. Default `public`.',
    managed_by  STRING DEFAULT 'nimble'
        COMMENT 'Filter by who manages the agent: nimble | community | self_managed. Default `nimble`. NULL = no filter.',
    max_results INT    DEFAULT 250
        COMMENT 'Results per page (1-250). Default 250 (API max).',
    page_offset INT    DEFAULT 0
        COMMENT 'Pagination offset (>=0). Default 0.'
)
RETURNS TABLE(
    name         STRING  COMMENT 'Agent name to pass to nimble_agent_run, e.g. "amazon_serp".',
    display_name STRING  COMMENT 'Human-readable agent name.',
    description  STRING  COMMENT 'What the agent does.',
    vertical     STRING  COMMENT 'Vertical / category, e.g. ecommerce, social.',
    entity_type  STRING  COMMENT 'Entity the agent targets, e.g. product, profile.',
    domain       STRING  COMMENT 'Primary target domain, e.g. amazon.com.',
    managed_by   STRING  COMMENT 'Who manages the agent: nimble | community | self_managed.',
    is_public    BOOLEAN COMMENT 'Whether the agent is publicly available.'
)
COMMENT 'Lists the Nimble agents available to the caller, one row per agent (name, display_name, description, vertical, entity_type, domain, managed_by, is_public). Use to discover which `agent` names can be passed to nimble_agent_run, or to enumerate the catalog for a Genie space. Returns zero rows on failure rather than raising.'
RETURN SELECT * FROM nimble_integration.tools._nimble_agent_list(
    privacy, managed_by, max_results, page_offset, secret('nimble', 'api_key')
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT count(*) AS n FROM nimble_integration.tools.nimble_agent_list();
