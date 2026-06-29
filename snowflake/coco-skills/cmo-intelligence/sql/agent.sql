/*
 * coco-skills/cmo-intelligence/sql/agent.sql — the per-app Cortex agent
 *
 * Role:     NIMBLE_ROLE (Cortex Agents must be enabled on the account)
 * Creates:  __DB__.__SCHEMA__.__AGENT_NAME__   (e.g. ACME_SHELF_ANALYST)
 * Prereq:   semantic_view.sql (SHELF_SV) + NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH
 *           (the live-web UDF, bundled in assets/integration/ — see Phase 0).
 *
 * A pre-seeded Cortex agent with two data sources: SHELF_SV (Cortex Analyst,
 * NL -> SQL over the ingested shelf) for share / price / sponsored / focal-share
 * questions, and NIMBLE_SEARCH (a scalar-UDF tool) for LIVE web data — current
 * prices, reviews, news and shopper sentiment from external sites. It charts
 * comparative results. (Cortex agent tools must be scalar UDFs or procedures, so
 * live web rides on the NIMBLE_SEARCH UDF; the NIMBLE_AGENT_RUN UDTF is purpose-
 * built for lateral-join enrichment during ingestion, not as an agent tool.)
 *
 * analyze_shelf is scoped to the shelf semantic view; sentiment, content,
 * AI-answer and next-best-action surfaces still live in cockpit-only views.
 * Widen SHELF_SV (semantic_view.sql) to bring those into the agent's scope.
 *
 * TEMPLATE PLACEHOLDERS:
 *   __DB__ __SCHEMA__ __BRAND__ __CATEGORY__ __WAREHOUSE__   (see config.sql)
 *   __AGENT_NAME__   = UPPER(brand, spaces -> underscores) || '_SHELF_ANALYST'
 */

USE ROLE NIMBLE_ROLE;
USE SCHEMA __DB__.__SCHEMA__;

-- PROFILE/COMMENT are dollar-quoted so a brand with an apostrophe (e.g. a brand
-- like "Brand's") doesn't break the literal during placeholder substitution. (For a
-- brand containing a double-quote, also strip/escape it in the JSON display_name.)
CREATE OR REPLACE AGENT __DB__.__SCHEMA__.__AGENT_NAME__
    WITH PROFILE = $${"display_name": "__BRAND__ Shelf Analyst"}$$
    COMMENT = $$__BRAND__ CMO digital-shelf agent$$
    FROM SPECIFICATION
$$
models:
  orchestration: auto
instructions:
  orchestration: |
    You are the __BRAND__ digital-shelf strategist for the __CATEGORY__ category across Walmart, Amazon and Target. Use analyze_shelf for share of shelf, price and sponsored placement data from our internal database. Use nimble_search for live web data — current prices, reviews, news, and shopper sentiment from external websites. __BRAND__ is the focal brand; filter brand_tier for competitors. Always pass comparative results to visualize.
  response: |
    Write for a CMO. Lead with the key number, show a chart, then a specific next best action. No jargon, no emoji.
  sample_questions:
    - question: What is __BRAND__ share of shelf by retailer
    - question: Which competitors rely most on sponsored placement
    - question: What are shoppers saying about __BRAND__ online this week
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: analyze_shelf
  - tool_spec:
      type: data_to_chart
      name: visualize
  - tool_spec:
      type: generic
      name: nimble_search
      description: Search the live web for current prices, reviews, news articles, and shopper sentiment about products. Use this when the user asks about external, current, or live information not in our shelf database.
      input_schema:
        type: object
        properties:
          query:
            type: string
            description: The search query to run on the web
          max_results:
            type: integer
            description: Number of results to return (default 10)
          focus:
            type: string
            description: "Search focus: general, news, shopping, social, or academic"
            enum: [general, news, shopping, social, academic]
        required:
          - query
tool_resources:
  analyze_shelf:
    semantic_view: __DB__.__SCHEMA__.SHELF_SV
    execution_environment:
      type: warehouse
      warehouse: __WAREHOUSE__
  nimble_search:
    type: function
    identifier: NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH
    execution_environment:
      type: warehouse
      warehouse: __WAREHOUSE__
$$;
