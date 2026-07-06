# Nimble Competitor-Intel on Claude Managed Agents

A reusable template that runs Nimble's **competitor-intel** skill as an autonomous
**Claude Managed Agent**: on a weekly cron it researches competitors via the Nimble MCP,
dedups against persistent memory, and posts a TL;DR digest to Slack. No human in the loop,
no server to run.

```
depl (cron) ──▶ session ──▶ agent
                              │  1. read profile ─────────▶ memory_* tools (persistent wiki)
                              │  2. run competitor-intel skill
                              │        ├─ web research ─────▶ Nimble MCP (mcp.nimbleway.com)
                              │        ├─ dedup ────────────▶ /memory/competitors/*.md (memory store)
                              │        └─ persist findings ─▶ memory store (survives to next week)
                              └─ 3. post TL;DR ────────────▶ Slack Web API (#your-channel)
```

Because the skill dedups against last week's findings, the digest is only *what is new*.

**To set it up, hand this folder to your coding agent** (Claude Code, Cursor, etc.) and ask
it to follow `AGENTS.md`. It will interview you to build the profile, collect your tokens,
and provision everything. The manual steps are in [Setup](#setup) below.

## Architecture

| Concern | How | Why |
|---|---|---|
| Agent config | `agent.yaml` via `ant beta:agents` | Persisted + versioned: create once, run weekly, tweak without breaking running sessions |
| Web research | **Nimble MCP** (`mcp.nimbleway.com/mcp`) + Vault | MCP-native: no CLI install, auth injected at the proxy |
| Digest delivery | **Slack** — Web API with a bot token, or the Slack MCP with OAuth | Two supported modes; the Web API path works with an `xoxb-` bot token, the MCP path uses OAuth (see AGENTS.md "Choose the Slack transport") |
| Skill workflow | competitor-intel as a **custom Skill** (fetched from `Nimbleway/agent-skills`) | Reuses the full playbook: research, freshness validation, dedup, report structure |
| Persistence | **Memory Store** via the `memory_*` tools | The store is the wiki; the agent maps the skill's `~/.nimble/...` paths onto memory-store paths. Makes "only what's new" work across weeks |
| Cadence | **Scheduled Deployment** (cron) | Each firing creates a session |

Things the template handles so the unattended run works: the system prompt pins every default
and forbids the skill's interactive prompts (no human to answer them); it sets `always_allow`
on every toolset (an MCP call awaiting approval would otherwise idle the session forever); and
it maps the skill's hardcoded `~/.nimble/...` paths onto the memory store's `memory_*` tools
(there is no `/mnt/memory` mount in this environment). Verified end to end: a run posts a
deduped TL;DR to Slack and persists the wiki for next week.

## Setup

The template ships **no company profile** — you supply your own.

**Step 0 — create your profile.** The scheduled agent runs unattended, so create the profile
before deploying (onboarding is interactive). Either run the skill once in Claude Code (`/competitor-intel`, which
discovers competitors and writes `~/.nimble/business-profile.json`) then `cp` it into
`profile/`, or copy `profile/business-profile.example.json` to
`profile/business-profile.json` and fill it in. Both `profile/business-profile.json` and
`.env` are git-ignored.

**Steps 1-3 — provision and deploy.**

```bash
cp .env.example .env      # NIMBLE_MCP_TOKEN + SLACK_MCP_ACCESS_TOKEN
bash scripts/00-setup.sh  # fetches the skill from GitHub, then creates env, vault,
                          # memory store, seeds YOUR profile, uploads skill, creates agent
#   -> paste the printed *_ID values into .env
bash scripts/10-deploy.sh # weekly scheduled deployment

# Smoke-test before trusting the schedule, then watch it in the Console:
ant beta:deployments run --deployment-id <depl_id>
```

Prereqs: `ant` authed to a workspace with the Managed Agents beta, `gh` (to fetch the
skill), a Nimble MCP token, and a Slack MCP access token. Both MCP endpoints are hardcoded.
Some `ant` flag shapes vary by CLI version; each script cites the raw HTTP path and where to
run `--help`.

## Files

```
AGENTS.md                               # runbook the customer's coding agent follows
agent.yaml                              # the CMA agent (system prompt, skill, MCP servers, tools)
environment.yaml                        # cloud container + networking
profile/business-profile.example.json   # schema to copy; your real profile is git-ignored
scripts/00-setup.sh                     # fetches skill from GitHub + one-time control-plane setup
scripts/10-deploy.sh                    # create the scheduled deployment
scripts/99-teardown.sh                  # archive/delete everything (versions-first for the skill)
.env.example                            # tokens + IDs
# skill/ is created at setup time (fetched from Nimbleway/agent-skills); git-ignored
```

## Changing settings after deploy

The Slack channel, competitor list, and keywords all live in the profile inside the memory
store (not a local file). To change any of them, edit the profile in the store and it takes
effect on the next run, no agent re-version needed:

```bash
ant beta:memory-stores:memories retrieve --memory-store-id <MEMSTORE_ID> --path /business-profile.json  # read
# edit the JSON (e.g. integrations.slack.channel), then:
ant beta:memory-stores:memories update   --memory-store-id <MEMSTORE_ID> --path /business-profile.json --content @business-profile.json
```

## Extending it

- Add a Notion MCP to archive the full report while Slack gets the TL;DR.
- Change the cron in `10-deploy.sh` or the competitor list in your profile.
- Swap the skill to wrap `competitor-positioning`, `brand-mention-monitor`, or
  `launch-monitor` the same way.
