# Amazon keyword research with `NIMBLE_AGENT_RUN`

A single SQL statement that turns a `KEYWORD_QUERIES` table of search terms into a fully populated `PRODUCT_SEARCH_RESULTS` table — title, ASIN, price, rating, review count, image URL, sponsored flag, and ranking position for every product that surfaces on Amazon for each query.

This is the canonical UDTF use case: **one input row → many structured output rows**. A scalar UDF can't do this. A stored procedure can do it but pays the cost of a Python middle-tier. `NIMBLE_AGENT_RUN` + `LATERAL FLATTEN` does it in one statement.

## What this recipe does

Given a `KEYWORD_QUERIES` table of research terms, the notebook:

1. Lateral-joins each query row with `TABLE(NIMBLE_AGENT_RUN('amazon_serp', OBJECT_CONSTRUCT('keyword', q.keyword)))` — Nimble's Amazon Search Engine Results Page Web Search Agent.
2. `LATERAL FLATTEN(INPUT => a.parsing)` expands the agent's product array into one row per result.
3. Projects each product into typed columns — `position`, `asin`, `title`, `web_price`, `currency`, `rating`, `review_count`, `image_url`, `sponsored`.
4. Appends the result into `PRODUCT_SEARCH_RESULTS` for trend analysis (share-of-shelf, new entrants, ranking shifts).
5. Builds a `V_NEW_ENTRANTS` view that flags products appearing on a tracked query for the first time in the last 7 days.

[`schedule.sql`](schedule.sql) puts the enrichment on a daily Snowflake Task so the landscape stays current without any application code.

## Why SERP (not PDP)

The Nimble agent gallery ships two flavours of Amazon agents:

- **`amazon_pdp`** — *one ASIN in, one product object out.* Best when you already know which products you care about (you have ASINs in your catalog) and want fresh details on each.
- **`amazon_serp`** — *one keyword in, an array of products out.* Best when you're researching the competitive landscape for a category and don't yet know the ASINs — you want to discover who is ranking, at what price, with what reviews.

Pair the two recipes: use this SERP recipe to discover ASINs of interest, then feed those ASINs into the [`cpg_price_monitoring`](../cpg_price_monitoring/) PDP enrichment for daily price tracking.

## How this differs from `cpg_price_monitoring`

| | `cpg_price_monitoring` | `amazon_keyword_research` (this recipe) |
| --- | --- | --- |
| Primitive | `NIMBLE_SEARCH` + `NIMBLE_EXTRACT` + `SNOWFLAKE.CORTEX.COMPLETE` | `NIMBLE_AGENT_RUN` (Amazon SERP WSA) |
| Input | `PRODUCTS(sku, brand, name)` — you bring SKU master data | `KEYWORD_QUERIES(query, category)` — you bring research terms |
| Output | One row per `(sku, retailer)` — you tell it which products | Many rows per query — Amazon decides which products surface |
| Discovery | Search-then-extract finds the PDP per `(brand, name)` | The SERP agent enumerates the top organic + sponsored results |
| Cardinality | 1 input row → 1 output row | 1 input row → up to ~50 output rows |
| Extraction | LLM-on-markdown via Cortex | Native Nimble parsing — typed `parsing` JSON |
| Code surface | Stored proc + ThreadPoolExecutor | One `INSERT INTO … SELECT … FROM TABLE(NIMBLE_AGENT_RUN(...)) , LATERAL FLATTEN(...)` statement |
| Token cost | Pays per row for Cortex completion | Zero LLM tokens |

## Prereqs

- `../../setup/setup.sql` deployed (role, db, warehouse, secret, EAI).
- `../../udtf-data-feeds/nimble_agent_run.sql` deployed (the UDTF this notebook calls).
- An active Snowpark session as `NIMBLE_ROLE` using `NIMBLE_AGENT_WH` (the notebook sets this in cell 2).

`cortex-agent-tools/` is NOT a prerequisite for this recipe — `NIMBLE_AGENT_RUN` is a standalone primitive in its own install group.

## Open the notebook

The notebook is plain Jupyter `.ipynb` (nbformat v4), so it opens cleanly in any of three environments:

### Option 1 — Snowflake Notebooks in Workspaces (recommended if available)

The successor to Legacy Notebooks; GA across AWS/Azure/GCP commercial regions as of [Feb 5, 2026](https://docs.snowflake.com/en/release-notes/2026/other/2026-02-05-notebooks-in-workspaces). Jupyter-compatible.

1. In Snowsight, open **Projects → Workspaces**.
2. **Create → Notebook from `.ipynb`** and select `research_keywords_on_amazon.ipynb`.
3. Select runtime `Run on warehouse` with `NIMBLE_AGENT_WH`.

### Option 2 — Legacy Snowflake Notebooks

Use this if your account hasn't been migrated to Workspaces yet. Legacy is still fully available; the renaming happened on [Mar 16, 2026](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-16-legacy-notebooks).

1. In Snowsight, open **Projects → Notebooks**.
2. **+ Notebook → Import .ipynb file** and select `research_keywords_on_amazon.ipynb`.
3. Set the notebook's role to `NIMBLE_ROLE` and warehouse to `NIMBLE_AGENT_WH`.

### Option 3 — Local JupyterLab against a Snowpark session

Useful for IDE-style editing.

1. `pip install snowflake-snowpark-python jupyterlab`
2. Replace the `get_active_session()` call in cell 2 with `Session.builder.configs({...}).create()` using your account credentials.
3. `jupyter lab research_keywords_on_amazon.ipynb`.

## Run it

Run the cells in order. The enrichment cell (cell 4) issues a single `INSERT INTO … SELECT … FROM TABLE(NIMBLE_AGENT_RUN(...)) , LATERAL FLATTEN(...)` against three sample keyword queries and should take ~30 seconds, producing roughly 60–150 rows in `PRODUCT_SEARCH_RESULTS` (depending on how many products each SERP returns). Sample output is preserved on the preview cells so you can see the expected shape before running.

> **Confirm `parsing` field names on first run.** The exact field names inside `parsing[*]` (`title`, `asin`, `web_price`, `rating`, …) are based on the [Nimble agent gallery](https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery) and can evolve as Nimble extends the agent. Before pinning these in a dbt model or scheduled task, run `SELECT raw FROM TABLE(NIMBLE_AGENT_RUN('amazon_serp', OBJECT_CONSTRUCT('keyword', 'noise canceling headphones')))` once and inspect the actual JSON.

## Productionize

Deploy [`schedule.sql`](schedule.sql) to put the lateral-join enrichment on a daily 08:00 Pacific cron. The view `V_NEW_ENTRANTS` then becomes a live signal you can feed into a Streamlit dashboard, a Slack webhook, or a downstream Snowflake Task.

## Adapt to your own data

- **Swap the agent.** Replace `'amazon_serp'` with any keyword-driven agent in the [Nimble agent gallery](https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery) — `google_search`, `linkedin_search`, and sibling marketplace SERP agents (Walmart, Target, Best Buy, … — see the gallery for the canonical agent names), …. Each one is a drop-in replacement; only the field names inside `parsing` change.
- **Track share-of-shelf per brand.** Add a `brand` column to `PRODUCT_SEARCH_RESULTS` derived from the title (or a lookup table) and aggregate by `(query, brand)` over time to see who is taking ranking from whom.
- **Multi-marketplace.** Pass `country` inside `params` (e.g. `OBJECT_CONSTRUCT('keyword', q.keyword, 'country', 'GB')`) to query the UK marketplace, then partition `PRODUCT_SEARCH_RESULTS` by marketplace.
- **Compose into a dbt model.** The `INSERT INTO … SELECT … FROM TABLE(NIMBLE_AGENT_RUN(...)) , LATERAL FLATTEN(...)` statement is also a valid dbt incremental model body — no Snowflake-specific orchestration required.

## A note on sample data

The three keyword queries in cell 1 are illustrative placeholders. Swap them with your own category terms before running against your production warehouse. The sample outputs preserved in the notebook are fictional — they show the shape of a successful run, not real product data.
