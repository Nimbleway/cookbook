/*
 * tools/nimble_agent_describe.sql — wraps Nimble's GET /v1/agents/{name}
 * endpoint as a UC SQL function. Returns the input / output schema for
 * one Nimble agent so callers know what params to send and what fields
 * to expect back.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools, plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_describe(agent)
 *             RETURNS STRUCT<...>
 * Prereq:     01_setup.sql has run successfully.
 * Runtime:    ~5 seconds to create; ~1-2s per call.
 *
 * API docs:   https://docs.nimbleway.com/api-reference/agents/get-agent-details
 *             (append `.md` to the URL for the plain-text spec)
 *
 * Typical use:
 *   - Before calling nimble_agent_run for an unfamiliar agent, call this
 *     to discover the agent's required + optional params and their types.
 *   - For programmatic / Genie use, the structured `input_properties`
 *     array is enough; for full output payload typing, callers can
 *     from_json the `output_schema_json` STRING.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_describe(
    agent STRING
        COMMENT 'Agent name to describe, e.g. "amazon_serp". Discover names via nimble_agent_list_table().'
)
RETURNS STRUCT<
    name:                      STRING,
    display_name:              STRING,
    description:               STRING,
    vertical:                  STRING,
    entity_type:               STRING,
    domain:                    STRING,
    managed_by:                STRING,
    is_public:                 BOOLEAN,
    is_localization_supported: BOOLEAN,
    is_pagination_supported:   BOOLEAN,
    input_properties: ARRAY<STRUCT<
        name:                  STRING,
        required:              BOOLEAN,
        type:                  STRING,
        description:           STRING,
        is_localization_param: BOOLEAN,
        is_pagination_param:   BOOLEAN,
        `default`:             STRING,
        examples:              ARRAY<STRING>
    >>,
    output_schema_json: STRING
>
COMMENT 'Returns the input schema (required + optional params, types, examples) and the output_schema for one Nimble agent. Call this before nimble_agent_run when you do not know what params an agent expects or what fields it returns.'
RETURN (
    /*
     * Parse the envelope with `from_json` for typed fields, and use
     * `get_json_object` to extract `output_schema` as a raw JSON string
     * (its shape is per-agent, so we cannot statically type it).
     *
     * Numeric / boolean fields come back as native JSON types from this
     * endpoint, but we parse via the all-STRING + try_cast pattern in
     * input_properties — Nimble agents historically ship those fields
     * as strings.
     */
    SELECT named_struct(
        'name',                      env.name,
        'display_name',              env.display_name,
        'description',               env.description,
        'vertical',                  env.vertical,
        'entity_type',               env.entity_type,
        'domain',                    env.domain,
        'managed_by',                env.managed_by,
        'is_public',                 try_cast(env.is_public AS BOOLEAN),
        'is_localization_supported', try_cast(env.feature_flags.is_localization_supported AS BOOLEAN),
        'is_pagination_supported',   try_cast(env.feature_flags.is_pagination_supported   AS BOOLEAN),
        'input_properties', coalesce(
            transform(
                env.input_properties,
                p -> named_struct(
                    'name',                  p.name,
                    'required',              try_cast(p.required AS BOOLEAN),
                    'type',                  p.type,
                    'description',           p.description,
                    'is_localization_param', try_cast(p.is_localization_param AS BOOLEAN),
                    'is_pagination_param',   try_cast(p.is_pagination_param   AS BOOLEAN),
                    'default',               p.`default`,
                    'examples',              p.examples
                )
            ),
            ARRAY()
        ),
        'output_schema_json', get_json_object(raw_text, '$.output_schema')
    )
    FROM (
        SELECT
            response.text AS raw_text,
            from_json(
                response.text,
                'STRUCT<
                    name STRING,
                    is_public STRING,
                    display_name STRING,
                    description STRING,
                    vertical STRING,
                    entity_type STRING,
                    domain STRING,
                    managed_by STRING,
                    feature_flags STRUCT<
                        is_localization_supported STRING,
                        is_pagination_supported   STRING
                    >,
                    input_properties ARRAY<STRUCT<
                        name STRING,
                        required STRING,
                        type STRING,
                        description STRING,
                        is_localization_param STRING,
                        is_pagination_param STRING,
                        `default` STRING,
                        examples ARRAY<STRING>
                    >>
                >'
            ) AS env
        FROM (
            SELECT http_request(
                conn    => 'nimble_api',
                method  => 'GET',
                path    => concat('/v1/agents/', agent),
                headers => map(
                    'Content-Type',    'application/json',
                    'X-Client-Source', 'nimble-dbx-udf'
                )
            ) AS response
        )
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT nimble_integration.tools.nimble_agent_describe('amazon_serp').name AS name;
