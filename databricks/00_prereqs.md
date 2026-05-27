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

`databricks api post /api/2.0/sql/statements` lets you fire a statement at a SQL warehouse without leaving the shell.

**Caveat**: that endpoint accepts **one statement per call**, and a SQL-aware splitter is needed because `01_setup.sql` and the comment strings inside the function definitions contain semicolons. The snippet below uses Python to split statements while respecting `'...'` string literals; `sqlparse` would also work if you have it installed.

```bash
WH=<your-serverless-warehouse-id>     # databricks warehouses list

deploy() {
  local file="$1"
  python3 - "$file" "$WH" <<'PY'
import json, os, re, subprocess, sys
path, wh = sys.argv[1], sys.argv[2]
text = open(path).read()
# strip /* ... */ blocks
text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
# split on `;` while honoring '...' string literals (incl. '' escapes)
stmts, cur, in_str, i = [], [], False, 0
while i < len(text):
    c = text[i]
    if c == "'":
        if in_str and i+1 < len(text) and text[i+1] == "'":
            cur.append("''"); i += 2; continue
        in_str = not in_str; cur.append(c)
    elif not in_str and c == '-' and i+1 < len(text) and text[i+1] == '-':
        while i < len(text) and text[i] != '\n': i += 1
        continue
    elif c == ';' and not in_str:
        s = ''.join(cur).strip()
        if s: stmts.append(s)
        cur = []
    else:
        cur.append(c)
    i += 1
last = ''.join(cur).strip()
if last: stmts.append(last)
for s in stmts:
    body = json.dumps({'warehouse_id': wh, 'statement': s, 'wait_timeout': '50s'})
    subprocess.check_call(['databricks', 'api', 'post', '/api/2.0/sql/statements', '--json', body])
PY
}

deploy databricks/01_setup.sql
for f in databricks/tools/*.sql; do deploy "$f"; done
```

If your workspace uses UC **Default Storage** and the catalog creation in `01_setup.sql` fails with *"Metastore storage root URL does not exist"*, see the comment block in `01_setup.sql` — either create the catalog from the Databricks UI (Catalog Explorer → Create Catalog → Default Storage) or use the explicit `MANAGED LOCATION` form pointed at one of your existing UC external locations (`SHOW EXTERNAL LOCATIONS`).

Smoke test:

```bash
databricks api post /api/2.0/sql/statements \
  --json "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT size(nimble_integration.tools.amazon_serp('cookies')) AS n\",\"wait_timeout\":\"50s\"}"
```

Expect `"n": "60"` (give or take, depending on Amazon's live results).
