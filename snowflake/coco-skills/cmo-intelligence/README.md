# CMO Intelligence — Cortex Code (CoCo) Agent Skill

**Version 1.0.0** · see [`CHANGELOG.md`](CHANGELOG.md). The version lives in `SKILL.md` frontmatter and follows SemVer.

A **Cortex Code Agent Skill** that conversationally provisions a complete, in-tenant
**digital-shelf intelligence app** — a branded Streamlit cockpit + a Cortex agent + live Nimble
web data — for any brand or category, in minutes. Nothing leaves your Snowflake account.

Ingestion standardizes on the documented **`NIMBLE_AGENT_RUN` UDTF** (from the [Nimble × Snowflake
integration](https://github.com/Nimbleway/cookbook/tree/main/snowflake)), and every per-app parameter
lives in **config tables** — so an app stays updatable after creation (add a keyword = insert a row)
with no DDL change or redeploy.

> **`SKILL.md` is the source of truth** for the workflow (intake → provision → surfaces → verify) and
> the placeholder list. This README is a human orientation; the agent reads `SKILL.md` + `references/`.

## Prerequisite

The Nimble × Snowflake integration is a one-time `ACCOUNTADMIN` install (role, warehouse, secret,
External Access Integration, and the `NIMBLE_INTEGRATION.TOOLS.NIMBLE_AGENT_RUN` UDTF the skill ingests
through). The skill's Phase 0 gate detects it at runtime, and **if it's missing and you're
`ACCOUNTADMIN`, the skill can install it for you** — it bundles the SQL in `assets/integration/` and
runs it after you confirm and paste your Nimble API key. If you're not admin, an admin runs those two
files (bundled here, or from the cookbook —
<https://github.com/Nimbleway/cookbook/tree/main/snowflake>).

## Layout

```
cmo-intelligence/
├── SKILL.md                 the agent entrypoint — workflow + golden rules
├── sql/                     templates the skill substitutes + runs, in order
│   ├── config.sql           CFG_APP + CFG_QUERIES — the config-table foundation
│   ├── ingest.sql           raw tables + REFRESH_SHELF() + REFRESH_PDP() (concurrent) + DAILY_SHELF_TASK
│   ├── views.sql            resolver (BRAND_MAP, V_PRODUCT_BRAND) + the analytics feature views
│   ├── semantic_view.sql    SHELF_SV — the Cortex Analyst semantic layer
│   └── agent.sql            <BRAND>_SHELF_ANALYST — the Cortex agent over SHELF_SV
├── assets/
│   ├── cockpit_template.py  branded Streamlit cockpit (filled + deployed to a stage)
│   └── integration/         bundled one-time ACCOUNTADMIN install (setup.sql + UDTF)
└── references/              docs the agent reads on demand
    ├── intake.md            the category-architect intake + CFG_* row shapes
    └── lifecycle.md         post-creation commands (update-keywords / -focal / refresh-now …)
```

The `sql/` + `assets/` files are **templates** with `__DB__` / `__SCHEMA__` / `__WAREHOUSE__` /
`__BRAND__` / `__CATEGORY__` / `__AGENT_NAME__` / `__REFRESH_CRON__` / `__CORTEX_MODEL__` /
`__CORTEX_MODEL_CHEAP__` placeholders the skill substitutes per app. Cortex is called via the GA
`AI_COMPLETE` AISQL function; `__CORTEX_MODEL__` (latest available Sonnet, for intake + cockpit) and
`__CORTEX_MODEL_CHEAP__` (Haiku, for the high-volume brand resolver) are both resolved by a Phase 0
probe. Target database, warehouse, and geography (`CFG_APP.geo_zip`) are all configurable — nothing
is pinned to a fixed account.

> **Confirm parsing field names on first run.** Each Nimble Web Search Agent's `parsing` shape differs
> and can evolve. `amazon_serp` is verified against `recipes/amazon_keyword_research`; `walmart_serp` /
> `target_serp` / `*_pdp` projections carry COALESCE fallbacks plus a probe note — run
> `SELECT raw FROM TABLE(NIMBLE_AGENT_RUN(...))` and adjust before trusting at scale.

## Run it by hand (without the skill)

Substitute the placeholders (e.g. `__DB__`→`NIMBLE_INTEGRATION`, `__SCHEMA__`→`ACME_CMO`,
`__WAREHOUSE__`→`NIMBLE_AGENT_WH`, `__REFRESH_CRON__`→`USING CRON 0 6 * * * America/Chicago`), then run
`sql/config.sql` → `sql/ingest.sql` → `EXECUTE TASK …DAILY_SHELF_TASK` (async seed; don't block on a
`CALL`) → `sql/views.sql` → `sql/semantic_view.sql` → `sql/agent.sql`, and deploy
`assets/cockpit_template.py` to a stage as a Streamlit. Verify:

```sql
SELECT is_focal, COUNT(*) FROM NIMBLE_INTEGRATION.ACME_CMO.V_PRODUCT_BRAND GROUP BY 1;  -- not all-FALSE
SELECT * FROM NIMBLE_INTEGRATION.ACME_CMO.V_SHARE_OF_SHELF ORDER BY snapshot_date DESC, share_of_shelf_pct DESC;
-- add a keyword later (no DDL); geography is applied at refresh:
INSERT INTO NIMBLE_INTEGRATION.ACME_CMO.CFG_QUERIES (keyword, retailer, agent) VALUES ('acme dark', 'amazon', 'amazon_serp');
```

## Note on target-site terms of service

These templates pipe data fetched by Nimble into Snowflake; they do not change the legal rules that
govern *what* you fetch. You are responsible for ensuring that any keywords, retailers, and scheduling
you configure comply with the target sites' terms of service, robots policies, and applicable law.
Brand and retailer names used in examples are illustrative.
