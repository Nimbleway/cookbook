# Adding a new Nimble tool

End-to-end recipe for exposing another Nimble API endpoint / agent as a UC **table function** in this directory. Every tool follows the same UDTF shape so users and LLM agents see a consistent surface.

## 1. Pick the Nimble endpoint

Start at <https://docs.nimbleway.com/api-reference/introduction>. Each API / agent has its own page with input / output schemas.

**Tip — fetch docs as Markdown:** append `.md` to any Nimble docs URL (e.g. `.../api-reference/agents/list-agents.md`) for the plain-text spec; the HTML pages are JS-rendered and don't read well via `WebFetch`.

Useful endpoint families:

- **Search** — `POST /v1/search`.
- **Extract** — `POST /v1/extract`.
- **Crawl** — `POST /v1/crawl`.
- **Agents** — `POST /v1/agents/run` (run by name), `GET /v1/agents` (catalog).

## 2. Decide the table shape

A tool is a table function: pick the columns each call should `yield`.

- Write down required + optional inputs, allowed values, and cross-param constraints (e.g. Nimble's `search_depth=fast` only works with `focus=general`).
- Pick the output columns and SQL types. One result → one row (e.g. extract a page); a list → one row per item (e.g. search results, agent catalog).
- Nimble agents often ship numeric / boolean fields as JSON **strings**; coerce them in Python (`int(...)`, a small `as_bool` helper) before yielding into typed columns.

## 3. Write the Python UDTF (`_<name>`)

Model it after `tools/nimble_search.sql`. The internal function does the HTTP call and yields rows. Key UDTF rules (all enforced by the platform):

- **`HANDLER '<ClassName>'` is required** for a Python table function.
- **`import` statements must live INSIDE `eval()`** — module-level imports in the `$$` body are not visible to the handler class (`NameError` at call time).
- The function **can't declare `DEFAULT`s** — all params (including `api_key`) are required; the SQL wrapper supplies defaults.
- On any error, **yield nothing** (don't raise) so a batch over many rows isn't aborted by one bad input.

```sql
CREATE OR REPLACE FUNCTION nimble_integration.tools._<name>(
    arg1 TYPE, arg2 TYPE, ..., api_key STRING
)
RETURNS TABLE(col1 STRING, col2 INT, ...)
LANGUAGE PYTHON
HANDLER 'Handler'
COMMENT 'Internal Python UDTF behind <name>(). Call the public <name>() wrapper instead.'
AS $$
class Handler:
    def eval(self, arg1, arg2, ..., api_key):
        import requests   # imports MUST be inside eval()
        headers = {"Authorization": "Bearer " + (api_key or ""),
                   "Content-Type": "application/json",
                   "X-Client-Source": "nimble-dbx-udtf"}
        try:
            resp = requests.post("https://sdk.nimbleway.com/v1/<endpoint>",
                                 json={...}, headers=headers, timeout=60)
            data = resp.json() if 200 <= resp.status_code < 300 else {}
        except Exception:
            data = {}
        for r in (data.get("results") or []):
            yield (r.get("col1"), r.get("col2"))
$$;
```

## 4. Write the public SQL wrapper (`<name>`)

A thin `RETURNS TABLE` wrapper that supplies DEFAULTs, injects the key via `secret()` (which passes straight through as a table-function argument), and carries the LLM-facing `COMMENT`s.

```sql
CREATE OR REPLACE FUNCTION nimble_integration.tools.<name>(
    arg1 TYPE COMMENT '<examples, allowed enums>',
    arg2 TYPE DEFAULT <value> COMMENT '<description, defaults, constraints>'
)
RETURNS TABLE(
    col1 STRING COMMENT '<plain English, NULL semantics>',
    col2 INT    COMMENT '...'
)
COMMENT '<long, example-question-rich description tuned for LLM tool selection>'
RETURN SELECT * FROM nimble_integration.tools._<name>(arg1, arg2, secret('nimble', 'api_key'));
```

The function `COMMENT` and per-column `COMMENT`s are what Genie reads to pick and summarize the tool — write them like a prompt.

## 5. Add example queries

Drop `recipes/<name>.sql` with 3–4 standalone-runnable patterns: simplest call, a filtered/paged variant, the expensive variant (deep mode / larger N), and a composition (`JOIN` / `CREATE TABLE … AS`).

## 6. Smoke test

```bash
WH=<warehouse-id>
python3 databricks/helpers/deploy_sql.py --file databricks/tools/<name>.sql --warehouse "$WH"

# Should return a non-zero row count.
echo "SELECT count(*) AS n FROM nimble_integration.tools.<name>(<example-args>);" > /tmp/probe.sql
python3 databricks/helpers/deploy_sql.py --file /tmp/probe.sql --warehouse "$WH"
```

If a Nimble validation error (HTTP 422) surfaces, the message is explicit (e.g. "search_depth='fast' is only supported with focus='general'") and usually means a DEFAULT param combination is invalid.

## 7. Gotchas & escape hatches

### Outbound networking must be enabled for the warehouse

UDTF egress on a serverless SQL warehouse is **off by default**. Enable the Preview **"Enable networking for isolated workloads in Serverless SQL Warehouses"** in the workspace Previews page and **cold-restart** the warehouse (Stop → Start; a plain restart isn't enough). Symptom of skipping it: DNS resolves but the request fails with `Connection refused` (Errno 111), so the tool returns zero rows. The account-level serverless egress **network policy** is a separate control and is usually already "allow all".

### `import` must be inside `eval()`

Module-level imports in the `$$` body are not in scope inside the handler class — you'll get `NameError: name 'requests' is not defined` at call time. Import inside `eval()`.

### UDTFs can't have DEFAULT parameter values

Put all DEFAULTs on the SQL wrapper; the Python UDTF takes every param (including `api_key`) as required.

### Yield-nothing vs raise

Raising inside `eval()` fails the whole query — bad for a batch CTAS over many inputs. These tools swallow errors and yield zero rows instead. If you'd rather a misconfiguration surface loudly, yield a sentinel error row or check counts in your pipeline.

### deploy_sql.py and `$$` bodies

`helpers/deploy_sql.py` treats `$$ … $$` dollar-quoted bodies as opaque, so the `;` / `'` / `--` inside a Python UDTF body don't corrupt statement splitting. If you hand-split SQL elsewhere, do the same.

### `secret()` is passed as an argument

The wrapper passes `secret('nimble','api_key')` straight into the UDTF as a normal argument — no in-UDF secret API is needed, and the value is redacted in plans/logs.

### Catalog creation on UC Default Storage workspaces

Plain `CREATE CATALOG IF NOT EXISTS nimble_integration` fails when the workspace uses UC account-level Default Storage without a metastore-level managed root. See the comment block in `01_setup.sql` for the UI / `MANAGED LOCATION` fallbacks.

### Optional fallback: `http_request()` instead of a UDTF

If a workspace can't enable UDTF egress (the Previews toggle above), the `http_request()` SQL builtin reaches the Nimble API through a different, always-on egress path — at the cost of `from_json` parsing in SQL and no per-row isolation. It needs a one-time UC HTTP `CONNECTION` (this is **not** created by `01_setup.sql`; requires the `CREATE CONNECTION` privilege):

```sql
CREATE CONNECTION IF NOT EXISTS nimble_api TYPE HTTP
OPTIONS (
    host         'https://sdk.nimbleway.com',
    port         '443',
    base_path    '/',
    bearer_token secret('nimble', 'api_key')
);
```

A fallback tool body then calls `http_request(conn => 'nimble_api', method => 'POST', path => '/v1/<endpoint>', headers => map('Content-Type','application/json'), json => to_json(named_struct(...)))`, gates on `response.status_code`, and parses `response.text` with `from_json`.
