# Snowflake × Nimble: Live Web Data for Cortex Agents

A runnable recipe directory that turns a fresh Snowflake account into a live-web research platform: a Cortex Agent backed by Nimble's Search and Extract APIs, plus a CPG price-monitoring tutorial built on top.

## What's in here

```
snowflake/
  README.md                          ← you are here
  01_setup.sql                       ACCOUNTADMIN: role, db, warehouse, secret, EAI
  02_nimble_search.sql               NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH scalar UDF
  03_nimble_extract.sql              NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT scalar UDF
  04_cortex_agent.sql                CREATE AGENT bound to the two UDFs
  recipes/
    cpg_price_monitoring/
      README.md                      how to open the notebook
      cpg_price_monitoring.ipynb     CPG tutorial: PRODUCTS → enrich → V_PRICE_ALERTS
      schedule.sql                   daily Snowflake Task wrapping the enrichment proc
```

Two artifact types, two audiences:

- **Deployment SQL** (`.sql`) — a Snowflake admin runs these once, in order, and forgets about them.
- **Tutorial notebook** (`.ipynb`) — a data analyst opens this interactively to learn the pattern and adapt it to their own catalog.

## Prerequisites

- A Snowflake account on **Enterprise edition or above** (Cortex Agents and Cortex Complete require it).
- The `ACCOUNTADMIN` role for the one-time setup in `01_setup.sql`. Everything after that runs under `NIMBLE_ROLE`.
- A **Nimble API key** — get one at <https://online.nimbleway.com/account-settings/api-keys>.

## Deployment (5 minutes)

Run the four setup scripts in order from Snowsight, the SnowSQL CLI, or any Snowflake worksheet. Each is independently idempotent (`CREATE OR REPLACE` throughout).

1. **`01_setup.sql`** — substitute `<<YOUR_NIMBLE_API_KEY>>` with your raw Nimble token (no `Bearer ` prefix), then run as `ACCOUNTADMIN`. Creates the role, database, warehouse, secret, network rule, and external access integration.
2. **`02_nimble_search.sql`** — creates `NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH`. Wraps Nimble's [`POST /v1/search`](https://docs.nimbleway.com/api-reference/search/search) endpoint.
3. **`03_nimble_extract.sql`** — creates `NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT`. Wraps [`POST /v1/extract`](https://docs.nimbleway.com/api-reference/extract/extract).
4. **`04_cortex_agent.sql`** — registers `NIMBLE_WEB_RESEARCH_AGENT`, a Cortex Agent that orchestrates the two tools.

Verify with smoke tests:

```sql
USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;

-- Should return the URL of the top search result for "AI agents news"
SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH('AI agents news', 5):results[0]:url::STRING;

-- Should return the rendered markdown of the home page
SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT('https://nimbleway.com'):markdown::STRING;
```

Both should return a non-null result within ~30 seconds.

## Try the agent

From a Cortex Agents REST API call (see the [Cortex Agents REST API docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api)) or the Snowsight Agents UI, ask:

> *"What were the top stories about AI agent frameworks in the last week? Cite your sources."*

`NIMBLE_WEB_RESEARCH_AGENT` will pick `nimble_search` (with `focus="news"`), pull the top URLs, optionally drill into one or two with `nimble_extract`, and return a cited summary.

## Open the recipe notebook

Once the four setup files are deployed, open [`recipes/cpg_price_monitoring/cpg_price_monitoring.ipynb`](recipes/cpg_price_monitoring/cpg_price_monitoring.ipynb) to walk through the CPG price-monitoring scenario end-to-end. See that recipe's [`README.md`](recipes/cpg_price_monitoring/README.md) for runtime-specific import instructions.

## Conventions

- All DDL uses `CREATE OR REPLACE` — every script is safely re-runnable.
- Every Python UDF sends `X-Client-Source: snowflake-cortex-agent` for Nimble-side telemetry.
- UDFs return `VARIANT` so callers can navigate the JSON response inline with `:field` syntax — composable in SELECT, views, dbt models, and lateral joins. The Cortex Agent in `04_cortex_agent.sql` consumes the same VARIANT via `tool_resources.<name>.type = "function"`.
- The Nimble API key lives in a Snowflake `SECRET`; no plain-text keys appear in function bodies.

## Note on target-site terms of service

These recipes show how to pipe data fetched by Nimble into Snowflake — they do not change the legal rules that govern *what* you fetch. You are responsible for ensuring that any URLs you pass to `NIMBLE_EXTRACT`, any queries you run through `NIMBLE_SEARCH`, and any production scheduling on top complies with the target sites' terms of service, robots policies, and applicable law in your jurisdiction. The retailer references in the CPG tutorial and its sample outputs are illustrative placeholders; the brand names, UPCs, URLs, prices, ratings, and review counts shown are fictional and do not represent real products or any real commercial relationship.

## What's deferred

This recipe directory covers **Pattern A** (Cortex Agents calling Nimble tools). Two siblings are tracked separately:

- **Pattern B** — Nimble feeding Cortex Search (unstructured corpus indexing). Adds `NIMBLE_CRAWL` and an end-to-end ingest → index → query loop.
- **Pattern C** — Nimble enriching Cortex Analyst Semantic Views (structured NL questions over the CPG data this recipe produces).

## References

- Snowflake Cortex Agents: <https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api>
- Snowflake `CREATE AGENT` reference: <https://docs.snowflake.com/en/sql-reference/sql/create-agent>
- Snowflake Notebooks (Workspaces + Legacy): <https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks>
- Nimble API reference: <https://docs.nimbleway.com/api-reference/introduction>
