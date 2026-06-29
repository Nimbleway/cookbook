/*
 * setup/setup.sql — Nimble × Snowflake integration (shared infrastructure)
 *
 * Role:        ACCOUNTADMIN (the rest of the deployment runs as NIMBLE_ROLE)
 * Creates:     NIMBLE_ROLE, NIMBLE_INTEGRATION database + TOOLS/AGENTS schemas,
 *              NIMBLE_AGENT_WH warehouse, NIMBLE_API_RULE network rule,
 *              NIMBLE_API_KEY secret, NIMBLE_API_ACCESS external access integration,
 *              INTEGRATION_VERSION view (version marker for upgrade detection).
 * Prereq:      A Nimble API key — get one at https://online.nimbleway.com/account-settings/api-keys
 * Runtime:     ~10 seconds.
 *
 * Substitute the placeholder below before running:
 *   <<YOUR_NIMBLE_API_KEY>>   the raw Bearer token (no "Bearer " prefix)
 *
 * Run order: 01 → 02 → 03 → 04. Then open the recipe notebook in Snowsight.
 */

USE ROLE ACCOUNTADMIN;

-- Custom role that owns the integration. Cortex features require the
-- SNOWFLAKE.CORTEX_USER database role grant below.
CREATE ROLE IF NOT EXISTS NIMBLE_ROLE;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE NIMBLE_ROLE;
GRANT ROLE NIMBLE_ROLE TO ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS NIMBLE_INTEGRATION;
CREATE SCHEMA IF NOT EXISTS NIMBLE_INTEGRATION.TOOLS;
CREATE SCHEMA IF NOT EXISTS NIMBLE_INTEGRATION.AGENTS;
CREATE SCHEMA IF NOT EXISTS NIMBLE_INTEGRATION.RECIPES;

GRANT OWNERSHIP ON DATABASE NIMBLE_INTEGRATION                 TO ROLE NIMBLE_ROLE COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   NIMBLE_INTEGRATION.TOOLS           TO ROLE NIMBLE_ROLE COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   NIMBLE_INTEGRATION.AGENTS          TO ROLE NIMBLE_ROLE COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   NIMBLE_INTEGRATION.RECIPES         TO ROLE NIMBLE_ROLE COPY CURRENT GRANTS;

-- Dedicated XSMALL warehouse for agent tool calls and the recipe notebook.
CREATE WAREHOUSE IF NOT EXISTS NIMBLE_AGENT_WH
    WAREHOUSE_SIZE       = XSMALL
    AUTO_SUSPEND         = 60
    AUTO_RESUME          = TRUE
    INITIALLY_SUSPENDED  = TRUE
    COMMENT              = 'Warehouse for Nimble stored procs and Cortex Agent tool calls';

GRANT USAGE ON WAREHOUSE NIMBLE_AGENT_WH TO ROLE NIMBLE_ROLE;

-- Egress is locked to Nimble's public API host. Auth, request bodies, and
-- response shapes are documented at https://docs.nimbleway.com/api-reference/introduction
CREATE OR REPLACE NETWORK RULE NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_RULE
    TYPE          = HOST_PORT
    MODE          = EGRESS
    VALUE_LIST    = ('sdk.nimbleway.com');

CREATE OR REPLACE SECRET NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY
    TYPE          = GENERIC_STRING
    SECRET_STRING = '<<YOUR_NIMBLE_API_KEY>>'
    COMMENT       = 'Raw Bearer token for the Nimble API. Get one at https://online.nimbleway.com/account-settings/api-keys';

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION NIMBLE_API_ACCESS
    ALLOWED_NETWORK_RULES = (NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_RULE)
    ALLOWED_AUTHENTICATION_SECRETS = (NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY)
    ENABLED = TRUE;

GRANT USAGE ON INTEGRATION NIMBLE_API_ACCESS TO ROLE NIMBLE_ROLE;
GRANT READ   ON SECRET NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_KEY TO ROLE NIMBLE_ROLE;
GRANT USAGE  ON NETWORK RULE NIMBLE_INTEGRATION.TOOLS.NIMBLE_API_RULE TO ROLE NIMBLE_ROLE;

-- Version marker for the whole integration (this file + the tool functions).
-- BUMP `version` on any change to setup.sql or the cortex-agent-tools / udtf-data-feeds
-- functions, so consumers can detect a stale install and prompt an upgrade. An account
-- that predates this view is simply treated as "older than 1.0.0".
CREATE OR REPLACE VIEW NIMBLE_INTEGRATION.TOOLS.INTEGRATION_VERSION AS
    SELECT '1.1.0' AS version;  -- 1.1.0: NIMBLE_SEARCH UDF is now part of the expected tool surface
GRANT SELECT ON VIEW NIMBLE_INTEGRATION.TOOLS.INTEGRATION_VERSION TO ROLE NIMBLE_ROLE;

-- Sanity check (optional)
SHOW INTEGRATIONS LIKE 'NIMBLE_API_ACCESS';
SELECT version AS nimble_integration_version FROM NIMBLE_INTEGRATION.TOOLS.INTEGRATION_VERSION;
