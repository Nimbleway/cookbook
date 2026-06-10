# Databricks × Nimble: Live Web Data as SQL Functions

A runnable recipe directory that turns a fresh Databricks workspace into a live-web data platform: Unity-Catalog SQL functions backed by Nimble's agents and APIs, callable from any SQL query, notebook, dashboard, or Databricks Genie agent.

## What's in here

```
databricks/
  README.md                          ← you are here
  00_prereqs.md                      one-time CLI setup: secret scope + ACL
  01_setup.sql                       catalog, schemas, UC HTTP CONNECTION
  NIMBLE_ENDPOINTS.md                map of Nimble API endpoints -> UC tools
  ADDING_A_TOOL.md                   walkthrough for wrapping a new endpoint
  tools/                             one SQL file per UC function — installable as-is
    README.md                        conventions for adding a new tool
    amazon_serp.sql                  scalar amazon_serp(keyword) RETURNS ARRAY<STRUCT<...>>
    amazon_serp_table.sql            TABLE wrapper required for Databricks Genie
    nimble_search.sql                scalar nimble_search(query, ...) — Web Search API
    nimble_search_table.sql          TABLE wrapper for the Search API
    nimble_agent_list.sql            scalar nimble_agent_list(...) — agent catalog
    nimble_agent_list_table.sql      TABLE wrapper for the agent catalog
    nimble_agent_describe.sql        scalar nimble_agent_describe(agent) — input/output schema
    nimble_agent_describe_table.sql  TABLE wrapper for agent introspection
    nimble_agent_run.sql             scalar nimble_agent_run(agent, params_json, ...) — generic runner
    nimble_agent_run_table.sql       TABLE wrapper for the generic runner
  examples/
    README.md                        what's in this folder
    amazon_serp_basic.sql            single call, EXPLODE, filter
    amazon_serp_keyword_table.sql    keyword-table-driven loader
    amazon_serp_aggregates.sql       average price, prime ratio, top-N
    nimble_search_basic.sql          search + focus + deep-mode examples
    nimble_agent_list_basic.sql      list catalog, filter, include community
    nimble_agent_describe_basic.sql  describe an agent's inputs / outputs / flags
    nimble_agent_run_basic.sql       generic agent runner, parse JSON output
  helpers/
    README.md                        what's in this folder
    deploy_sql.py                    split multi-statement .sql and POST via the CLI
    create_genie_space.py            build a v2 serialized_space and create a Genie
                                     space via /api/2.0/genie/spaces
    nimble_genie_instructions.md     canonical system-prompt for the Nimble Genie space
```

Three artifact types, three audiences:

- **`01_setup.sql`** — a workspace admin runs once to provision catalog, schemas, and the UC HTTP CONNECTION.
- **`tools/*.sql`** — install one per Nimble capability you want callable from SQL / Genie / agents. Re-runnable, independent of each other (except where one tool wraps another, e.g. `amazon_serp_table` calls `amazon_serp`).
- **`examples/*.sql`** — a data analyst or agent runs these to learn the pattern and adapt it.

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

# Statement Execution API accepts one statement per call, and our function
# COMMENTs contain semicolons inside string literals. databricks/helpers/
# deploy_sql.py splits + posts correctly. See helpers/README.md for detail.

python3 databricks/helpers/deploy_sql.py --file databricks/01_setup.sql --warehouse "$WH"
for f in databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

1. **`01_setup.sql`** — creates catalog `nimble_integration`, schemas `tools` + `examples`, and the UC HTTP `CONNECTION nimble_api` bound to the secret.
2. **`tools/amazon_serp.sql`** — creates the scalar `nimble_integration.tools.amazon_serp(keyword)`. Wraps the [`amazon_serp` agent](https://docs.nimbleway.com/api-reference/agents/run-agent).
3. **`tools/amazon_serp_table.sql`** — creates the Genie-friendly TABLE form `nimble_integration.tools.amazon_serp_table(keyword)`. Wraps the scalar with `LATERAL VIEW EXPLODE` so Genie can register it as a tool.

Smoke tests:

```sql
SELECT size(nimble_integration.tools.amazon_serp('cookies')) AS n;          -- expect ~60
SELECT * FROM nimble_integration.tools.amazon_serp_table('cookies') LIMIT 5;
```

## Adding more Nimble functions

See [`ADDING_A_TOOL.md`](ADDING_A_TOOL.md) for the full walkthrough — pick a Nimble endpoint, extract the schema, write the scalar + TABLE wrapper, add examples, smoke-test, and the known limitations you'll hit along the way.

Quick summary:

1. Create `tools/nimble_web_search.sql` following the header conventions in `tools/amazon_serp.sql`:
   - Function lives under `nimble_integration.tools.<name>`.
   - Scalar form `RETURNS ARRAY<STRUCT<...>>` matched to the agent's output schema.
   - `COMMENT '<verbatim agent description from Nimble docs>'`.
   - Body uses `http_request(conn => 'nimble_api', ...)` + `from_json(..., '<all-STRING schema>')` + `transform(...)` with `try_cast` into the declared numeric / boolean return types.
2. If the tool is meant to be Genie-callable, add `tools/nimble_web_search_table.sql` — a TABLE wrapper around the scalar, with rich per-column `COMMENT`s.
3. Add a sibling file under `examples/` with 2–3 queries demonstrating the new function.
4. That's it — no folder reshuffles, no shared boilerplate to update.

See [`NIMBLE_ENDPOINTS.md`](NIMBLE_ENDPOINTS.md) for the live map of which Nimble endpoints have shipped UC wrappers and which are still planned.

## Conventions

- **All DDL is re-runnable.** `CREATE OR REPLACE FUNCTION`, `CREATE SCHEMA IF NOT EXISTS`, `CREATE CONNECTION IF NOT EXISTS`.
- **One UC `CONNECTION` for all Nimble endpoints** (`nimble_api`). Each function picks the right `path => '/v1/agents/run'`, `'/v1/search'`, etc.
- **API key stays in `secret('nimble','api_key')`.** No plain-text tokens in function bodies or DDL.
- **Function COMMENT carries the agent description verbatim.** This is the surface area an LLM picks tools from.
- **Numeric / boolean fields are `try_cast`-ed** because Nimble agents ship them as JSON strings. The function's declared return type is the typed one users expect; the casting happens internally.
- **`tools` schema for functions, `examples` schema for sample tables.** Grant `EXECUTE` on `tools` to your readers; keep `examples` writable for experiments.

## Try it from a Genie / AI agent

Once `amazon_serp_table` exists, register it as a tool in any [Databricks Genie space](https://docs.databricks.com/en/genie/index.html) or [Mosaic AI agent](https://docs.databricks.com/en/generative-ai/agent-framework/index.html) by pointing at `nimble_integration.tools.amazon_serp_table`. Genie only registers TABLE functions, which is why the table wrapper exists alongside the scalar. The function's COMMENT (and the per-column COMMENTs in the return schema) is what the LLM reads to decide when to call it; ask:

> *"What are the top-rated wireless headphones on Amazon under $100? Show me 10."*

The agent will call `amazon_serp('wireless headphones')`, flatten the array, filter, and answer.

### Create the Genie space programmatically

The public `POST /api/2.0/genie/spaces` endpoint requires a stringified `serialized_space` whose schema isn't documented externally. `helpers/create_genie_space.py` builds a minimal valid v2 payload from a list of `_table` functions and a markdown instructions file:

```bash
WH=<your-serverless-warehouse-id>
python3 databricks/helpers/create_genie_space.py \
    --title "Nimble Web Data" \
    --warehouse "$WH" \
    --parent-path "/Users/you@example.com" \
    --instructions-file databricks/helpers/nimble_genie_instructions.md \
    --function nimble_integration.tools.nimble_agent_list_table \
    --function nimble_integration.tools.nimble_agent_describe_table \
    --function nimble_integration.tools.nimble_agent_run_table \
    --function nimble_integration.tools.nimble_search_table \
    --function nimble_integration.tools.amazon_serp_table
```

See [`helpers/README.md`](helpers/README.md) for the inspect / export trick (`databricks api patch /api/2.0/genie/spaces/<id> --json '{}'` returns the full `serialized_space` + an `etag`).

## Note on target-site terms of service

These recipes show how to pipe data fetched by Nimble into Databricks — they do not change the legal rules that govern *what* you fetch. You are responsible for ensuring that any queries you pass through these functions comply with the target sites' terms of service, robots policies, and applicable law in your jurisdiction.

## References

- Nimble API reference: <https://docs.nimbleway.com/api-reference/introduction>
- Databricks `http_request` SQL builtin: <https://docs.databricks.com/en/sql/language-manual/functions/http_request.html>
- Databricks `CREATE CONNECTION` (HTTP): <https://docs.databricks.com/en/connect/external-systems/index.html>
- Databricks Genie: <https://docs.databricks.com/en/genie/index.html>
- Databricks secrets CLI: <https://docs.databricks.com/en/security/secrets/secrets.html>
