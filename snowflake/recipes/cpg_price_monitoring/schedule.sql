/*
 * schedule.sql — production scheduling for the CPG price-monitoring recipe
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.RECIPES.DAILY_ENRICHMENT task
 * Prereq:      cpg_price_monitoring.ipynb has been run at least once (creates
 *              PRODUCTS, PRODUCT_LISTINGS, ENRICH_PRODUCT_LISTINGS).
 *
 * Schedule:    daily at 08:00 America/Los_Angeles. Adjust to your business hours.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;

CREATE OR REPLACE TASK NIMBLE_INTEGRATION.RECIPES.DAILY_ENRICHMENT
    WAREHOUSE = NIMBLE_AGENT_WH
    SCHEDULE  = 'USING CRON 0 8 * * * America/Los_Angeles'
    COMMENT   = 'Daily competitive-pricing enrichment across Amazon, Walmart, Target'
AS
    CALL NIMBLE_INTEGRATION.RECIPES.ENRICH_PRODUCT_LISTINGS(
        ARRAY_CONSTRUCT('amazon', 'walmart', 'target'),
        10
    );

-- Tasks are created suspended; resume to activate scheduling.
ALTER TASK NIMBLE_INTEGRATION.RECIPES.DAILY_ENRICHMENT RESUME;

-- Inspect:
-- SHOW TASKS IN SCHEMA NIMBLE_INTEGRATION.RECIPES;
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'DAILY_ENRICHMENT'));
