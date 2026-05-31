# Helpers

Small, dependency-free utilities used by this recipe directory. Optional — every SQL file in `../` is human-runnable in the Databricks SQL editor without any helper.

## What's here

```
helpers/
  deploy_sql.py                  Split a multi-statement .sql file and POST each
                                 statement to /api/2.0/sql/statements via the
                                 `databricks` CLI.
  create_genie_space.py          Build a v2 serialized_space and POST to
                                 /api/2.0/genie/spaces to create an AI/BI Genie
                                 space referencing the UC tools in ../tools/.
  nimble_genie_instructions.md   Canonical system-prompt markdown for the
                                 "Nimble Web Data" Genie space (input to
                                 create_genie_space.py --instructions-file).
```

## `deploy_sql.py`

```bash
python databricks/helpers/deploy_sql.py \
    --file databricks/01_setup.sql \
    --warehouse <warehouse-id>             # uses default profile

python databricks/helpers/deploy_sql.py \
    --file databricks/tools/amazon_serp.sql \
    --warehouse <warehouse-id> \
    --profile my-profile
```

Why it exists: the Statement Execution API accepts **one** statement per call, and a plain `;`-split corrupts function COMMENT strings (which contain semicolons inside string literals). This script strips comments and splits while honoring `'...'` string literals and `''` apostrophe escapes.

Requirements: Python 3.9+, `databricks` CLI on `$PATH` and authenticated. No third-party Python packages.

Deploy everything in this directory:

```bash
WH=<your-serverless-warehouse-id>
for f in databricks/01_setup.sql databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

## `create_genie_space.py`

Creates a Databricks AI/BI Genie space programmatically. The public API
endpoint is `POST /api/2.0/genie/spaces`, but the body requires a
stringified `serialized_space` whose schema isn't documented externally —
this helper builds a minimal valid v2 space from a list of TABLE-returning
UC SQL functions and a markdown instructions file.

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

Notes:

- Every `sql_function` / `text_instruction` entry needs a 32-hex UUID
  `id` (no hyphens); the helper generates them.
- `instructions.sql_functions` must be sorted by `(id, identifier)` —
  the helper sorts before emitting.
- To inspect / export an existing space's `serialized_space` (no
  documented GET /export exists), use:
  `databricks api patch /api/2.0/genie/spaces/<id> --json '{}'` —
  returns the full serialized_space + an `etag` for optimistic updates.
