# Helpers

Small, dependency-free utilities used by this recipe directory. Optional — every SQL file in `../` is human-runnable in the Databricks SQL editor without any helper.

## What's here

```
helpers/
  deploy_sql.py    Split a multi-statement .sql file and POST each statement
                   to /api/2.0/sql/statements via the `databricks` CLI.
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
