# Genie Code skills — Nimble on Databricks

Custom [Agent Skills](https://agentskills.io/specification) for **Databricks Genie Code** (Agent
mode). They package the "live web search data → Delta → dashboard/app" workflow so a user can ask Genie Code
in plain English and it drives the whole flow natively — using the Nimble Unity Catalog functions
([`../`](../) cookbook) plus Genie's native dashboard agent and AppsAgent. No `nimble` CLI, no shell
scripts.

## What's here

```
genie-code-skills/
└── nimble-data-products/   ← the skill (folder name = skill `name`)
    ├── SKILL.md                        discover → ingest → dashboard/app workflow
    └── references/
        ├── nimble-agents.md            SQL discovery + the control-table + LATERAL ingest
        ├── deliverables.md             per-vertical views + how to instruct the dashboard agent / AppsAgent
        └── branding.md                 "Powered by Nimble"
```

## Prerequisite

The Nimble × Databricks integration must be installed (the five `nimble_integration.tools.*` table
functions). See [`../INSTALL.md`](../INSTALL.md). The skill's Phase 0 gate checks for them and stops
with install guidance if missing.

## Install

Genie Code loads skills from a `.assistant/skills/` directory (see the Databricks
[agent skills guide](https://docs.databricks.com/aws/en/genie-code/skills)). Copy the skill folder
there — the folder name must stay `nimble-data-products`.

- **User skill** (just you; the prototype path): `/Users/{username}/.assistant/skills/`
- **Workspace skill** (org-wide; admins): `Workspace/.assistant/skills/`

Quickest path — open the skills folder from the Genie Code panel (**⚙ Settings → Open skills folder**)
and copy the folder in. Then start a **new** Agent-mode chat (edits don't apply to active threads).

### Keep it in sync with this repo (recommended)

Back the skills folder with a [Databricks Git folder](https://docs.databricks.com/aws/en/repos/) so
updates here flow to the workspace:

1. In the workspace, create a Git folder from this repo.
2. Point `.assistant/skills/nimble-data-products` at
   `databricks/genie-code-skills/nimble-data-products` (symlink/copy on pull, or clone the repo
   under `.assistant/skills/` and keep only this subtree).
3. `git pull` to update; start a new Agent-mode chat to pick up changes.

(Manual copy works too — just re-copy the folder when it changes.)

## Use

In a Genie Code [Agent-mode](https://docs.databricks.com/aws/en/genie-code/use-genie-code) chat,
describe the goal in plain English — the skill auto-loads by its description (skills load only in
Agent mode). Examples:

- `pricing comparison on dog products from Amazon and Walmart`
- `scrape Zillow listings for Austin into a Delta table and build a dashboard`
- `show competitor prices from the web in a dashboard`

You can also `@`-mention the skill to force it.

## Relationship to the Claude Code / Cursor skill

The same workflow ships as a published skill in [`Nimbleway/agent-skills`](https://github.com/Nimbleway/agent-skills)
for Claude Code and Cursor, where it uses helper scripts and the `databricks` CLI. This Genie Code
variant is built for Genie's native execution: discovery/ingest run as inline SQL, dashboards go to
Genie's dashboard agent, and apps go to the AppsAgent (Python frameworks by default — Streamlit / Dash
/ Gradio — with React supported build-less via a CDN).

## See also

- [Use Genie Code](https://docs.databricks.com/aws/en/genie-code/use-genie-code) — Agent mode, modes, and how Genie Code works.
- [Extend Genie Code with agent skills](https://docs.databricks.com/aws/en/genie-code/skills) — the authoritative guide to creating and installing custom skills (`.assistant/skills/`, User vs Workspace, `@`-mention).
- [Nimble × Databricks integration](../README.md) — the `nimble_integration.tools.*` SQL functions this skill builds on.
- [Agent Skills specification](https://agentskills.io/specification) — the open standard both this skill and Genie Code follow.
