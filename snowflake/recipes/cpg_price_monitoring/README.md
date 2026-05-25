# CPG Price Monitoring

A daily-refreshed competitive-pricing feed across Amazon, Walmart, and Target — built in ~50 lines of SQL + Python on top of `NIMBLE_SEARCH`, `NIMBLE_EXTRACT`, and Snowflake Cortex.

## What this recipe does

Given a `PRODUCTS` master table, the notebook:

1. Discovers each SKU's product detail page (PDP) on each retailer via `NIMBLE_SEARCH` with `focus="shopping"` and a domain filter.
2. Fetches each PDP's rendered markdown via `NIMBLE_EXTRACT` (JS-rendered, since these are SPAs).
3. Pulls structured fields — `price`, `currency`, `in_stock`, `rating`, `review_count`, `seller`, `image_url` — out of the markdown using `SNOWFLAKE.CORTEX.COMPLETE` with a JSON-shaped prompt.
4. Appends results to a `PRODUCT_LISTINGS` history table.
5. Surfaces actionable alerts (price drops, OOS events) through a `V_PRICE_ALERTS` view backed by window functions.

`schedule.sql` puts step 1–4 on a daily Snowflake Task — turning the notebook walkthrough into a self-refreshing production pipeline.

## Prereqs

- The four scripts in `snowflake/` (`01_setup.sql` → `04_cortex_agent.sql`) have been deployed to your Snowflake account.
- You have an active Snowpark session as `NIMBLE_ROLE` using `NIMBLE_AGENT_WH` (the notebook sets this in cell 2).

## Open the notebook

The notebook is authored as plain Jupyter `.ipynb` (nbformat v4) — no Snowsight-specific cell types — so it opens cleanly in any of three environments:

### Option 1 — Snowflake Notebooks in Workspaces (recommended if available)

The successor to Legacy Notebooks; GA across AWS/Azure/GCP commercial regions as of [Feb 5, 2026](https://docs.snowflake.com/en/release-notes/2026/other/2026-02-05-notebooks-in-workspaces). Jupyter-compatible.

1. In Snowsight, open **Projects → Workspaces**.
2. **Create → Notebook from `.ipynb`** and select `cpg_price_monitoring.ipynb`.
3. Select runtime `Run on warehouse` with `NIMBLE_AGENT_WH`.

### Option 2 — Legacy Snowflake Notebooks

Use this if your account hasn't been migrated to Workspaces yet. Legacy is still fully available; the renaming happened on [Mar 16, 2026](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-16-legacy-notebooks).

1. In Snowsight, open **Projects → Notebooks**.
2. **+ Notebook → Import .ipynb file** and select `cpg_price_monitoring.ipynb`.
3. Set the notebook's role to `NIMBLE_ROLE` and warehouse to `NIMBLE_AGENT_WH`.

### Option 3 — Local JupyterLab against a Snowpark session

Useful for IDE-style editing.

1. `pip install snowflake-snowpark-python jupyterlab`
2. Replace the `get_active_session()` call in cell 2 with `Session.builder.configs({...}).create()` using your account credentials.
3. `jupyter lab cpg_price_monitoring.ipynb`.

## Run it

Run the 10 cells in order. Cells 6 (PRODUCT_LISTINGS query) and 9 (V_PRICE_ALERTS query) have sample output preserved so you can see the expected shape before running; other cells are stripped.

Expected wall-clock for the first run with `max_workers=10`: ~30 seconds for 3 SKUs × 3 retailers.

## Productionize

Once the notebook works against your catalog, deploy [`schedule.sql`](schedule.sql) to put the enrichment on a daily 08:00 Pacific cron. The view `V_PRICE_ALERTS` then becomes a live signal you can feed into a Streamlit dashboard, a Slack webhook, or a downstream Snowflake Task.

## Adapt to your own data

- **Swap retailers.** Add `chewy`, `costco`, `bestbuy` (or anything else) to the `DOMAINS` and `PDP_PATTERNS` dicts in cell 4. The PDP-pattern regex is what reliably picks the product page out of search results.
- **Use Nimble's retailer-specific Web Search Agents instead of the markdown+LLM step.** For higher-fidelity structured output, swap the Extract + Cortex call inside `_enrich_one` for a single call to `/v1/agent/run` with `agent="amazon_pdp"` (Walmart PDP, Target PDP, etc. all available — see the [agent gallery](https://docs.nimbleway.com/nimble-sdk/agentic/agent-gallery/)). This requires a thin `NIMBLE_AGENT_RUN` stored proc on the Snowflake side; a companion recipe covers it.
- **Add a Cortex Analyst Semantic View on top.** A companion recipe wires this CPG data into a [Semantic View](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec) so analysts can ask natural-language questions over it.
