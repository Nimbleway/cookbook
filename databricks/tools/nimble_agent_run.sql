/*
 * tools/nimble_agent_run.sql — wraps Nimble's POST /v1/agents/run endpoint
 * as a generic UC SQL function. Runs ANY Nimble agent by name with caller-
 * supplied JSON params.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools, plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_run(agent, params_json, localization)
 *             RETURNS STRUCT<...>
 * Prereq:     01_setup.sql has run successfully.
 * Runtime:    ~5 seconds to create; ~5-30s per call (depends on agent + target site).
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/agent-run
 *             (append `.md` to the URL for the plain-text spec)
 *
 * When to use this vs. a typed wrapper (amazon_serp, etc.):
 *   - Typed wrappers (e.g. nimble_integration.tools.amazon_serp) project
 *     the parsed output into a strict ARRAY<STRUCT<...>> with proper SQL
 *     types — best for Genie + dashboards.
 *   - This generic runner exposes EVERY agent (incl. ones we have no
 *     dedicated wrapper for) but returns the parsed structure as a raw
 *     JSON STRING (`parsing_json`). Caller must from_json() it with an
 *     agent-specific schema.
 *
 * Notes on parameters:
 *   - agent:        agent name from `nimble_agent_list`, e.g. "amazon_serp".
 *   - params_json:  raw JSON object of agent-specific params, e.g.
 *                   '{"keyword":"cookies","page":1}'. Must be a valid JSON
 *                   object literal. The endpoint requires at least one
 *                   agent-specific key-value pair.
 *   - localization: optional; default FALSE. When TRUE, agents that
 *                   support zip_code / store_id localize requests.
 *
 * The endpoint's `formats` array (html/markdown/headers/links) is
 * intentionally not exposed here — those output modes change the response
 * shape considerably and are better suited to a dedicated wrapper.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_run(
    agent        STRING
        COMMENT 'Agent name to execute (e.g. "amazon_serp", "linkedin_company_details"). See nimble_agent_list_table() for the full catalog.',
    params_json  STRING
        COMMENT 'Raw JSON object of agent-specific params, e.g. ''{"keyword":"wireless headphones","page":1}''. Schema is per-agent; see GET /v1/agents/{name} for each agent''s input_properties.',
    localization BOOLEAN DEFAULT FALSE
        COMMENT 'Optional. When TRUE, agents that support it localize via zip_code / store_id. Default FALSE.'
)
RETURNS STRUCT<
    status:            STRING,
    status_code:       INT,
    task_id:           STRING,
    url:               STRING,
    parsing_json:      STRING,
    query_time:        STRING,
    driver:            STRING,
    query_duration_ms: INT,
    warnings:          ARRAY<STRING>
>
COMMENT 'Generic Nimble agent runner. Executes any Nimble agent realtime via POST /v1/agents/run and returns the response envelope plus the parsed payload as a raw JSON STRING (`parsing_json`). Use this when there is no typed wrapper for the agent you need. For agents WITH a typed wrapper (e.g. amazon_serp), prefer the typed wrapper for proper SQL types.'
RETURN (
    /*
     * The response envelope is fixed across agents, but `data.parsing`
     * has a per-agent shape (object). We extract via `get_json_object`
     * to keep `parsing` as a raw JSON STRING the caller can from_json
     * with the right per-agent schema. `try_cast` guards the numeric
     * envelope fields (they come through as JSON strings under spark's
     * get_json_object).
     *
     * Note: `status_code` here is the HTTP status the TARGET site
     * returned (per the Nimble response envelope), not the Nimble API
     * status — that's `response.status_code` from http_request itself,
     * which we gate on below to surface Nimble-side 4xx/5xx as real
     * query errors.
     */
    SELECT CASE
        WHEN response.status_code BETWEEN 200 AND 299 THEN
            named_struct(
                'status',            get_json_object(response.text, '$.status'),
                'status_code',       try_cast(get_json_object(response.text, '$.status_code')           AS INT),
                'task_id',           get_json_object(response.text, '$.task_id'),
                'url',               get_json_object(response.text, '$.url'),
                'parsing_json',      get_json_object(response.text, '$.data.parsing'),
                'query_time',        get_json_object(response.text, '$.metadata.query_time'),
                'driver',            get_json_object(response.text, '$.metadata.driver'),
                'query_duration_ms', try_cast(get_json_object(response.text, '$.metadata.query_duration') AS INT),
                'warnings',          from_json(coalesce(get_json_object(response.text, '$.warnings'), '[]'), 'ARRAY<STRING>')
            )
        ELSE raise_error(concat(
            'Nimble /v1/agents/run failed with status ',
            cast(response.status_code AS STRING), ': ', response.text
        ))
    END
    FROM (
        SELECT http_request(
            conn    => 'nimble_api',
            method  => 'POST',
            path    => '/v1/agents/run',
            headers => map(
                'Content-Type',    'application/json',
                'X-Client-Source', 'nimble-dbx-udf'
            ),
            /*
             * Build the body via named_struct + parse_json so VARIANT
             * carries `params` as actual JSON (different agents have
             * different params schemas, so we cannot statically type
             * it). to_json handles all string escaping for `agent` and
             * the boolean serialization for `localization`.
             */
            json    => to_json(named_struct(
                'agent',        agent,
                'localization', localization,
                'params',       parse_json(params_json)
            ))
        ) AS response
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT nimble_integration.tools.nimble_agent_run('amazon_serp', '{"keyword":"cookies","page":1}').status AS status;
