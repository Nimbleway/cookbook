# 00_prereqs — one-time Databricks CLI setup

Everything below is `bash` against the [Databricks CLI v0.205+](https://docs.databricks.com/en/dev-tools/cli/install.html). Run once per workspace. After this, the SQL files in `01_setup.sql` and beyond can be deployed by anyone with `CREATE CONNECTION` and `CREATE SCHEMA` privileges.

## 1. Authenticate the CLI

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
# follow the browser prompt; creates / refreshes the profile in ~/.databrickscfg
databricks auth profiles      # confirm the profile shows Valid = YES
```

If you have multiple profiles, prepend `--profile <name>` to every command below.

## 2. Create the secret scope and store the Nimble API key

```bash
# Scope holding all Nimble-related secrets for this workspace.
databricks secrets create-scope nimble

# Paste the raw bearer token (NOT prefixed with "Bearer "), then Ctrl-D.
databricks secrets put-secret nimble api_key

# Alternative one-liner (leaves the token in shell history — avoid in shared shells):
# databricks secrets put-secret nimble api_key --string-value 'YOUR_NIMBLE_TOKEN'
```

Get a token at <https://online.nimbleway.com/account-settings/api-keys>.

## 3. Grant `READ` to all workspace users

```bash
databricks secrets put-acl nimble users READ
```

This lets every workspace user *call* `secret('nimble','api_key')` from SQL — values come back **redacted** in any display or log, so they can't extract the plaintext.

If you prefer to limit access to a group, replace `users` with a Databricks group name; everyone outside that group will get `PERMISSION_DENIED` when they try to call `amazon_serp(...)`.

## 4. Verify

```bash
databricks secrets list-scopes | grep nimble
# nimble    DATABRICKS

databricks secrets list-secrets nimble
# api_key

databricks secrets list-acls nimble
# users    READ
```

## 5. (Optional) Run the SQL deploys from the CLI

`databricks api post /api/2.0/sql/statements` lets you fire a statement at a SQL warehouse without leaving the shell. That endpoint accepts **one statement per call**, and the SQL files in this directory contain multiple statements plus function COMMENTs that legitimately include `;` inside string literals. The repo ships a tiny helper that splits + posts correctly:

```bash
WH=<your-serverless-warehouse-id>     # databricks warehouses list

python3 databricks/helpers/deploy_sql.py --file databricks/01_setup.sql --warehouse "$WH"

for f in databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

Pass `--profile <name>` if your authenticated Databricks CLI profile isn't `DEFAULT`. See [`helpers/README.md`](helpers/README.md) for details.

If your workspace uses UC **Default Storage** and the catalog creation in `01_setup.sql` fails with *"Metastore storage root URL does not exist"*, see the comment block in `01_setup.sql` — either create the catalog from the Databricks UI (Catalog Explorer → Create Catalog → Default Storage) or use the explicit `MANAGED LOCATION` form pointed at one of your existing UC external locations (`SHOW EXTERNAL LOCATIONS`).

Smoke test:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT size(nimble_integration.tools.amazon_serp('cookies')) AS n\",\"wait_timeout\":\"50s\"}"
```

Expect `"n": "60"` (give or take, depending on Amazon's live results).
