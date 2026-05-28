/*
 * schedule.sql — production scheduling for the Amazon keyword research recipe
 *
 * Role:        NIMBLE_ROLE
 * Creates:     NIMBLE_INTEGRATION.RECIPES.DAILY_AMAZON_KEYWORD_RESEARCH task
 * Prereq:      research_keywords_on_amazon.ipynb has been run at least once
 *              (creates KEYWORD_QUERIES, PRODUCT_SEARCH_RESULTS, V_NEW_ENTRANTS).
 *
 * Schedule:    daily at 08:00 America/Los_Angeles. Adjust to your business hours.
 *
 * Unlike the cpg_price_monitoring schedule, no stored proc is needed — the
 * lateral-join + FLATTEN INSERT is a single SQL statement that a Task can
 * execute directly.
 */

USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;

CREATE OR REPLACE TASK NIMBLE_INTEGRATION.RECIPES.DAILY_AMAZON_KEYWORD_RESEARCH
    WAREHOUSE = NIMBLE_AGENT_WH
    SCHEDULE  = 'USING CRON 0 8 * * * America/Los_Angeles'
    COMMENT   = 'Daily Amazon SERP keyword research via NIMBLE_AGENT_RUN(amazon_serp, ...)'
AS
    INSERT INTO NIMBLE_INTEGRATION.RECIPES.PRODUCT_SEARCH_RESULTS
        (keyword, category, position, asin, title, price, currency, rating,
         review_count, image_url, sponsored, status, enriched_at)
    SELECT
        q.keyword                                              AS keyword,
        q.category                                           AS category,
        p.value:position::INTEGER                            AS position,
        p.value:asin::STRING                                 AS asin,
        p.value:product_name::STRING                                AS title,
        p.value:price::NUMBER(10, 2)                     AS price,
        p.value:currency::STRING                             AS currency,
        p.value:rating::NUMBER(3, 2)                         AS rating,
        p.value:review_count::INTEGER                       AS review_count,
        p.value:image_url::STRING                                AS image_url,
        p.value:sponsored::BOOLEAN                           AS sponsored,
        a.status                                             AS status,
        CURRENT_TIMESTAMP()                                  AS enriched_at
    FROM NIMBLE_INTEGRATION.RECIPES.KEYWORD_QUERIES q,
         TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
             'amazon_serp',
             OBJECT_CONSTRUCT('keyword', q.keyword)
         )) a,
         LATERAL FLATTEN(INPUT => a.parsing) p
    WHERE q.keyword IS NOT NULL
      AND a.status = 'success';

-- Tasks are created suspended; resume to activate scheduling.
ALTER TASK NIMBLE_INTEGRATION.RECIPES.DAILY_AMAZON_KEYWORD_RESEARCH RESUME;

-- Inspect:
-- SHOW TASKS IN SCHEMA NIMBLE_INTEGRATION.RECIPES;
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'DAILY_AMAZON_KEYWORD_RESEARCH'));
