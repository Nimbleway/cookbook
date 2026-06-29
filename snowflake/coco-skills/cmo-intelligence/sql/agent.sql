/*
 * coco-skills/cmo-intelligence/sql/agent.sql — the per-app Cortex agent
 *
 * Role:     NIMBLE_ROLE (Cortex Agents must be enabled on the account)
 * Creates:  __DB__.__SCHEMA__.__AGENT_NAME__   (e.g. ACME_SHELF_ANALYST)
 * Prereq:   semantic_view.sql (SHELF_SV)
 *
 * A pre-seeded Cortex agent grounded on SHELF_SV: it answers shelf / price /
 * sponsored / focal-share questions via Cortex Analyst (NL -> SQL) and charts
 * the result. It has NO live web tool — all web data is already ingested into
 * the warehouse. Cortex agent tools are scalar UDFs or procedures, so if a live
 * web tool is ever wanted the path is a scalar UDF (NIMBLE_SEARCH / NIMBLE_EXTRACT);
 * the NIMBLE_AGENT_RUN UDTF is purpose-built for lateral-join enrichment instead.
 *
 * The agent is grounded only on the shelf semantic view for now; sentiment,
 * content, AI-answer and next-best-action surfaces live in cockpit-only views.
 * Widen SHELF_SV (semantic_view.sql) to bring those into the agent's scope.
 *
 * TEMPLATE PLACEHOLDERS:
 *   __DB__ __SCHEMA__ __BRAND__ __CATEGORY__ __WAREHOUSE__   (see config.sql)
 *   __AGENT_NAME__   = UPPER(brand, spaces -> underscores) || '_SHELF_ANALYST'
 */

USE ROLE NIMBLE_ROLE;
USE SCHEMA __DB__.__SCHEMA__;

CREATE OR REPLACE AGENT __DB__.__SCHEMA__.__AGENT_NAME__
    WITH PROFILE = '{"display_name": "__BRAND__ Shelf Analyst"}'
    COMMENT = '__BRAND__ CMO digital-shelf agent'
    FROM SPECIFICATION
$$
models:
  orchestration: auto
instructions:
  orchestration: |
    You are the __BRAND__ digital-shelf strategist for the __CATEGORY__ category across Walmart, Amazon and Target. Use analyze_shelf for share of shelf, price and sponsored placement. __BRAND__ is the focal brand; filter brand_tier for competitors. Always pass comparative results to visualize.
  response: |
    Write for a CMO. Lead with the key number, show a chart, then a specific next best action. No jargon, no emoji.
  sample_questions:
    - question: What is __BRAND__ share of shelf by retailer
    - question: Which competitors rely most on sponsored placement
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: analyze_shelf
  - tool_spec:
      type: data_to_chart
      name: visualize
tool_resources:
  analyze_shelf:
    semantic_view: __DB__.__SCHEMA__.SHELF_SV
    execution_environment:
      type: warehouse
      warehouse: __WAREHOUSE__
$$;
