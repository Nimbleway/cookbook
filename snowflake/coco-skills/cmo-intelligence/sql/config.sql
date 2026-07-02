/*
 * coco-skills/cmo-intelligence/sql/config.sql — per-app config-table foundation
 *
 * Role:        NIMBLE_ROLE (or the app-owner role that holds the grants below)
 * Creates:     __DB__.__SCHEMA__.CFG_APP      — one-row scalar config for the app
 *              __DB__.__SCHEMA__.CFG_QUERIES  — one row per SERP search term
 * Prereq:      the Nimble × Snowflake integration (setup.sql + nimble_agent_run.sql) —
 *              https://github.com/Nimbleway/cookbook/tree/main/snowflake
 *              (role, DB, warehouse, secret, EAI, and the NIMBLE_AGENT_RUN UDTF).
 *
 * The foundation that makes a provisioned app UPDATABLE AFTER CREATION. Instead
 * of one-shot procedure arguments baked into view DDL, every per-app parameter
 * lives in these two config tables:
 *
 *   - CFG_QUERIES drives ingestion. The daily refresh (ingest.sql) lateral-joins
 *     it to NIMBLE_AGENT_RUN, so ADDING A KEYWORD = INSERT A ROW and REMOVING ONE
 *     = set active=FALSE. No DDL change, no redeploy — the next run picks it up.
 *   - CFG_APP holds the scalar knobs (brand, category, focal patterns,
 *     geography, refresh cadence, retailer map). The resolver + feature views
 *     (views.sql) READ these instead of baked literals, so changing focal
 *     patterns is also a one-row edit the live views reflect.
 *
 * TEMPLATE PLACEHOLDERS (substituted by the CoCo skill / provisioning step):
 *   __DB__         target database          (e.g. NIMBLE_INTEGRATION, or an account default)
 *   __SCHEMA__     per-app schema           (e.g. ACME_CMO — one schema per app)
 *   __WAREHOUSE__  warehouse for this run   (e.g. NIMBLE_AGENT_WH)
 * These keep the target database and warehouse configurable per app.
 * Geography is CFG_APP.GEO_ZIP, below — also configurable, not pinned.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE __WAREHOUSE__;

CREATE SCHEMA IF NOT EXISTS __DB__.__SCHEMA__;
USE SCHEMA __DB__.__SCHEMA__;

-- Target database, warehouse, and geography (CFG_APP.geo_zip) are all
-- configurable — nothing is pinned to a fixed account, warehouse, or region.

-- ---------------------------------------------------------------------------
-- CFG_APP — single-row scalar config. The skill writes exactly one row on
-- create; update commands (update-focal, …) edit it in place.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.CFG_APP (
    app_key           STRING        NOT NULL,             -- = schema name; the app identity
    brand             STRING,                             -- focal brand display name; NULL = category-overview mode
    category          STRING        NOT NULL,             -- shopper-facing category ("chocolate"); feeds resolver + agent
    focal_patterns    ARRAY,                              -- brand-SKU substrings incl. spacing variants ['ACME BAR','ACMEBAR']
    geo_zip           STRING        DEFAULT '75243',      -- geography; US single-market for the first phase
    pdp_cap           NUMBER        DEFAULT 50,            -- max PDP fetches per retailer per refresh (runtime/cost guard). Seed low (~30) for a snappy first cockpit, then raise for the unattended daily run.
    geo_seed_prompts  NUMBER        DEFAULT 15,            -- top-N answer-engine prompts for the FIRST-setup GEO seed (fast, async). The weekly REFRESH_GEO() uses the full set (~60). Mirrors the pdp_cap two-tier convention.
    refresh_cron      STRING        DEFAULT 'USING CRON 0 6 * * * America/Chicago',  -- source of truth for DAILY_SHELF_TASK
    retailer_map      OBJECT,                             -- retailer -> {pdp_agent, id_key, zip_key}; resolves SERP geo + the PDP pass (see ingest.sql)
    updated_at        TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_cfg_app PRIMARY KEY (app_key)
);

-- ---------------------------------------------------------------------------
-- CFG_QUERIES — one row per SERP search term × retailer. The ingestion Task
-- lateral-joins this to NIMBLE_AGENT_RUN. PDP queries are NOT stored here —
-- they are derived from the product ids that SERP discovers (see ingest.sql).
--
-- The NIMBLE_AGENT_RUN params are NOT stored here; REFRESH_SHELF builds them at
-- call time from the keyword + CFG_APP.geo_zip + the retailer's zip_key
-- (CFG_APP.retailer_map), the same way the PDP pass does. So geography lives in
-- one place (CFG_APP.geo_zip) and a keyword is just (keyword, retailer, agent).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS __DB__.__SCHEMA__.CFG_QUERIES (
    query_id    STRING        DEFAULT UUID_STRING(),
    keyword     STRING        NOT NULL,                   -- the SERP search term
    retailer    STRING        NOT NULL,                   -- amazon | walmart | target (logical channel; feeds RAW_SERP.retailer)
    agent       STRING        NOT NULL,                   -- the Nimble WSA, e.g. 'amazon_serp'
    active      BOOLEAN       DEFAULT TRUE,               -- FALSE = stop refreshing this term (no delete needed)
    added_at    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_cfg_queries PRIMARY KEY (query_id)
);

-- ===========================================================================
-- SEED EXAMPLE — what the CoCo skill writes for the Acme reference app.
-- This is illustrative; the skill renders these INSERTs from the confirmed
-- category-architect intake (brand / keywords / focal patterns).
-- Replace the literals (or let the skill do it) when provisioning a new app.
-- ===========================================================================

-- One CFG_APP row. retailer_map carries, per retailer:
--   pdp_agent = which WSA to call for product detail
--   id_key    = the params key that carries the product id (amazon -> 'asin')
--   zip_key   = the params key that carries geography, used for BOTH the SERP and
--               PDP calls (NULL if that retailer's agents take no zip)
-- CONFIRM these agent names + param keys against the Nimble agent gallery
-- (https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery) /
-- nimble_agent_describe on first run; they can evolve.
INSERT INTO __DB__.__SCHEMA__.CFG_APP
    (app_key, brand, category, focal_patterns, geo_zip, pdp_cap, refresh_cron, retailer_map)
SELECT
    '__SCHEMA__',
    'Acme',
    'chocolate',
    ARRAY_CONSTRUCT('ACME BAR', 'ACMEBAR'),
    '75243',
    50,
    'USING CRON 0 6 * * * America/Chicago',
    OBJECT_CONSTRUCT(
        'amazon',  OBJECT_CONSTRUCT('pdp_agent', 'amazon_pdp',  'id_key', 'asin',       'zip_key', 'zip_code'),
        'walmart', OBJECT_CONSTRUCT('pdp_agent', 'walmart_pdp', 'id_key', 'product_id', 'zip_key', 'zipcode'),
        'target',  OBJECT_CONSTRUCT('pdp_agent', 'target_pdp',  'id_key', 'product_id', 'zip_key', NULL)
    )
WHERE NOT EXISTS (SELECT 1 FROM __DB__.__SCHEMA__.CFG_APP WHERE app_key = '__SCHEMA__');

-- SERP queries: keywords × {amazon, walmart, target}. The skill expands the
-- intake keyword list across the configured retailers. Geography is NOT stored
-- here — REFRESH_SHELF applies CFG_APP.geo_zip at call time.
-- (~6 keywords is the category-architect default; 3 shown here.)
INSERT INTO __DB__.__SCHEMA__.CFG_QUERIES (keyword, retailer, agent)
SELECT kw.value::STRING, r.retailer, r.agent
FROM   (SELECT * FROM TABLE(FLATTEN(INPUT => ARRAY_CONSTRUCT('acme', 'chocolate bar', 'candy bar')))) kw
CROSS JOIN (
    SELECT 'amazon'  AS retailer, 'amazon_serp'  AS agent UNION ALL
    SELECT 'walmart',               'walmart_serp'                  UNION ALL
    SELECT 'target',                'target_serp'
) r
WHERE NOT EXISTS (SELECT 1 FROM __DB__.__SCHEMA__.CFG_QUERIES);  -- guard: only seed an empty table

-- Quick checks after seeding:
--   SELECT * FROM __DB__.__SCHEMA__.CFG_APP;
--   SELECT retailer, COUNT(*) FROM __DB__.__SCHEMA__.CFG_QUERIES WHERE active GROUP BY 1;
