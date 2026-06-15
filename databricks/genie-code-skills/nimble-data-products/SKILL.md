---
name: nimble-data-products
description: |
  Builds a Databricks data product from live web data, natively in Genie Code, end to end:
  discovers the right Nimble web-data agents, scrapes into a Delta table, and assembles an AI/BI
  dashboard — table → dashboard, for a quick demo or a real data product. Use whenever a request
  pairs live or scraped web data WITH a Databricks destination — e.g. "pricing comparison on dog
  products from Amazon and Walmart", "scrape Zillow/Instagram/Maps/search results into a Delta table
  and build a dashboard", "show competitor prices from the web in a dashboard", "live web data in
  Databricks". Runs entirely on SQL + Genie's native dashboard agent via the Nimble Unity Catalog
  functions — no CLI, no shell. Do NOT use for generic Databricks work with no live-web-data angle.
---

# Nimble on Databricks — live web search → Delta → dashboard (Genie Code)

Turn a natural-language brief like `pricing comparison on dog products from Amazon and Walmart` into a
working Databricks data product, all inside Genie Code:
**discover agents (SQL) → ingest live web search data into a Delta table (SQL) → build an AI/BI dashboard
and/or a deployed app (Genie's native dashboard agent + AppsAgent) → deliver the link + headline.**

You run everything natively — SQL against the warehouse and Genie's built-in dashboard agent. There is
**no `nimble` CLI, no `databricks` CLI, and no shell**: every Nimble capability is a Unity Catalog
table function in `nimble_integration.tools`, and dashboards/apps are built by Genie's native
dashboard agent and AppsAgent.

## Golden rules

- **Discover, don't assume.** Read agent names with `nimble_agent_list()`, input params with
  `nimble_agent_describe('<agent>')`, and output fields by probing one call
  (`SELECT parsing FROM nimble_agent_run(...)`). Never hardcode from memory — Amazon search takes
  `keyword`, not `query`.
- **Probe before fanning out.** Run one `nimble_agent_run` per source first to learn its real field
  names, the localization flag, and value formats (some sources return numeric prices, others
  currency strings). This catches surprises in ~40s instead of after a wasted full round.
- **One unified table.** A `source` column + a normalized core (`product_name, price, currency,
  rating, review_count, brand, url, …`) + a `raw VARIANT` catch-all. Keep only fields the chosen
  agents actually emit.
- **Defensive casts, per-agent localization.** Strip non-numerics before casting prices
  (`try_cast(regexp_replace(...))`), and set localization per agent (it is not global).
- **Confirm the target before writing.** Recommend a writable `catalog.schema` (default
  `users.<username>`) and confirm before creating tables.
- **Branding is always on, neutral.** "Powered by Nimble", light theme, yellow as an accent only.
  See `references/branding.md`.
- **End with the link + the one-sentence insight** (e.g. the price gap).

## Workflow

Track these as todos so nothing is skipped.

### Phase 0 — Preflight (SQL only)
1. `SELECT current_user()` — capture the username (for the default `users.<username>` schema).
2. **Integration gate** — confirm all five Nimble functions exist:
   ```sql
   SHOW FUNCTIONS IN nimble_integration.tools;
   -- expect: nimble_search, nimble_extract, nimble_agent_list, nimble_agent_describe, nimble_agent_run
   ```
   **If missing → STOP** and tell the user to install the Nimble × Databricks integration from the
   cookbook (<https://github.com/Nimbleway/cookbook/tree/main/databricks>). Do not try to auto-install.
3. **Recommend + confirm** a writable `catalog.schema` (default `users.<username>`). Verify
   writability — some shared catalogs deny `CREATE TABLE`.

(Genie runs against a SQL warehouse already, so there is no warehouse selection step.)

### Phase 1 — Interpret the brief + clarify
Parse the brief into: **domain/entity · search terms · sources · analysis goal**. Then confirm:
- **Deliverable** — table, table + dashboard, or table + dashboard + app (always ask).
- **Sources** — the agents you matched (e.g. Amazon + Walmart SERP).
- **Volume** — default ~8–10 search terms, ~100+ rows/source.

Keep the brief's intent (the "analysis goal") — it picks the Phase 4 dashboard shape and the headline.

### Phase 2 — Discover agents + map a unified schema
See `references/nimble-agents.md`.
1. `nimble_agent_list()` (SQL) — filter by the source/domain keywords.
2. `nimble_agent_describe('<agent>')` (SQL) — read each chosen agent's input params (required ones,
   exact names, localization/pagination flags). Output fields come from the §2.5 probe, not here.
3. Design **one unified table**: `source` column + normalized core + `raw VARIANT`.

### Phase 3 — Ingest (control table + one set-based INSERT)
See `references/nimble-agents.md` for the full SQL.
1. **Probe one call per source first** — read the real field names, localization flag, and price format.
2. Create a **control (queries) table** (one row per source × term) and the **unified results table**.
3. Run **one INSERT** that calls `nimble_agent_run` via a correlated `LATERAL` join over the control
   table (with a `/*+ REPARTITION(N) */` hint so the agent calls run in parallel). It is one
   long-running statement — Genie runs it inline; the live agent calls take ~30–40s each, parallelized.
4. **Reconcile against the control table** (LEFT JOIN) to confirm every source landed data; if a
   source shows 0, re-check its localization flag and casts.

### Phase 4 — Build the deliverable(s) — Genie's native agents
Genie builds both deliverables natively from plain-English intent — describe **what**; the agents
assemble it. Do **not** hand-write Lakeview JSON or scaffold app files yourself. Pick the per-vertical
view set and the exact hand-off wording from `references/deliverables.md`.

- **Dashboard** → hand off to Genie's built-in **dashboard agent**: point it at the unified results
  table, request the per-vertical widgets (KPIs, comparison bars, price-vs-rating scatter, product
  table with Open links), apply branding (title wordmark + a top text widget "Live web search · Powered
  by Nimble", yellow accent), and publish.
- **App** (only if chosen) → create a Databricks App; Genie's **AppsAgent** scaffolds and deploys it.
  Default to a **Python** framework (Streamlit / Dash / Gradio) — the native path for Genie Code apps
  (React is supported too, build-less via a CDN). Tell it to query the
  unified table, show the per-vertical views, and brand it "Powered by Nimble" (light theme, yellow
  accent). Confirm it reaches RUNNING and grab the URL.

For multi-source briefs, always include the cross-source comparison (aggregate bars by source) and,
if confident item-level matches exist, a "same-product price gap" view.

### Phase 5 — Verify, deliver & headline
- Confirm the dashboard published; collect the link.
- Summarize what was built and the **headline insight** (the comparison takeaway).
- Offer iterations (more charts, item-level matching, a scheduled refresh).

## Reference map
- `references/nimble-agents.md` — discovery, schema mapping, the control-table + `LATERAL` ingest SQL, and gotchas.
- `references/deliverables.md` — per-vertical view sets + the instructions to give Genie's dashboard agent and AppsAgent.
- `references/branding.md` — "Powered by Nimble" tokens + how to brand an AI/BI dashboard.
