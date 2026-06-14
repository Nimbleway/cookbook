# INSTALL — one-time Databricks setup & deploy

The complete install path for this cookbook: CLI auth, the networking Preview, the secret scope, then deploying the SQL files. Run once per workspace. Most steps are `bash` against the [Databricks CLI v0.205+](https://docs.databricks.com/en/dev-tools/cli/install.html). After this, the SQL files in `01_setup.sql` and beyond can be deployed by anyone with `CREATE SCHEMA` and `CREATE FUNCTION` privileges on the target catalog.

## 1. Authenticate the CLI

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
# follow the browser prompt; creates / refreshes the profile in ~/.databrickscfg
databricks auth profiles      # confirm the profile shows Valid = YES
```

If you have multiple profiles, prepend `--profile <name>` to every command below.

## 1.5 Enable outbound networking for the SQL warehouse (required)

The Nimble tools are Python **UDTFs** that call the Nimble API over HTTPS. A serverless SQL warehouse blocks UDF/UDTF egress by default, so two one-time steps are required:

1. **Workspace Previews** → enable **"Enable networking for isolated workloads in Serverless SQL Warehouses."**
2. **Cold-restart the warehouse** — fully **Stop** it, then **Start** it. A plain "restart" is not enough; the new network config is only picked up on a cold start.

Symptom of skipping this: a Nimble tool returns zero rows and the underlying request fails with `Connection refused` (Errno 111) even though DNS resolves. (The serverless egress *network policy* is a separate, account-level control and is usually already "allow all" — it is not this setting.)

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

If you prefer to limit access to a group, replace `users` with a Databricks group name; everyone outside that group will get `PERMISSION_DENIED` when they try to call the Nimble functions.

## 4. Verify

```bash
databricks secrets list-scopes | grep nimble
# nimble    DATABRICKS

databricks secrets list-secrets nimble
# api_key

databricks secrets list-acls nimble
# users    READ
```

## 5. Deploy the SQL files

This is the canonical deploy path (you can also paste each file into a Databricks SQL editor by hand). `databricks api post /api/2.0/sql/statements` fires a statement at a SQL warehouse without leaving the shell. That endpoint accepts **one statement per call**, and the SQL files in this directory contain multiple statements plus function COMMENTs that legitimately include `;` inside string literals. The repo ships a tiny helper that splits + posts correctly:

```bash
# Grab a warehouse id automatically (first one); or set WH explicitly. Needs jq.
WH=$(databricks warehouses list -o json | jq -r '.[0].id')

for f in databricks/01_setup.sql databricks/tools/*.sql; do
    python3 databricks/helpers/deploy_sql.py --file "$f" --warehouse "$WH"
done
```

Pass `--profile <name>` only if you have multiple Databricks CLI profiles and want a non-default one. See the docstring in [`helpers/deploy_sql.py`](helpers/deploy_sql.py) for details.

If your workspace uses UC **Default Storage** and the catalog creation in `01_setup.sql` fails with *"Metastore storage root URL does not exist"*, see the comment block in `01_setup.sql` — either create the catalog from the Databricks UI (Catalog Explorer → Create Catalog → Default Storage) or use the explicit `MANAGED LOCATION` form pointed at one of your existing UC external locations (`SHOW EXTERNAL LOCATIONS`).

Smoke test:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT count(*) AS n FROM nimble_integration.tools.nimble_search('AI agents news', 5)\",\"wait_timeout\":\"50s\"}"
```

Expect a non-zero `n` (live search result count). If `n` is 0, re-check step 1.5 (the Previews toggle + cold restart).
