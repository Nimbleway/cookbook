/*
 * tools/nimble_agent_run_table.sql — Genie-friendly TABLE wrapper around
 * nimble_agent_run.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_run_table(agent, params_json, localization)
 *             RETURNS TABLE(...)
 * Prereq:     01_setup.sql and tools/nimble_agent_run.sql have run successfully.
 * Runtime:    ~5 seconds to create; ~5-30s per call.
 *
 * Why a separate TABLE wrapper?
 *   Databricks Genie can only register tools that are TABLE functions
 *   (`RETURNS TABLE(...)`). The scalar nimble_agent_run() returns a
 *   single STRUCT, which Genie won't pick up. This wrapper exposes
 *   the same data as a one-row table so Genie / Mosaic-AI agents can
 *   call it.
 *
 *   Direct SQL callers can pick either:
 *     SELECT * FROM nimble_integration.tools.nimble_agent_run_table('amazon_serp', '{"keyword":"cookies","page":1}');
 *     -- vs --
 *     SELECT nimble_integration.tools.nimble_agent_run('amazon_serp', '{"keyword":"cookies","page":1}').parsing_json;
 *
 * The COMMENT is intentionally long and example-rich: Genie reads it
 * verbatim to decide when to call this function.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_run_table(
    agent        STRING
        COMMENT 'Agent name (e.g. "amazon_serp", "linkedin_company_details"). Discover names via nimble_agent_list_table().',
    params_json  STRING
        COMMENT 'Raw JSON object of agent-specific params, e.g. ''{"keyword":"wireless headphones","page":1}''. See the per-agent input schema at GET /v1/agents/{name}.',
    localization BOOLEAN DEFAULT FALSE
        COMMENT 'Optional. TRUE enables zip_code / store_id-based localization for agents that support it. Default FALSE.'
)
RETURNS TABLE(
    status            STRING  COMMENT 'Overall extraction status: "success" or "failed"',
    status_code       INT     COMMENT 'HTTP status returned by the target website (200, 404, ...)',
    task_id           STRING  COMMENT 'Unique extraction task UUID for tracing / support',
    url               STRING  COMMENT 'Final URL the agent extracted from',
    parsing_json      STRING  COMMENT 'Parsed payload as a raw JSON STRING. Shape is agent-specific — caller should from_json() it with the per-agent schema. NULL when agent has no parsing output.',
    query_time        STRING  COMMENT 'ISO-8601 timestamp when the extraction ran',
    driver            STRING  COMMENT 'Underlying extraction driver used (e.g. "vx8")',
    query_duration_ms INT     COMMENT 'Wall-clock duration of the extraction in milliseconds',
    warnings          ARRAY<STRING> COMMENT 'Warnings emitted during extraction (empty array if none)'
)
COMMENT 'Generic Nimble agent runner: executes any Nimble agent by name and returns the response envelope plus the parsed payload as raw JSON.
Use this function when the user wants to call an agent for which there is NO typed wrapper (e.g. anything outside amazon_serp / nimble_search). For agents with a typed wrapper, prefer the typed wrapper since it returns proper SQL types instead of JSON strings.
The `parsing_json` column holds whatever the agent extracted — shape depends on the agent and must be parsed by the caller with from_json(). Discover agent names + their input schemas via nimble_agent_list_table().
Example questions this answers:
"Run the linkedin_company_details agent for nimbleway and return the raw JSON.",
"Call the homedepot_pdp agent for this product URL.",
"Execute agent X with these params and show me the parsed output."'
RETURN (
    SELECT result.*
    FROM (
        SELECT nimble_integration.tools.nimble_agent_run(agent, params_json, localization) AS result
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT status, status_code, length(parsing_json) AS parsing_len
-- FROM nimble_integration.tools.nimble_agent_run_table('amazon_serp', '{"keyword":"cookies","page":1}');
