-- Basic nimble_agent_describe patterns. Prereqs:
--   ../01_setup.sql
--   ../tools/nimble_agent_describe.sql
--   ../tools/nimble_agent_describe_table.sql

-- 1. Simplest TABLE-form call — one row of agent metadata.
SELECT name, display_name, vertical, entity_type, domain
FROM nimble_integration.tools.nimble_agent_describe_table('amazon_serp');


-- 2. List the input params an agent accepts: name, required, type, default.
--    Use this before calling nimble_agent_run for an unfamiliar agent.
WITH d AS (
    SELECT nimble_integration.tools.nimble_agent_describe('amazon_serp') AS r
)
SELECT
    p.name,
    p.required,
    p.type,
    p.`default`,
    p.description,
    p.examples
FROM d
LATERAL VIEW EXPLODE(r.input_properties) t AS p
ORDER BY p.required DESC, p.name;


-- 3. Check capability flags before building a paginated / localized call.
SELECT name, is_localization_supported, is_pagination_supported
FROM nimble_integration.tools.nimble_agent_describe_table('amazon_serp');


-- 4. Discover the output_schema for an agent. The shape is per-agent —
--    parse with from_json + an agent-specific schema string for typing.
SELECT output_schema_json
FROM nimble_integration.tools.nimble_agent_describe_table('amazon_serp');
