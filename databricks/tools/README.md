# Tools

UC SQL functions wrapping individual Nimble agents / APIs. Each `.sql` file in here is **self-contained and re-runnable**: it declares one function, deploys with `CREATE OR REPLACE`, and depends only on `../01_setup.sql` (and possibly another file in this folder, when one tool builds on another).

## What's here

```
tools/
  amazon_serp.sql              scalar  amazon_serp(keyword) RETURNS ARRAY<STRUCT<...>>
  amazon_serp_table.sql        TABLE   amazon_serp_table(keyword) RETURNS TABLE(...)
                                       — required for Databricks Genie tool registration
  nimble_search.sql            scalar  nimble_search(query, ...) — Nimble Web Search API
  nimble_search_table.sql      TABLE   nimble_search_table(query, ...)
  nimble_agent_list.sql        scalar  nimble_agent_list(...) — catalog of Nimble agents
  nimble_agent_list_table.sql  TABLE   nimble_agent_list_table(...)
```

## Pattern for adding a new tool

1. Create `tools/<function_name>.sql`.
2. Header block: purpose, the agent / endpoint it wraps, prereqs, runtime, link to Nimble docs.
3. Define **both** signatures when you expect Genie / Mosaic-AI usage:
   - A scalar `RETURNS ARRAY<STRUCT<...>>` form — useful for direct SQL composition.
   - A `RETURNS TABLE(...)` wrapper — Genie can only register table functions as tools.
4. Function `COMMENT` is the LLM-facing spec. Write it like a prompt: state when to use the tool, what kinds of questions it answers, what each returned column means.
5. Body uses `http_request(conn => 'nimble_api', method => '...', path => '...', headers => map(...), json => to_json(named_struct(...)))` + `from_json(response.text, '<all-STRING schema>')` + `transform()` with `try_cast` for typed fields.
6. Add a sibling `.sql` (or several) under `../examples/` showing how to call the new tool.

## Deployment

After `../00_prereqs.md` + `../01_setup.sql`, run every file in this folder. Order between files only matters when one references another (e.g. `amazon_serp_table.sql` calls `amazon_serp`). All files are idempotent; re-running is safe.

```bash
WH=<your-serverless-warehouse-id>

# ../helpers/deploy_sql.py splits + posts a multi-statement SQL file
# correctly (function COMMENTs contain semicolons inside string literals).
for f in databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

## Registering with Databricks Genie

In your Genie space, add a tool referencing the **`*_table`** function (e.g. `nimble_integration.tools.amazon_serp_table`). Genie reads the function `COMMENT`, the input parameter doc, and the returned-column docs to decide when to call it and how to summarize the result.
