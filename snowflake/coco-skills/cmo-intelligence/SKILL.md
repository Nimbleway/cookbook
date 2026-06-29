---
name: cmo-intelligence
description: |
  Provisions a complete in-tenant digital-shelf / CMO intelligence app in Snowflake from live Nimble
  web data, natively in Cortex Code, end to end: a conversational intake (name a category, optionally a
  brand), then it stands up the per-app schema, config tables, UDTF ingestion Task, brand resolver,
  analytics views, a governed semantic view, a Cortex agent, and a branded Streamlit cockpit — and the
  app stays updatable after creation (add a keyword = insert a row). Use whenever someone wants to
  stand up retail/brand shelf intelligence inside Snowflake — e.g. "build a digital-shelf app for
  Acme", "set up CMO intelligence for the coffee category", "provision a pricing + share-of-shelf
  cockpit for my brand", "monitor our category on Walmart/Amazon/Target in Snowflake". Runs entirely on
  SQL + the Nimble NIMBLE_AGENT_RUN UDTF + Streamlit-in-Snowflake — no CLI, no shell. Do NOT use for
  one-off web fetches with no Snowflake destination, or generic Snowflake work with no live-web angle.
---

# CMO Intelligence — provision a digital-shelf app in Snowflake (Cortex Code)

Turn a brief like `set up CMO intelligence for the chocolate category, focal brand Acme` into a
working, in-tenant intelligence app: **intake (conversational) → provision the data foundation (SQL)
→ stand up the surfaces (a Cortex agent + a branded Streamlit cockpit) → seed, schedule, verify.**
Nothing leaves the customer's Snowflake account.

You provision by **running the template files in `sql/` + `assets/` in order**, substituting the
per-app placeholders. There is **no `nimble` CLI and no shell** — Nimble web data comes in through the
`NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN` UDTF for SERP (a lateral join, ideal at low call counts)
and a concurrent `REFRESH_PDP` stored proc for the high-volume PDP fan-out (the standard pattern for
hundreds of calls) — and the cockpit is Streamlit-in-Snowflake.

## Golden rules

- **Gate, then offer guided install — never silent.** The account-level integration (role, EAI,
  secret, warehouse, `NIMBLE_AGENT_RUN`) is a one-time `ACCOUNTADMIN` install. The skill **bundles** it
  (`assets/integration/`), so if it's missing and the user is `ACCOUNTADMIN` and consents and supplies
  their Nimble API key, install it for them (Phase 0). If the user isn't admin, stop and point them at
  the bundled files / the cookbook (<https://github.com/Nimbleway/cookbook/tree/main/snowflake>). Only
  ever install with explicit consent + the user's key — never silently.
- **Intake is a conversation, derive the rest.** Ask for the minimum (a category; a brand is
  optional). Use Cortex to propose keywords / focal patterns (the "category architect"
  in `references/intake.md`), then **show the proposal and get explicit confirmation** before building.
- **Config is the source of truth.** Write the confirmed intake into `CFG_APP` + `CFG_QUERIES`; the
  views and the Task read those. Never bake brand/keywords/geo into DDL — that's what keeps the app
  updatable after creation.
- **One app = one schema; never clobber a live app.** Each provision targets its own `<db>.<schema>`.
  Before building, check whether the schema already exists (Phase 0) and let the user choose new /
  update / rebuild — re-provisioning over a live app is only allowed as an explicit, `DROP`-first rebuild.
- **Substitute every placeholder.** `__DB__`, `__SCHEMA__`, `__WAREHOUSE__`, `__BRAND__`,
  `__CATEGORY__`, `__AGENT_NAME__`, `__REFRESH_CRON__`, `__CORTEX_MODEL__`, `__CORTEX_MODEL_CHEAP__` must all be replaced before running a file.
  For a category-overview app (no focal brand), see the no-brand note in `references/intake.md`.
  **Escape quotes in substituted values** for the context: in a single-quoted SQL literal double the
  apostrophe (`'` → `''`); in JSON (the agent's `display_name`) drop or `\`-escape a `"`. `agent.sql`
  dollar-quotes its literals so apostrophe brands (e.g. `Brand's`) are already safe.
- **Probe one agent call before trusting projections.** Field names inside `parsing` differ per WSA.
  `amazon_serp` is verified; confirm `walmart_serp` / `target_serp` / `*_pdp` once with
  `SELECT raw FROM TABLE(NIMBLE_AGENT_RUN(...))` and adjust `ingest.sql` if they differ.
- **Branding is on, neutral.** The cockpit ships pre-branded (light theme, "Powered by Nimble"
  credit). Keep the credit intact; don't re-theme unless the user asks.
- **End with the two links + one headline.** The cockpit URL, the agent name, and the one-line
  takeaway (e.g. the focal brand's share of shelf).

## Workflow

Track these as todos so nothing is skipped.

### Phase 0 — Preflight (SQL only)
1. `SELECT CURRENT_ROLE(), CURRENT_ACCOUNT();`
2. **Integration gate** — confirm the UDTF exists:
   ```sql
   SHOW FUNCTIONS LIKE 'NIMBLE_AGENT_RUN' IN SCHEMA NIMBLE_INTEGRATION.TOOLS;
   ```
   **If present →** version-check (step 2a). **If missing →** offer to install it (don't dead-end at a link):
   - Check rights: `SELECT CURRENT_AVAILABLE_ROLES();` — is `ACCOUNTADMIN` available?
   - **Admin + consent → guided install (the skill carries the SQL).** Confirm with the user, then ask
     for their **Nimble API key** (get one at <https://online.nimbleway.com/account-settings/api-keys>).
     Run `assets/integration/setup.sql` with `<<YOUR_NIMBLE_API_KEY>>` replaced by that key
     (`USE ROLE ACCOUNTADMIN` first), then `assets/integration/nimble_agent_run.sql`, then re-run the
     `SHOW FUNCTIONS` check. The key goes only into the Snowflake `SECRET` — never echo or log it.
   - **No `ACCOUNTADMIN` → STOP.** It's an account-level install; tell the user an admin must run the
     two files, pointing at the bundled `assets/integration/` (or the cookbook,
     <https://github.com/Nimbleway/cookbook/tree/main/snowflake>).
   - **Never install silently** — always require explicit consent + the user-supplied key.
2a. **Version gate (detect, recommend — never force).** The integration is a *shared, account-level*
   primitive; the skill must not silently overwrite it. Read the installed version and compare to the
   version this skill bundles (see `assets/integration/README.md` — currently **`1.0.0`**):
   ```sql
   SELECT version FROM NIMBLE_INTEGRATION.TOOLS.INTEGRATION_VERSION;  -- errors if the account predates versioning
   ```
   - **Missing view or older than the bundled version →** tell the user the install is stale (show both
     versions) and **recommend** upgrading from the canonical cookbook
     (<https://github.com/Nimbleway/cookbook/tree/main/snowflake>). Only re-run the bundled
     `setup.sql` + `nimble_agent_run.sql` (`ACCOUNTADMIN`) on **explicit consent** — and warn that the
     bundle may itself be behind the cookbook, so the cookbook is the source of truth. Never auto-upgrade.
   - **Equal or newer →** continue.
2b. **Resolve the Cortex models → `__CORTEX_MODEL__` + `__CORTEX_MODEL_CHEAP__`.** The skill calls
   Cortex via `AI_COMPLETE` (the GA AISQL function; `SNOWFLAKE.CORTEX.COMPLETE` is its legacy
   namespace). It uses **two** models, since availability is region-dependent — probe in preference
   order and bind the first that returns:
   - **`__CORTEX_MODEL__`** — the **reasoning** model for the intake architect and cockpit chat; pick
     the latest Sonnet the account answers to:
   ```sql
   SELECT AI_COMPLETE('claude-sonnet-4-6', 'ping');  -- newest Sonnet; else ↓
   -- on "model … not available in region" / unknown-model, try the next:
   --   claude-sonnet-4-5   (broader regional availability)
   --   mistral-large       (last-resort fallback — always available)
   ```
   - **`__CORTEX_MODEL_CHEAP__`** — a **cheap, fast** model for the high-volume brand-normalization
     resolver (runs over ~60 brands every refresh). Prefer Haiku; fall back to the reasoning model so
     the resolver never breaks:
   ```sql
   SELECT AI_COMPLETE('claude-haiku-4-5', 'ping');  -- cheapest capable; else fall back to __CORTEX_MODEL__
   ```
   Substitute each value everywhere its placeholder appears (`__CORTEX_MODEL__`: `references/intake.md`
   + the cockpit; `__CORTEX_MODEL_CHEAP__`: the `REBUILD_BRAND_MAP` resolver in `sql/views.sql`).
   If the user wants the newest but it's not native to the region, mention enabling cross-region
   inference: `ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';` (needs `ACCOUNTADMIN`).
   Authoritative model list: <https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-regional-availability>.
3. **Confirm targets.** Recommend a target database + a warehouse (defaults: `NIMBLE_INTEGRATION` /
   `NIMBLE_AGENT_WH`). Cortex Agents must be enabled on the account for the agent step.
   **If the target DB is not `NIMBLE_INTEGRATION`** (which `NIMBLE_ROLE` owns), grant `NIMBLE_ROLE`
   schema-creation on it once as `ACCOUNTADMIN`:
   ```sql
   GRANT USAGE, CREATE SCHEMA ON DATABASE <target_db> TO ROLE NIMBLE_ROLE;
   ```
4. **Discover existing apps (one app = one schema).** Check the target DB for any of the skill's
   tables so you don't collide with — or silently clobber — a live *or half-provisioned* app:
   ```sql
   SELECT table_schema, ARRAY_AGG(table_name) tables
   FROM <target_db>.INFORMATION_SCHEMA.TABLES
   WHERE table_name IN ('CFG_APP','RAW_SERP','RAW_PDP') GROUP BY 1;
   ```
   When the architect proposes a schema name (Phase 1), if that schema appears here, STOP and let the
   user choose — never re-provision over it implicitly:
   - **(a) New app** — pick/confirm a *different* schema name, then proceed normally.
   - **(b) Update the existing app** — do NOT re-provision; route to `references/lifecycle.md`
     (`update-keywords` / `update-focal` / `re-resolve-category` / `refresh-now`).
   - **(c) Rebuild from scratch** — only on explicit confirmation, and do a true reset first
     (`DROP SCHEMA IF EXISTS <db>.<schema>;`) so the Phase 2 templates apply to a clean schema rather
     than half-replacing objects while stale `CFG_*`/`RAW_*` rows survive. (A schema with `RAW_*` but
     no `CFG_APP` is exactly this half-provisioned state — treat it as rebuild, not new.)

### Phase 1 — Intake (the category architect)
See `references/intake.md` for the tiers and the Cortex proposal prompt.
1. Ask for **category** (required) and **brand** (optional — omit for a category-overview app).
2. Run the category-architect Cortex prompt to propose **focal brand** (if not given), **keywords**
   (~6), **focal patterns** (spacing variants), and a **schema name**.
3. **Show the proposal; get confirmation / edits.** Defaults (Tier 3): retailers Walmart/Amazon/Target,
   geo US zip, daily refresh.

### Phase 2 — Provision the data foundation (run the templates in order)
Fill the placeholders from the confirmed intake, then run each file. Derive
`__AGENT_NAME__` = `UPPER(brand, spaces→underscores) || '_SHELF_ANALYST'`; render `__REFRESH_CRON__`
from the chosen cadence (default `USING CRON 0 6 * * * America/Chicago`); use the `__CORTEX_MODEL__`
and `__CORTEX_MODEL_CHEAP__` resolved in Phase 0 (2b) everywhere they appear (`__CORTEX_MODEL__`:
`references/intake.md` + the cockpit; `__CORTEX_MODEL_CHEAP__`: the resolver in `sql/views.sql`).

1. **`sql/config.sql`** — run the `CREATE TABLE` statements (CFG_APP/CFG_QUERIES). **Do NOT run the
   example seed**; instead write `CFG_APP` (one row, incl. `geo_zip` + `retailer_map`) and
   `CFG_QUERIES` (one row per keyword × retailer — geography is applied at refresh, not stored here)
   from the confirmed intake, per `references/intake.md`. This assumes a **fresh schema** (guaranteed
   by the Phase 0 gate: a new name, or a rebuild that `DROP`ped first) — the plain `INSERT`s apply
   cleanly. To *change* an existing app's config, use `references/lifecycle.md`, not a re-provision.
2. **`sql/ingest.sql`** — raw tables + `REFRESH_SHELF()` + `DAILY_SHELF_TASK`.
3. **`sql/views.sql`** — `BRAND_MAP` + `V_PRODUCT_BRAND` + the feature views.
4. **`sql/semantic_view.sql`** — `SHELF_SV`.
5. **`sql/agent.sql`** — the `<BRAND>_SHELF_ANALYST` Cortex agent.

### Phase 3 — Seed, then stand up the cockpit
1. **Seed fast, then widen — two-cap.** The first seed is interactive (the user is waiting for a live
   cockpit), the daily run is unattended, so use a small cap for the seed and a fuller one for the
   cron. Focal-first PDP ordering means even a small cap still enriches the focal brand, so the cockpit
   has real focal content immediately:
   ```sql
   UPDATE __DB__.__SCHEMA__.CFG_APP SET pdp_cap = 30 WHERE app_key = '__SCHEMA__';  -- snappy first cockpit (~4 min total)
   ```
2. **Seed the first snapshot — server-side, async.** Do **not** `CALL REFRESH_SHELF()` from the
   session: it blocks the client for the whole run and reads as a hang. Fire the task instead:
   ```sql
   EXECUTE TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK;   -- runs REFRESH_SHELF() server-side, returns immediately
   ```
   Watch it to SUCCEEDED:
   ```sql
   SELECT name, state, scheduled_time, completed_time, error_message
   FROM TABLE(__DB__.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'DAILY_SHELF_TASK')) ORDER BY scheduled_time DESC LIMIT 5;
   ```
   Expect a few minutes (SERP via the UDTF lateral join; PDP fanned out concurrently by `REFRESH_PDP`).
   The resolver needs no manual step — `REFRESH_SHELF` calls `REBUILD_BRAND_MAP()` as its last step
   (after `RAW_PDP` is populated), so `BRAND_MAP` refreshes on the seed and every daily run, and the
   cockpit shows real brand tiers on first open. (A category change still warrants a manual
   `CALL …REBUILD_BRAND_MAP();` — see lifecycle.)
3. **Cockpit:** render `assets/cockpit_template.py` (replace `__DB__`/`__SCHEMA__`/`__BRAND__`/
   `__CATEGORY__`), `PUT` it to a per-app stage, and `CREATE STREAMLIT`:
   ```sql
   CREATE STAGE IF NOT EXISTS __DB__.__SCHEMA__.APP_STAGE;
   -- PUT file://app.py @__DB__.__SCHEMA__.APP_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE;
   CREATE OR REPLACE STREAMLIT __DB__.__SCHEMA__.COCKPIT
     ROOT_LOCATION = '@__DB__.__SCHEMA__.APP_STAGE' MAIN_FILE = 'app.py'
     QUERY_WAREHOUSE = '__WAREHOUSE__';
   ```
4. **Restore the daily cap.** Once the cockpit is verified, set the cap the unattended daily run
   should use — default `50`; raise (e.g. `100`–`200`) for fuller coverage on a larger warehouse:
   ```sql
   UPDATE __DB__.__SCHEMA__.CFG_APP SET pdp_cap = 50 WHERE app_key = '__SCHEMA__';
   ```
   (Safe any time — `REFRESH_PDP` reads the cap once at the start of each run, so it only affects the
   *next* daily refresh.)

### Phase 4 — Verify & deliver
**Object completeness gate (do this first).** The cockpit reads its views defensively — a *missing*
view renders as a silently-empty panel, not an error — so confirm the **full** object set exists before
declaring success (a partial `views.sql` run is the classic cause of empty Content / Analytics / VOC
surfaces). Expect every name below; if any is missing, re-run the relevant template wholesale:
```sql
SELECT object_name, object_type FROM __DB__.INFORMATION_SCHEMA.OBJECTS
WHERE object_schema = '__SCHEMA__'
  AND object_name IN ('CFG_APP','CFG_QUERIES','RAW_SERP','RAW_PDP','RAW_VOC','GEO_ANSWERS','GEO_SOURCES',
                      'BRAND_MAP','V_PRODUCT_BRAND','V_BRAND_CLASSIFIED','V_SHARE_OF_SHELF','V_CONTENT_HEALTH',
                      'V_ALERT_OOS','V_TREND_SOS_DAILY','V_TREND_KPI','V_SENTIMENT_SUMMARY',
                      'V_AI_SHARE_OF_ANSWER','V_AI_TOP_SOURCES','V_NEXT_BEST_ACTIONS','SHELF_SV')
ORDER BY object_type, object_name;
-- plus the procs (REFRESH_SHELF/REFRESH_PDP/REBUILD_BRAND_MAP), the task, the agent, the streamlit.
```
> When **updating** an existing app, re-run the **entire** `views.sql` (it creates all views in one
> pass) — never a subset, or you leave stale/missing views behind.

Then run the data checks from the README (`is_focal` not all-FALSE; `V_SHARE_OF_SHELF` populated;
`SEMANTIC_VIEW(SHELF_SV ...)` returns rows). Then deliver:
- the **cockpit** (`SHOW STREAMLITS IN SCHEMA __DB__.__SCHEMA__;` → the app URL),
- the **agent** (`__AGENT_NAME__`, in Snowflake Intelligence → Agents),
- the **headline** (focal share of shelf, top complaint, etc.).
> Share of AI Answer shows 0% until the GEO backfill runs — pre-seed it for any live demo.

## Lifecycle — manage the app after creation
The skill manages a config-driven pipeline. See `references/lifecycle.md` for the SQL of each command:
`update-keywords`, `update-focal`, `re-resolve-category`, `refresh-now`.

## Reference map
- `references/intake.md` — the intake tiers, the category-architect Cortex prompt, and how to build
  the `CFG_APP` / `CFG_QUERIES` rows (incl. the per-retailer agents + zip keys).
- `references/lifecycle.md` — the update commands (the config-edit-then-refresh patterns).
- `README.md` — the components, the data model, and a by-hand walkthrough.
