# Lifecycle — manage the app after creation

The app is a config-driven pipeline, so most changes are a one-row edit the live views reflect on the
next refresh. These are the skill's commands; substitute `__DB__` / `__SCHEMA__` throughout.

## `refresh-now`
Run ingestion immediately, **server-side and non-blocking** — fire the task rather than a blocking
`CALL` (which would hold the session for the whole SERP + concurrent-PDP run):
```sql
EXECUTE TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK;
-- watch it:
SELECT name, state, completed_time, error_message
FROM TABLE(__DB__.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'DAILY_SHELF_TASK')) ORDER BY scheduled_time DESC LIMIT 5;
```

## `update-keywords` — add / remove a search term (no DDL)
Add a keyword (the next refresh ingests it). Geography is applied at refresh, so a row is just
keyword + retailer + agent:
```sql
INSERT INTO __DB__.__SCHEMA__.CFG_QUERIES (keyword, retailer, agent)
VALUES ('dark chocolate', 'amazon', 'amazon_serp');
```
Stop refreshing a term without deleting history:
```sql
UPDATE __DB__.__SCHEMA__.CFG_QUERIES SET active = FALSE WHERE keyword = 'dark chocolate';
```
Apply now with `refresh-now`, or wait for the daily Task.

## `update-focal` — change focal patterns or the focal brand (live)
`V_PRODUCT_BRAND` reads these from `CFG_APP`, so the views reflect the edit immediately — no DDL,
no refresh needed:
```sql
UPDATE __DB__.__SCHEMA__.CFG_APP
SET focal_patterns = ARRAY_CONSTRUCT('ACME BAR','ACMEBAR','KIT-KAT')   -- and/or brand = 'Acme'
WHERE app_key = '__SCHEMA__';
```
If you changed the **brand label**, also re-run `sql/agent.sql` (the agent's display name + instructions
embed `__BRAND__` at create time; the views already follow `CFG_APP.brand`).

## `re-resolve-category` — change the category (heavier)
The category drives the Cortex brand resolver and the agent instructions, so it's not a pure live tweak:
```sql
UPDATE __DB__.__SCHEMA__.CFG_APP SET category = 'candy' WHERE app_key = '__SCHEMA__';
CALL __DB__.__SCHEMA__.REBUILD_BRAND_MAP();   -- re-normalize brand tiers for the new category (Cortex over RAW_PDP)
```
Then re-run `sql/agent.sql` so the agent instructions match. `V_PRODUCT_BRAND`'s
category-stem exclusions are live (they read `CFG_APP.category`).

## Other knobs
- **Geography** — `UPDATE CFG_APP SET geo_zip = '<zip>' WHERE app_key = '__SCHEMA__';` then
  `refresh-now`. The zip is applied at refresh from `CFG_APP.geo_zip`, so this single edit re-targets
  both the SERP and PDP passes — no per-row rewrite.
- **Cadence** — `CFG_APP.refresh_cron` is the source of truth; to change the live schedule,
  `ALTER TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK SUSPEND;` then recreate it with the new `SCHEDULE`
  and `RESUME`.
- **PDP depth** — `UPDATE CFG_APP SET pdp_cap = <n>` (max PDP fetches per retailer per refresh;
  runtime/cost guard). Two-cap pattern: a low cap (~30) for the interactive first seed, then a fuller
  cap for the unattended daily run (focal-first ordering means even a low cap still enriches the focal
  brand). `REFRESH_PDP` reads the cap at the start of each run, so a change applies to the next refresh.

## Rebuild or remove an app
Each app is a self-contained schema, so:
- **Rebuild from scratch** (e.g. config drifted, or you want a clean reset): `DROP SCHEMA IF EXISTS
  __DB__.__SCHEMA__;` then re-run the provision templates (Phase 2–3). The `DROP` first means the
  config `INSERT`s apply to a clean schema instead of half-replacing objects over stale rows.
- **Remove an app entirely**: `DROP SCHEMA IF EXISTS __DB__.__SCHEMA__;` (suspend the task first with
  `ALTER TASK __DB__.__SCHEMA__.DAILY_SHELF_TASK SUSPEND;`). Other apps in the database are untouched.
