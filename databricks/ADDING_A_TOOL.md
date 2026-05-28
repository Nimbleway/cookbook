# Adding a new Nimble tool

End-to-end recipe for exposing another Nimble agent / API endpoint as a UC SQL function in this directory. Follow the same structure for every new tool so users and LLM agents see a consistent surface.

## 1. Pick the Nimble endpoint

Start at <https://docs.nimbleway.com/api-reference/introduction>. Each agent / API has its own page with input / output schemas.

**Tip — fetch docs as Markdown:** append `.md` to any Nimble docs URL to get the plain-text version (e.g. `https://docs.nimbleway.com/api-reference/agents/list-agents.md`). The HTML pages are JS-rendered and don't work well with `WebFetch`; the `.md` variant returns the raw OpenAPI-derived spec.

Useful endpoint families:

- **Agents** — `POST /v1/agents/run`, with `agent` = `amazon_serp` / `amazon_pdp` / `homedepot_serp` / `linkedin_company_details` / ... See the full list at `GET /v1/agents?managed_by=nimble`.
- **Search** — `POST /v1/search`.
- **Extract** — `POST /v1/extract`.
- **Crawl** — `POST /v1/crawl`.
- **Batches** — `POST /v1/agents/batch` + `GET /v1/batches/{id}` + `GET /v1/batches/{id}/progress`.

Pick something with a clear input/output and a real Genie / dashboard use case.

## 2. Extract input and output schema

For an agent: `GET /v1/agents/<agent_name>` returns the full schema. `input_properties[]` lists params with type / required / examples; `output_schema` maps each result field.

For the Search / Extract / Crawl APIs: docs site has the request and response shapes inline.

Write down for the new tool:

- Function name (lowercase snake_case, matches the endpoint where possible: `nimble_search`, `nimble_extract`, `amazon_pdp`).
- Required inputs + per-input description + allowed values + cross-param constraints (e.g. Nimble's `search_depth=fast` only works with `focus=general`).
- Output fields + SQL types you want callers to see. Note that Nimble agents ship numeric / boolean fields as JSON **strings** ("price":"23.76", "sponsored":"true") — they need `try_cast` to the declared types.

## 3. Create the scalar SQL UDF

Drop a new file under `tools/<function_name>.sql`. Model it after `tools/amazon_serp.sql` or `tools/nimble_search.sql`:

```sql
CREATE OR REPLACE FUNCTION nimble_integration.tools.<name>(
    arg1 TYPE COMMENT '<example values, allowed enums>',
    arg2 TYPE DEFAULT <value> COMMENT '<description, defaults, constraints>'
)
RETURNS ARRAY<STRUCT<
    field1: STRING,
    field2: DOUBLE,
    ...
>>
COMMENT '<verbatim agent description from Nimble docs, escape '' as ''''>'
RETURN (
    SELECT COALESCE(
        transform(
            from_json(
                response.text,
                'STRUCT<<path to results array>: ARRAY<STRUCT< ...all-STRING schema... >>>'
            )<path>,
            x -> named_struct(
                'field1', x.field1,
                'field2', try_cast(x.field2 AS DOUBLE),
                ...
            )
        ),
        ARRAY()
    )
    FROM (
        SELECT http_request(
            conn    => 'nimble_api',
            method  => 'POST',
            path    => '/v1/<endpoint>',
            headers => map('Content-Type', 'application/json'),
            json    => to_json(named_struct('arg1', arg1, 'arg2', arg2))
        ) AS response
    )
);
```

Notes:

- The `from_json` schema uses **all-STRING** fields; the outer `transform()` does the `try_cast` to your declared return types. This is because Nimble returns numeric / boolean as strings.
- `to_json(named_struct(...))` happily serializes `NULL` values as JSON `null`. Most Nimble endpoints treat that as "use server default", so optional params can be `DEFAULT NULL` without a conditional struct builder.
- Stay aligned with the `nimble_api` HTTP CONNECTION already declared in `01_setup.sql` — every tool should use it; never embed bearer tokens in the function body.

## 4. Create the Genie-callable TABLE wrapper

Drop `tools/<function_name>_table.sql`. Genie only registers `RETURNS TABLE(...)` functions; the wrapper exposes the scalar's array row-by-row. Model after `tools/amazon_serp_table.sql`:

```sql
CREATE OR REPLACE FUNCTION nimble_integration.tools.<name>_table(
    arg1 TYPE COMMENT '<example, examples, examples>',
    ...
)
RETURNS TABLE(
    field1 STRING COMMENT '<plain English, mention NULL semantics>',
    field2 DOUBLE COMMENT '...',
    ...
)
COMMENT '<long, example-question-rich description tuned for LLM tool selection>'
RETURN (
    WITH raw AS (SELECT nimble_integration.tools.<name>(arg1, ...) AS arr)
    SELECT item.* FROM raw LATERAL VIEW EXPLODE(arr) items AS item
);
```

Per-column COMMENTs matter as much as the function-level COMMENT — Genie summarizes results using them.

## 5. Add example queries

Under `examples/<function_name>_basic.sql`, show 3–5 patterns. Look at `examples/amazon_serp_basic.sql` or `examples/nimble_search_basic.sql` for the conventional structure:

1. Simplest table-form call.
2. Variant with a focus / filter / paging parameter.
3. Variant exercising the more expensive option (deep mode, larger N, etc.).
4. Scalar form with `WITH … LATERAL VIEW EXPLODE` — for callers who want to compose in SQL.

Each query must be standalone runnable after the prereqs comment at the top.

## 6. Smoke test

After `01_setup.sql` is deployed and the new `tools/<name>.sql` + `tools/<name>_table.sql` are deployed, run a quick sanity check via `helpers/deploy_sql.py` and a follow-up `SELECT`:

```bash
WH=<warehouse-id>

# Deploy the two new files.
python3 databricks/helpers/deploy_sql.py --file databricks/tools/<name>.sql        --warehouse "$WH"
python3 databricks/helpers/deploy_sql.py --file databricks/tools/<name>_table.sql  --warehouse "$WH"

# Sanity test — should return a non-zero row count.
cat > /tmp/probe.sql <<SQL
SELECT count(*) AS n
FROM nimble_integration.tools.<name>_table(<example-args>);
SQL
python3 databricks/helpers/deploy_sql.py --file /tmp/probe.sql --warehouse "$WH"
```

If the test errors with HTTP 422 / validation, check the message — Nimble validation errors are explicit (e.g. "search_depth='fast' is only supported with focus='general'") and almost always indicate a param combination your DEFAULTs ship by accident.

## 7. Known limitations & escape hatches

These show up while wiring new tools; remember them rather than rediscovering each time. The cookbook chose option (a) for every tool so far; (b) is a real alternative when (a) is the wrong fit.

### `http_request()` "Can not start an object" error on multi-row Delta sources

When a query reads keywords / inputs from a managed table and passes them per-row to `http_request()`, the planner parallelizes and the response struct stream is corrupted with a Jackson parse error. `/*+ COALESCE(1) */` / `REPARTITION(1)` / `ORDER BY` / `collect_list+EXPLODE` / `transform()` lambda — none reliably fix it. Workarounds:

- (a) **Per-row INSERT loop** (one statement per keyword, via `helpers/deploy_sql.py` or a SQL stored procedure with `FOR rec IN (...) DO INSERT ...`). Each statement plans for a single literal — no parallelism, no bug. This cookbook uses this pattern.
- (b) Use the **Python-UDF flavour** of the tool. UC Python UDFs avoid the http_request planner path entirely. They have their own restrictions (next item) but they work over Delta multi-row scans.

### UC Python UDFs blocked from outbound HTTP on Serverless SQL

`requests.post(...)` from a UC Python UDF on a serverless SQL warehouse returns `ConnectionError [Errno 111] Connection refused`. The serverless sandbox has no outbound network. Workarounds:

- (a) **Pure SQL via `http_request()` and the UC HTTP CONNECTION** — works on serverless. This cookbook uses this pattern.
- (b) **Switch the SQL warehouse to classic (DBR-backed) compute.** DBR Python UDFs can reach the network. Trade-off: slower warm-up, higher per-query cost than serverless. Useful if you specifically need the Python-UDF flavour to sidestep the http_request multi-row bug above.

### UC Python UDFs reject DEFAULT parameter values

`UDF_UNSUPPORTED_PARAMETER_DEFAULT_VALUE`. SQL UDFs (`LANGUAGE SQL`) accept DEFAULTs. If a tool absolutely needs Python (e.g. complex parsing), wrap the Python UDF in a thin SQL UDF that injects the defaults / secrets and forwards.

### Function in Generate (EXPLODE) is forbidden

`SELECT EXPLODE(some_udf(...))` errors with "Using SQL function in Generate is not supported." Always materialize via a CTE first:

```sql
WITH r AS (SELECT some_udf(...) AS items)
SELECT item.* FROM r LATERAL VIEW EXPLODE(items) t AS item;
```

### Catalog creation on UC Default Storage workspaces

Plain `CREATE CATALOG IF NOT EXISTS nimble_integration` fails when the workspace uses UC account-level Default Storage without a metastore-level managed root. The cookbook keeps the simple SQL form as the default because most workspaces work fine with it; see the comment block in `01_setup.sql` for the UI / `MANAGED LOCATION` / REST-API fallbacks.

### GET query params must use the `params` map, not the path

`http_request(method => 'GET', path => '/v1/agents?managed_by=nimble', ...)` returns HTTP 404 — the UC HTTP connection does not parse a query string embedded in `path`. Use the dedicated `params` argument instead:

```sql
http_request(
    conn    => 'nimble_api',
    method  => 'GET',
    path    => '/v1/agents',
    params  => map_filter(
        map('managed_by', managed_by, 'limit', cast(max_results AS STRING)),
        (k, v) -> v IS NOT NULL
    ),
    headers => map('Content-Type', 'application/json')
)
```

`map_filter` drops NULL values so optional filters can be omitted by passing NULL. Note that `params` is `MAP<STRING, STRING>` — cast `INT` params explicitly.

### Statement Execution API: 50s wait cap

For statements that may exceed 50 seconds (e.g. CTAS over a slow function), submit with `wait_timeout=0s` and poll `GET /api/2.0/sql/statements/{id}` until terminal. The `helpers/deploy_sql.py` uses 50s synchronously, which suits the per-row INSERT pattern; rework if you need long-running deploys.
