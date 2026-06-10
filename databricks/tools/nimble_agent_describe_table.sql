/*
 * tools/nimble_agent_describe_table.sql — Genie-friendly TABLE wrapper
 * around nimble_agent_describe.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_describe_table(agent)
 *             RETURNS TABLE(...)
 * Prereq:     01_setup.sql and tools/nimble_agent_describe.sql have run successfully.
 * Runtime:    ~5 seconds to create; ~1-2s per call.
 *
 * Why a separate TABLE wrapper?
 *   Databricks Genie can only register tools that are TABLE functions
 *   (`RETURNS TABLE(...)`). The scalar nimble_agent_describe() returns
 *   a single STRUCT, which Genie won't pick up. This wrapper exposes
 *   the same data as a one-row table.
 *
 *   Direct SQL callers can pick either:
 *     SELECT * FROM nimble_integration.tools.nimble_agent_describe_table('amazon_serp');
 *     -- vs --
 *     SELECT nimble_integration.tools.nimble_agent_describe('amazon_serp').input_properties;
 *
 * The COMMENT is intentionally long and example-rich: Genie reads it
 * verbatim to decide when to call this function.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_describe_table(
    agent STRING
        COMMENT 'Agent name (e.g. "amazon_serp", "linkedin_company_details"). Discover names via nimble_agent_list_table().'
)
RETURNS TABLE(
    name                      STRING  COMMENT 'Agent identifier (matches the input)',
    display_name              STRING  COMMENT 'Human-readable agent name',
    description               STRING  COMMENT 'Agent description; NULL if not provided',
    vertical                  STRING  COMMENT 'Industry vertical (e.g. "Ecommerce", "News & Media")',
    entity_type               STRING  COMMENT 'Data entity extracted (e.g. "Product Detail Page", "Article")',
    domain                    STRING  COMMENT 'Target site / domain (e.g. "amazon.com")',
    managed_by                STRING  COMMENT 'Who manages the agent: nimble | community | self_managed',
    is_public                 BOOLEAN COMMENT 'TRUE if publicly visible',
    is_localization_supported BOOLEAN COMMENT 'TRUE if the agent accepts zip_code / store_id-style localization params',
    is_pagination_supported   BOOLEAN COMMENT 'TRUE if the agent supports a page / pagination param',
    input_properties ARRAY<STRUCT<
        name:                  STRING,
        required:              BOOLEAN,
        type:                  STRING,
        description:           STRING,
        is_localization_param: BOOLEAN,
        is_pagination_param:   BOOLEAN,
        `default`:             STRING,
        examples:              ARRAY<STRING>
    >> COMMENT 'Input params the agent accepts: name, required flag, JSON type, description, default, examples',
    output_schema_json        STRING  COMMENT 'Output schema as a raw JSON STRING. Shape is per-agent — caller can from_json() it for typed projection.'
)
COMMENT 'Returns the input + output schema for a single Nimble agent. Use this BEFORE calling nimble_agent_run for an unfamiliar agent so you know which params to pass (input_properties) and which fields will come back (output_schema_json). Pairs naturally with nimble_agent_list_table() — list to discover the catalog, describe to learn one agent''s signature.
Example questions this answers:
"What params does the amazon_pdp agent take?",
"What does the linkedin_company_details agent return?",
"Show me the schema for the homedepot_serp agent.",
"Does agent X support pagination or localization?".'
RETURN (
    SELECT result.*
    FROM (
        SELECT nimble_integration.tools.nimble_agent_describe(agent) AS result
    )
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT name, vertical, size(input_properties) AS n_inputs
-- FROM nimble_integration.tools.nimble_agent_describe_table('amazon_serp');
