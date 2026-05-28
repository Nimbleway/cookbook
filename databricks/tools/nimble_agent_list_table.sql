/*
 * tools/nimble_agent_list_table.sql — Genie-friendly TABLE wrapper around
 * nimble_agent_list.
 *
 * Privileges: USE on nimble_integration + nimble_integration.tools; plus
 *             CREATE FUNCTION on the schema.
 * Creates:    nimble_integration.tools.nimble_agent_list_table(privacy, managed_by, max_results, page_offset)
 *             RETURNS TABLE(...)
 * Prereq:     01_setup.sql and tools/nimble_agent_list.sql have run successfully.
 * Runtime:    ~5 seconds to create; ~1-3s per call.
 *
 * Why a separate TABLE wrapper?
 *   Databricks Genie can only register tools that are TABLE functions
 *   (`RETURNS TABLE(...)`). The scalar nimble_agent_list() returns
 *   ARRAY<STRUCT<...>>, which Genie won't pick up. This wrapper exposes
 *   the same data row-by-row.
 *
 *   Direct SQL callers can pick either:
 *     SELECT * FROM nimble_integration.tools.nimble_agent_list_table();
 *     -- vs --
 *     WITH r AS (SELECT nimble_integration.tools.nimble_agent_list() AS items)
 *     SELECT item.* FROM r LATERAL VIEW EXPLODE(items) t AS item;
 *
 * The COMMENT is intentionally long and example-rich: Genie reads it
 * verbatim to decide when to call this function. Keep the example
 * questions current with real user phrasing.
 */

CREATE OR REPLACE FUNCTION nimble_integration.tools.nimble_agent_list_table(
    privacy     STRING DEFAULT 'all'
        COMMENT 'Privacy filter: public | private | all. Default `all`.',
    managed_by  STRING DEFAULT 'nimble'
        COMMENT 'Filter by who manages the agent: nimble | community | self_managed. Default `nimble` (Nimble-managed catalog). Pass NULL to list every catalog.',
    max_results INT    DEFAULT 100
        COMMENT 'Results per page (1-250). Default 100.',
    page_offset INT    DEFAULT 0
        COMMENT 'Pagination offset (>=0). Default 0. Maps to the API `offset` query param.'
)
RETURNS TABLE(
    name         STRING  COMMENT 'Agent ID used to invoke the agent via /v1/agents/run (e.g. "amazon_serp", "linkedin_company_details")',
    display_name STRING  COMMENT 'Human-friendly agent name as shown in the Nimble UI',
    description  STRING  COMMENT 'Agent description from Nimble; NULL if not provided',
    vertical     STRING  COMMENT 'Business vertical / domain category (e.g. "ecommerce", "social"); NULL if not classified',
    entity_type  STRING  COMMENT 'Entity the agent extracts (e.g. "product", "profile", "search_result"); NULL if not classified',
    domain       STRING  COMMENT 'Target site / domain the agent operates against (e.g. "amazon.com"); NULL if not site-bound',
    managed_by   STRING  COMMENT 'Who manages the agent: nimble | community | self_managed',
    is_public    BOOLEAN COMMENT 'TRUE if the agent is publicly visible to all accounts'
)
COMMENT 'Catalog of Nimble web-extraction agents available to the caller, returned as rows.
Use this function whenever the user asks WHICH agents are available, what
Nimble can scrape, what domains / verticals are supported, or to discover
agent `name` values that can be passed to other tools (the /v1/agents/run
endpoint and its wrappers like amazon_serp). Default filter is
managed_by=nimble — the official Nimble-managed catalog. Pass managed_by
= NULL to also include community and self-managed agents. Example
questions this answers:
"What Nimble agents are available for Amazon?",
"List all LinkedIn-related agents in the Nimble catalog.",
"Which agents extract product pages?",
"Show me the Instagram agents I can call.",
"What''s the full list of Nimble agents and what each one does?".'
RETURN (
    WITH raw AS (
        SELECT nimble_integration.tools.nimble_agent_list(privacy, managed_by, max_results, page_offset) AS arr
    )
    SELECT item.*
    FROM raw
    LATERAL VIEW EXPLODE(arr) items AS item
);

-- Smoke test (uncomment to verify after deploy):
-- SELECT * FROM nimble_integration.tools.nimble_agent_list_table() LIMIT 5;
