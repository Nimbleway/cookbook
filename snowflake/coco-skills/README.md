# Cortex Code skills — Nimble on Snowflake

Custom [Agent Skills](https://agentskills.io/specification) for **Snowflake Cortex Code**. They
package end-to-end "live Nimble web data → in-tenant intelligence app" workflows so a user can ask
Cortex Code in plain English and it drives the whole flow natively — using the Nimble Snowflake
integration (the [`../`](../) cookbook: `setup/` + `udtf-data-feeds/` + `cortex-agent-tools/`) plus
Cortex Analyst, Cortex agents, and Streamlit-in-Snowflake. No `nimble` CLI, no shell scripts.

## What's here

```
coco-skills/
└── cmo-intelligence/   ← the skill (folder name = skill `name`)
    ├── SKILL.md                        intake → provision → surfaces → verify workflow
    ├── sql/                            the per-app templates the skill runs in order
    │   ├── config.sql                  CFG_APP + CFG_QUERIES (config-table foundation)
    │   ├── ingest.sql                  raw tables + REFRESH_SHELF() + DAILY_SHELF_TASK
    │   ├── views.sql                   resolver + analytics feature views
    │   ├── semantic_view.sql           SHELF_SV (Cortex Analyst semantic layer)
    │   └── agent.sql                   the <BRAND>_SHELF_ANALYST Cortex agent
    ├── assets/cockpit_template.py      branded Streamlit cockpit (filled + deployed)
    └── references/                     intake, lifecycle
```

## Prerequisite

The Nimble × Snowflake integration must be installed (run once as `ACCOUNTADMIN`): [`../setup/setup.sql`](../setup/setup.sql)
then [`../udtf-data-feeds/nimble_agent_run.sql`](../udtf-data-feeds/nimble_agent_run.sql). These create
`NIMBLE_ROLE`, the warehouse, the secret, the External Access Integration, and the `NIMBLE_AGENT_RUN`
UDTF. Each skill's Phase 0 gate checks for it; if it's missing and the user is `ACCOUNTADMIN`, the
skill can install it (it bundles the SQL) after consent + an API key — otherwise it points an admin here.

## Install

Copy the skill folder into Cortex Code's skills directory (see Snowflake's Cortex Code agent-skills
documentation for the exact location on your client). The folder name must stay `cmo-intelligence`,
and start a fresh Agent-mode chat after adding it.

### Keep it in sync with this repo (recommended)
Symlink or copy from a checkout so updates flow through, rather than hand-editing the installed copy.

## Skills

| Skill | What it does |
|---|---|
| [`cmo-intelligence`](cmo-intelligence/) | Provisions a complete in-tenant digital-shelf / CMO intelligence app from live Nimble web data — config tables, UDTF ingestion Task, brand resolver, analytics views, a semantic view, a Cortex agent, and a branded Streamlit cockpit — and keeps it updatable after creation. |
