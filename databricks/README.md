# Databricks × Nimble: Live Web Data as SQL Table Functions

Turn a Databricks workspace into a live-web data platform: Unity Catalog **table functions** backed by Nimble's APIs and agents, callable from any SQL query, notebook, dashboard, or Databricks Genie agent — and landing results in governed Delta tables.

```sql
-- Live web search, straight from SQL:
SELECT title, url FROM nimble_integration.tools.nimble_search('AI agent frameworks news', 5, 'news');

-- Enrich a table of URLs and persist as a governed Delta table:
CREATE TABLE my_catalog.web.page_text AS
SELECT u.id, x.url, x.content
FROM my_catalog.web.urls u,
     LATERAL nimble_integration.tools.nimble_extract(u.url) x;
```

## What's in here

```
databricks/
  README.md                ← you are here
  00_prereqs.md            one-time setup: CLI auth, secret scope, the Previews toggle
  01_setup.sql             catalog + schemas (tools + recipes)
  ADDING_A_TOOL.md         how to wrap a new Nimble endpoint as a UDTF
  tools/                   one table function per Nimble capability — installable as-is
    nimble_search.sql        nimble_search(query, ...)               — Web Search API
    nimble_extract.sql       nimble_extract(url, ...)                — Extract API
    nimble_agent_list.sql    nimble_agent_list(...)                  — agent catalog
    nimble_agent_run.sql     nimble_agent_run(agent, params_json, ...) — generic agent runner
  recipes/                 runnable SQL — per-tool snippets + end-to-end recipes
    local_business_universe.sql   stitch many agent calls → governed Delta table
  helpers/                 deploy_sql.py (multi-statement deploy) + create_genie_space.py
```

Every tool is a **table function** — call it in the FROM clause. Each `tools/*.sql` ships a Python **UDTF** (`_name`, does the HTTP call and yields rows) plus a thin SQL `RETURNS TABLE` wrapper (`name`, supplies DEFAULTs and injects the API key). The public wrapper is what you call and what Genie registers; there is no scalar twin.

## Prerequisites

- A Databricks workspace with a **serverless SQL warehouse**.
- **Outbound networking enabled for the warehouse** — enable the Preview **"Enable networking for isolated workloads in Serverless SQL Warehouses"** and **cold-restart** the warehouse (Stop → Start). Without this, the tools return zero rows and the underlying request fails with `Connection refused`. See [`00_prereqs.md`](00_prereqs.md) §1.5.
- Privilege to create a catalog/schema (or an existing schema you own) and `CREATE FUNCTION` on it.
- A **Nimble API key** — get one at <https://online.nimbleway.com/account-settings/api-keys>.
- The **Databricks CLI v0.205+** installed and authenticated (`databricks auth login`).

## Deployment

### 1. One-time prereqs ([`00_prereqs.md`](00_prereqs.md))

CLI auth, the Previews toggle + cold restart, and the secret scope:

```bash
databricks secrets create-scope nimble
databricks secrets put-secret  nimble api_key   # paste token, Ctrl-D
databricks secrets put-acl     nimble users READ
```

### 2. Run the SQL files

`helpers/deploy_sql.py` splits multi-statement files and posts each statement (it treats `$$ … $$` UDTF bodies as opaque).

```bash
WH=<your-serverless-warehouse-id>   # databricks warehouses list

python3 databricks/helpers/deploy_sql.py --file databricks/01_setup.sql --warehouse "$WH"
for f in databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

1. **`01_setup.sql`** — creates catalog `nimble_integration`, schemas `tools` + `recipes`.
2. **`tools/*.sql`** — installs the table functions.

Smoke test:

```sql
SELECT count(*) AS n FROM nimble_integration.tools.nimble_search('AI agents news', 5);  -- expect > 0
SELECT length(content) FROM nimble_integration.tools.nimble_extract('https://www.nimbleway.com');
```

If a tool returns zero rows, re-check the Previews toggle + cold restart (Prerequisites).

## The tools

| Function | What it does |
|---|---|
| `nimble_search(query, max_results, focus, search_depth, ...)` | Live web search → rows of `title, description, url, content`. |
| `nimble_extract(url, render, format, ...)` | Fetch + parse one URL → a row of `url, format, content` (markdown/html/links). |
| `nimble_agent_list(privacy, managed_by, ...)` | The Nimble agent catalog → one row per agent. |
| `nimble_agent_run(agent, params_json, localization)` | Run any agent → one row: envelope + `parsing_json`. |

See [`recipes/`](recipes/) for runnable patterns — including `local_business_universe.sql`, which stitches many `nimble_agent_run('google_maps_search', …)` calls into a governed Delta table.

## Land web data as a governed Delta table

The point of SQL-native web data: results compose with `CREATE TABLE … AS` and inherit Unity Catalog governance.

```sql
-- A table of companies → enrich each homepage → governed Delta table.
CREATE TABLE my_catalog.web.company_pages AS
SELECT c.company_id, c.homepage, x.content AS homepage_markdown, current_timestamp() AS fetched_at
FROM my_catalog.crm.companies c,
     LATERAL nimble_integration.tools.nimble_extract(c.homepage) x;
```

Because a tool yields zero rows on failure (instead of raising), a batch over many inputs is never aborted by one bad row.

## Use it from Databricks Genie

Genie registers **table functions** as tools, so each public function is directly registrable — point a Genie space at `nimble_integration.tools.nimble_search` (etc.). The function `COMMENT` and per-column `COMMENT`s are what the LLM reads to decide when to call it. To create a space programmatically:

```bash
python3 databricks/helpers/create_genie_space.py \
    --title "Nimble Web Data" --warehouse "$WH" \
    --parent-path "/Users/you@example.com" \
    --instructions-file databricks/helpers/nimble_genie_instructions.md \
    --function nimble_integration.tools.nimble_search \
    --function nimble_integration.tools.nimble_extract \
    --function nimble_integration.tools.nimble_agent_list \
    --function nimble_integration.tools.nimble_agent_run
```

## Conventions

- **All DDL is re-runnable** (`CREATE OR REPLACE` / `IF NOT EXISTS`).
- **UDTF-only**: every capability is a table function. The Python UDTF does the HTTP call; a thin SQL wrapper adds DEFAULTs and injects `secret('nimble','api_key')` — no token in any function body or call site.
- **Zero rows on failure**: tools swallow errors and yield nothing, so batch CTAS jobs are resilient.
- **Function COMMENTs carry the LLM-facing spec** — they're the surface an agent picks tools from.

## Adding more Nimble functions

See [`ADDING_A_TOOL.md`](ADDING_A_TOOL.md) — pick an endpoint, write the UDTF + wrapper, add examples, smoke-test, and the gotchas to expect.

## Note on target-site terms of service

These recipes pipe data fetched by Nimble into Databricks — they don't change the rules governing *what* you fetch. You are responsible for ensuring your queries comply with target sites' terms of service, robots policies, and applicable law.

## References

- Nimble API reference: <https://docs.nimbleway.com/api-reference/introduction>
- Databricks UC Python UDFs/UDTFs (incl. network access): <https://docs.databricks.com/aws/en/udf/unity-catalog>
- Databricks Genie: <https://docs.databricks.com/aws/en/genie/>
