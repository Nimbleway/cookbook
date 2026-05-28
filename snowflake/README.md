# Snowflake × Nimble: Live Web Data for Cortex Agents

A runnable recipe directory that turns a fresh Snowflake account into a live-web research platform: a Cortex Agent backed by Nimble's Search and Extract APIs, a CPG price-monitoring tutorial on top, and a UDTF that enriches warehouse tables row-by-row with structured output from Nimble's Web Search Agents.

## What's in here

```
snowflake/
  README.md                              ← you are here
  setup/
    setup.sql                            ACCOUNTADMIN: role, db, warehouse, secret, EAI (shared)
  cortex-agent-tools/
    01_nimble_search.sql                 NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH scalar UDF
    02_nimble_extract.sql                NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT scalar UDF
    03_cortex_agent.sql                  CREATE AGENT bound to the two UDFs above
  udtf-data-feeds/
    nimble_agent_run.sql                 NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN UDTF
  recipes/
    cpg_price_monitoring/
      README.md                          how to open the notebook
      cpg_price_monitoring.ipynb         CPG tutorial: PRODUCTS → enrich → V_PRICE_ALERTS
      schedule.sql                       daily Snowflake Task wrapping the enrichment proc
    amazon_keyword_research/
      README.md                          how to open the notebook
      research_keywords_on_amazon.ipynb  lateral-join keywords with NIMBLE_AGENT_RUN('amazon_serp') + FLATTEN
      schedule.sql                       daily Snowflake Task refreshing the keyword landscape
```

Three groups of deployment SQL, two recipe notebooks:

- **`setup/`** — shared infrastructure (role, database, warehouse, secret, External Access Integration). Run once as `ACCOUNTADMIN`; every other primitive depends on it.
- **`cortex-agent-tools/`** — scalar UDFs (Search + Extract) exposed as Cortex Agent custom tools. Install this group if you want a Snowflake Intelligence chat agent backed by Nimble. The three scripts deploy in order.
- **`udtf-data-feeds/`** — UDTFs that turn Nimble's typed Web Search Agents into lateral-joinable tables. Install this group if you want to enrich warehouse rows with structured data feeds (price, availability, reviews, …) in plain SQL — no agent, no procedure.
- **`recipes/`** — runnable Jupyter notebooks that consume any of the above primitives end-to-end, plus a `schedule.sql` per recipe that puts the workflow on a daily Snowflake Task.

Install groups independently. `cortex-agent-tools/` and `udtf-data-feeds/` share `setup/` but don't depend on each other — pick one, the other, or both.

## Three primitives, three SQL shapes

Nimble's web data reaches Snowflake through three primitives, each matched to a different question.

| Primitive | Shape | When to reach for it |
| --- | --- | --- |
| `NIMBLE_SEARCH` — scalar UDF | `SELECT NIMBLE_SEARCH('query'):results[0]:url::STRING` | Inline web search inside a `SELECT`, view, or dbt model. The Cortex Agent (`cortex-agent-tools/03_cortex_agent.sql`) calls this as a tool. |
| `NIMBLE_EXTRACT` — scalar UDF | `SELECT NIMBLE_EXTRACT('https://…'):data:markdown::STRING` | Pull rendered content from a single known URL. Also a Cortex Agent tool. |
| `NIMBLE_AGENT_RUN` — UDTF | `SELECT … FROM p, TABLE(NIMBLE_AGENT_RUN('amazon_pdp', OBJECT_CONSTRUCT('asin', p.asin)))` | Lateral-join a warehouse table with **typed structured fields** from a Nimble Web Search Agent (Amazon PDP, Google Search, LinkedIn Profile, …). One input row → one structured output row. |

The two scalar UDFs are Cortex Agent custom tools. The UDTF is purpose-built for BI / dbt / `TABLE()` lateral joins — Cortex Agent tools can't be UDTFs (the agent runtime only accepts scalar functions and procedures), and inline scalars can't return per-row structured columns. Different question, different primitive.

## Prerequisites

- A Snowflake account on **Enterprise edition or above** (Cortex Agents and Cortex Complete require it).
- The `ACCOUNTADMIN` role for the one-time setup in `setup/setup.sql`. Everything after that runs under `NIMBLE_ROLE`.
- A **Nimble API key** — get one at <https://online.nimbleway.com/account-settings/api-keys>.

## Deployment (5 minutes)

Run the deployment scripts from Snowsight, the SnowSQL CLI, or any Snowflake worksheet. Each is independently idempotent (`CREATE OR REPLACE` throughout). After `setup/setup.sql` you can install either group (or both) — they don't depend on each other.

### 1. Shared infrastructure — run once

1. **`setup/setup.sql`** — substitute `<<YOUR_NIMBLE_API_KEY>>` with your raw Nimble token (no `Bearer ` prefix), then run as `ACCOUNTADMIN`. Creates the role, database, warehouse, secret, network rule, and external access integration.

### 2a. Cortex Agent tools — install this group for a Snowflake Intelligence chat agent

Deploy these three in order under `NIMBLE_ROLE`:

1. **`cortex-agent-tools/01_nimble_search.sql`** — creates `NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH`. Wraps Nimble's [`POST /v1/search`](https://docs.nimbleway.com/api-reference/search/search) endpoint.
2. **`cortex-agent-tools/02_nimble_extract.sql`** — creates `NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT`. Wraps [`POST /v1/extract`](https://docs.nimbleway.com/api-reference/extract/extract).
3. **`cortex-agent-tools/03_cortex_agent.sql`** — registers `NIMBLE_WEB_RESEARCH_AGENT`, a Cortex Agent that orchestrates the two scalar UDFs above.

### 2b. UDTF data feeds — install this group for lateral-join enrichment

1. **`udtf-data-feeds/nimble_agent_run.sql`** — creates `NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN`, a UDTF wrapping Nimble's [`POST /v1/agents/run`](https://docs.nimbleway.com/api-reference/agents/run-realtime) endpoint. Use this when you want to enrich a warehouse table row-by-row with structured output from a Nimble Web Search Agent (Amazon PDP, Google Search, LinkedIn Profile, …).

Verify with smoke tests:

```sql
USE ROLE NIMBLE_ROLE;
USE WAREHOUSE NIMBLE_AGENT_WH;

-- Should return the URL of the top search result for "AI agents news"
SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_SEARCH('AI agents news', 5):results[0]:url::STRING;

-- Should return the rendered markdown of the home page
SELECT NIMBLE_INTEGRATION.TOOLS.NIMBLE_EXTRACT('https://nimbleway.com'):markdown::STRING;

-- Should return a structured Amazon PDP row (title, price, rating, …)
SELECT parsing
FROM   TABLE(NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN(
           'amazon_pdp',
           OBJECT_CONSTRUCT('asin', 'B09B8V1LZ3')
       ));
```

All three should return a non-null result within ~30 seconds.

## Try the agent

From a Cortex Agents REST API call (see the [Cortex Agents REST API docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api)) or the Snowsight Agents UI, ask:

> *"What were the top stories about AI agent frameworks in the last week? Cite your sources."*

`NIMBLE_WEB_RESEARCH_AGENT` will pick `nimble_search` (with `focus="news"`), pull the top URLs, optionally drill into one or two with `nimble_extract`, and return a cited summary.

## Open a recipe notebook

Two notebooks live under `recipes/`:

- [`cpg_price_monitoring/cpg_price_monitoring.ipynb`](recipes/cpg_price_monitoring/cpg_price_monitoring.ipynb) — Search + Extract + Cortex Complete to assemble a daily PRODUCT_LISTINGS table from Amazon, Walmart, and Target. Needs the `cortex-agent-tools/` UDFs (`01_` and `02_`) deployed.
- [`amazon_keyword_research/research_keywords_on_amazon.ipynb`](recipes/amazon_keyword_research/research_keywords_on_amazon.ipynb) — a single SQL statement that lateral-joins a `KEYWORD_QUERIES` table with `NIMBLE_AGENT_RUN('amazon_serp', …)` and `LATERAL FLATTEN`s the product array into one row per ranked product. Shows the *one input row → many output rows* pattern that UDTFs exist for. Needs `udtf-data-feeds/nimble_agent_run.sql` deployed.

Each recipe's `README.md` explains how to open the notebook in Snowflake Workspaces, Legacy Notebooks, or local JupyterLab.

## Conventions

- All DDL uses `CREATE OR REPLACE` — every script is safely re-runnable.
- Every Python function sends `X-Client-Source: snowflake-cortex-agent` for Nimble-side telemetry.
- Scalar UDFs return `VARIANT` so callers can navigate the JSON response inline with `:field` syntax — composable in SELECT, views, dbt models. The Cortex Agent in `cortex-agent-tools/03_cortex_agent.sql` consumes the same VARIANT via `tool_resources.<name>.type = "function"`.
- The UDTF in `udtf-data-feeds/nimble_agent_run.sql` yields one row per call with a typed `parsing VARIANT` column. HTTP and transport errors are caught and surfaced as a row with `status` like `http_429`, so a single failing row never aborts a lateral join.
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
