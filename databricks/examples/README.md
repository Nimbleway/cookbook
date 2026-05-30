# Examples — Nimble × Databricks

Runnable SQL snippets demonstrating the functions deployed by `../01_setup.sql` and the per-capability files in `../tools/` (e.g. `../tools/amazon_serp.sql`).

Run any of these in the Databricks SQL editor (point it at a serverless warehouse) or via `databricks api post /api/2.0/sql/statements`.

## What's here

```
examples/
  README.md                       ← you are here
  amazon_serp_basic.sql           single call, EXPLODE, filter
  amazon_serp_keyword_table.sql   keyword-table-driven loader
  amazon_serp_aggregates.sql      avg price, prime ratio, top-N
  nimble_search_basic.sql         simple search, focus modes, deep-mode
  nimble_agent_list_basic.sql     list catalog, filter, include community
  nimble_agent_run_basic.sql      generic agent runner, parse JSON output
```

## Adding examples for new functions

When you add a new tool under `../tools/` (e.g. `../tools/nimble_web_search.sql`), drop matching example files here using the same triple:

- `<function>_basic.sql` — minimal single call + EXPLODE pattern
- `<function>_keyword_table.sql` (or analogous) — table-driven driver
- `<function>_aggregates.sql` — analytics queries

Each file should be **standalone runnable** after `../01_setup.sql` and the relevant `../tools/<function>.sql` have been deployed.
