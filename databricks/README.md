# Databricks × Nimble: Live Web Data as SQL Functions

A runnable recipe directory that turns a fresh Databricks workspace into a live-web data platform: Unity-Catalog SQL functions backed by Nimble's agents and APIs, callable from any SQL query, notebook, dashboard, or Databricks Genie agent.

## What's in here

```
databricks/
  README.md                          ← you are here
  00_prereqs.md                      one-time CLI setup: secret scope + ACL
  01_setup.sql                       catalog, schemas, UC HTTP CONNECTION
  02_amazon_serp.sql                 nimble_integration.tools.amazon_serp
  examples/
    README.md                        what's in this folder
    amazon_serp_basic.sql            single call, EXPLODE, filter
    amazon_serp_keyword_table.sql    keyword-table-driven loader
    amazon_serp_aggregates.sql       average price, prime ratio, top-N
```

Two artifact types, two audiences:

- **Deployment SQL** (`01_*`, `02_*`) — a workspace admin (or an LLM agent with workspace access) runs these once and forgets about them.
- **Example queries** (`examples/*.sql`) — a data analyst or agent runs these to learn the pattern and adapt it to their own data.

## Prerequisites

- A Databricks workspace with **serverless SQL warehouses** (the `http_request()` SQL builtin requires serverless or DBR 15.4+).
- Privileges to create a UC `CONNECTION` in the metastore (metastore admin or `CREATE CONNECTION` privilege).
- A **Nimble API key** — get one at <https://online.nimbleway.com/account-settings/api-keys>.
- The **Databricks CLI v0.205+** installed and authenticated (`databricks auth login`).

## Deployment (5 minutes)

### 1. One-time prereqs ([`00_prereqs.md`](00_prereqs.md))

```bash
databricks secrets create-scope nimble
databricks secrets put-secret  nimble api_key   # paste token, Ctrl-D
databricks secrets put-acl     nimble users READ
```

### 2. Run the SQL files in order

Each is independently idempotent (`CREATE OR REPLACE` / `IF NOT EXISTS` throughout). Open them in the Databricks SQL editor and **Run All**, or fire them from the CLI:

```bash
WH=<your-serverless-warehouse-id>   # databricks warehouses list

for f in databricks/01_setup.sql databricks/02_amazon_serp.sql; do
  databricks api post /api/2.0/sql/statements \
    --json "$(jq -n --rawfile s "$f" --arg wh "$WH" \
              '{warehouse_id:$wh, statement:$s, wait_timeout:"50s"}')"
done
```

1. **`01_setup.sql`** — creates catalog `nimble_integration`, schemas `tools` + `examples`, and the UC HTTP `CONNECTION nimble_api` bound to the secret.
2. **`02_amazon_serp.sql`** — creates `nimble_integration.tools.amazon_serp(keyword)`. Wraps the [`amazon_serp` agent](https://docs.nimbleway.com/api-reference/agents/run-agent).

Smoke test:

```sql
SELECT size(nimble_integration.tools.amazon_serp('cookies')) AS n;  -- expect ~60
```

## Adding more Nimble functions

The folder layout is designed to grow one file per capability. To add e.g. `nimble_web_search`:

1. Create `03_nimble_web_search.sql` with the same header conventions as `02_amazon_serp.sql`:
   - Function lives under `nimble_integration.tools.<name>`.
   - `RETURNS ARRAY<STRUCT<...>>` matched to the agent's output schema.
   - `COMMENT '<verbatim agent description from Nimble docs>'` — this is what an LLM-driven Genie / agent reads to decide whether to call your function.
   - Body uses `http_request(conn => 'nimble_api', ...)` + `from_json(..., '<all-STRING schema>')` + `transform(...)` with `try_cast` into the declared numeric / boolean return types.
2. Add a sibling file under `examples/` with 2–3 queries demonstrating the new function.
3. That's it — no folder reshuffles, no shared boilerplate to update.

Planned next additions:
- `03_nimble_web_search.sql` — wraps `POST /v1/search` for general / news / shopping / academic search.
- `04_nimble_agent_list.sql` — wraps `GET /v1/agents` so callers can introspect available agents.

## Conventions

- **All DDL is re-runnable.** `CREATE OR REPLACE FUNCTION`, `CREATE SCHEMA IF NOT EXISTS`, `CREATE CONNECTION IF NOT EXISTS`.
- **One UC `CONNECTION` for all Nimble endpoints** (`nimble_api`). Each function picks the right `path => '/v1/agents/run'`, `'/v1/search'`, etc.
- **API key stays in `secret('nimble','api_key')`.** No plain-text tokens in function bodies or DDL.
- **Function COMMENT carries the agent description verbatim.** This is the surface area an LLM picks tools from.
- **Numeric / boolean fields are `try_cast`-ed** because Nimble agents ship them as JSON strings. The function's declared return type is the typed one users expect; the casting happens internally.
- **`tools` schema for functions, `examples` schema for sample tables.** Grant `EXECUTE` on `tools` to your readers; keep `examples` writable for experiments.

## Try it from a Genie / AI agent

Once `amazon_serp` exists, register it as a tool in any [Databricks Genie space](https://docs.databricks.com/en/genie/index.html) or [Mosaic AI agent](https://docs.databricks.com/en/generative-ai/agent-framework/index.html) by pointing at `nimble_integration.tools.amazon_serp`. The function's COMMENT is what the LLM reads to decide when to call it; ask:

> *"What are the top-rated wireless headphones on Amazon under $100? Show me 10."*

The agent will call `amazon_serp('wireless headphones')`, flatten the array, filter, and answer.

## Note on target-site terms of service

These recipes show how to pipe data fetched by Nimble into Databricks — they do not change the legal rules that govern *what* you fetch. You are responsible for ensuring that any queries you pass through these functions comply with the target sites' terms of service, robots policies, and applicable law in your jurisdiction.

## References

- Nimble API reference: <https://docs.nimbleway.com/api-reference/introduction>
- Databricks `http_request` SQL builtin: <https://docs.databricks.com/en/sql/language-manual/functions/http_request.html>
- Databricks `CREATE CONNECTION` (HTTP): <https://docs.databricks.com/en/connect/external-systems/index.html>
- Databricks Genie: <https://docs.databricks.com/en/genie/index.html>
- Databricks secrets CLI: <https://docs.databricks.com/en/security/secrets/secrets.html>
