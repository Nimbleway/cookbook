# Setup runbook (for the coding agent)

You are helping the user stand up a **Claude Managed Agent** that runs Nimble's
competitor-intel skill on a weekly schedule and posts a digest to Slack. Work through the
phases in order. Interview the user where a phase needs input. See `README.md` for what the
system does and how it fits together; this file is the procedure.

## Rules
- **Secrets:** tokens go only into `.env` (git-ignored) and the Vault. Never print them back,
  never write them into any other file, never commit them.
- **`.env` hygiene:** clean `KEY=value` lines only. No inline `# comments` after a value (they
  become part of the value when sourced). Never add `ANTHROPIC_API_KEY` to `.env` — a blank or
  stale value silently overrides the `ant auth login` profile and breaks auth.
- **Verify flags before trusting them.** These are beta APIs; `ant` flags vary by version. If a
  command errors on a flag, run its `--help`, adjust, and continue. The scripts already encode
  the working shapes for ant v1.16 (see quirks below).
- **Confirm the profile with the user before provisioning** (Phase 4). Everything downstream
  depends on it.

## ant CLI (v1.16) — the invocation shapes the scripts use
The working patterns for the current CLI; keep them if you rewrite a step:
- `beta:vaults create` takes `--display-name` (while `memory-stores create` takes `--name`).
- `beta:vaults:credentials create` takes the auth object as a `--auth` flag (a JSON string).
- `beta:skills create` sends each `--file` by basename, so upload with `curl` using
  folder-prefixed multipart filenames — that places SKILL.md at the top level of the skill
  (00-setup.sh Phase 7 does this).
- `beta:agents create` takes `--model` (an object, e.g. `{id: claude-opus-4-8}`) and `--name` as
  flags; the rest of the body comes from stdin YAML.
- `beta:agents update` takes `--version` (optimistic lock); pass changed object fields
  (skills/tools) via stdin YAML alongside it.
- To remove a skill, delete its versions first, then the skill (see `scripts/99-teardown.sh`).
- **Set `always_allow` on every toolset for an unattended agent.** MCP toolsets default to
  `always_ask`; in a headless run the first MCP call would otherwise wait for an approval that
  never arrives. Set `permission_policy: {type: always_allow}` on the agent_toolset and each mcp_toolset.
- **A deployment pins the agent version at creation.** After you update the agent, recreate the
  deployment so it runs the new version.
- **Reach the memory store through the `memory_*` tools** (memory_read / memory_list / memory write).
  Map the skill's `~/.nimble/...` paths onto memory-store paths (`/business-profile.json`,
  `/memory/competitors/<name>.md`, …); the agent.yaml system prompt already instructs this.
- **Slack:** the hosted Slack MCP uses OAuth. For a bot-token setup, post via the Slack Web API
  (`chat.postMessage`) with the bot token as an `environment_variable` Vault credential
  (allowed_hosts `slack.com`) and allow-list `slack.com` in the environment. Both modes work
  (see "Choose the Slack transport").

## Phase 0 — Prerequisites
1. `ant --version` and `ant auth status` — the `ant` CLI must be installed and authed to an
   Anthropic **workspace with the Managed Agents beta enabled**. If missing, guide the user:
   install `ant` (`brew install anthropics/tap/ant` or the release binary), then
   `ant auth login`.
2. `gh --version` — used to fetch the skill from GitHub in Phase 4. (Or curl; the setup
   script uses `gh`.)
3. Collect from the user, and hold for later phases:
   - **Nimble API key** — self-serve from their Nimble account; used as the bearer for the
     Nimble MCP (`mcp.nimbleway.com/mcp`).
   - **Slack channel** for the digest (e.g. `#competitor-intel`).
   - **Slack auth mode** — ask which of the two the user wants (see next section).

## Choose the Slack transport (ask the user)
Slack delivery works two ways. Pick one with the user before provisioning.

**Option A — Bot token via the Slack Web API (default, simplest).**
The agent posts with `chat.postMessage` using a Slack **bot token**. Best when the user can
create/opt-into a Slack app and drop its `xoxb-` token in.
- User provides: a bot token (`xoxb-…`) with `chat:write`; the bot must be invited to the channel.
- Provisioning: `SLACK_BOT_TOKEN` in `.env`; `00-setup.sh` stores it as an `environment_variable`
  Vault credential (allowed_hosts `slack.com`); the environment allow-lists `slack.com`; the agent
  posts via the Web API. This is what `agent.yaml`/`environment.yaml` ship configured for.

**Option B — Slack MCP + OAuth (manual connect in the Console).**
The agent posts through the hosted Slack MCP (`mcp.slack.com`). Best when the user prefers OAuth
(no long-lived bot token) and per-user scopes.
- User does a one-time **manual OAuth connect** in the Anthropic Console (Platform UI) to authorize
  the Slack MCP, which stores the OAuth credential.
- Provisioning changes: add a `slack` MCP server + an `mcp_toolset` (with `always_allow`) to
  `agent.yaml`; store the OAuth credential in the Vault via the Console connect; drop the
  `SLACK_BOT_TOKEN` env-var credential and the `slack.com` egress. **No system-prompt edit needed** —
  the shipped prompt is mode-agnostic ("if a Slack MCP tool is available, the skill posts via it;
  otherwise post via the Web API"), so it works for either mode as-is.

Default to Option A unless the user asks for MCP/OAuth. Either way the channel lives in the
profile (`integrations.slack.channel`).

## Phase 1 — Build the profile (interview)
The scheduled agent runs unattended, so the profile must exist before it runs (the skill's
onboarding is interactive). Build it now. Copy `profile/business-profile.example.json` to
`profile/business-profile.json` and fill it by interviewing the user:
- company name + domain, one-line description
- competitors: name, domain, category (offer to suggest a list for their domain and let them
  confirm/edit)
- industry keywords
- `integrations.slack.channel` = the channel from Phase 0
Show the finished profile and get explicit confirmation. It is git-ignored.

## Phase 2 — Credentials
Copy `.env.example` to `.env` and fill `NIMBLE_MCP_TOKEN` and `SLACK_MCP_ACCESS_TOKEN` with
the tokens from Phase 0. Leave the `*_ID` fields blank — Phase 4 fills them. `.env` is
git-ignored.

## Phase 3 — Review the config (usually no change)
- `agent.yaml` — the agent: system prompt, the competitor-intel skill, Nimble + Slack MCP
  servers, and the file toolset. MCP URLs are hardcoded.
- `environment.yaml` — cloud container, MCP-only egress.
- `scripts/10-deploy.sh` — the schedule (default: Mon 08:00 America/New_York). Confirm the
  cron and timezone with the user and edit if needed.

## Phase 4 — Provision
Run `bash scripts/00-setup.sh` with the Phase 0 tokens exported in your shell. It:
creates the environment and vault (+ Nimble/Slack credentials), creates the memory store and
seeds the profile into it, fetches the skill from `Nimbleway/agent-skills` and uploads it,
then creates the agent. If an `ant` step errors on a flag, apply the Rules (run `--help`,
adapt). When it finishes, paste the printed `*_ID` values into `.env`.

## Phase 5 — Deploy
Run `bash scripts/10-deploy.sh`. It creates the weekly scheduled deployment and prints the
next fire times — check them.

## Phase 6 — Smoke-test and hand off
Trigger one run immediately instead of waiting for the schedule:
```
ant beta:deployments run --deployment-id <depl_id>
```
Open the Console session URL it reports and confirm the run: it symlinks `~/.nimble` to the
memory store, researches via the Nimble MCP, dedups, and posts the TL;DR to the Slack
channel. Report the outcome to the user, and tell them the digest now arrives on the
schedule. To pause later: `ant beta:deployments pause --deployment-id <depl_id>`.

## Changing settings after deploy
The config lives in the profile inside the memory store (`MEMSTORE_ID`), not in a local
file. To change the **Slack channel**, competitor list, or keywords, read the current
profile, edit it, and write it back:
```
# read
ant beta:memory-stores:memories retrieve --memory-store-id <MEMSTORE_ID> --path /business-profile.json
# write back the edited JSON (updates integrations.slack.channel, competitors, etc.)
ant beta:memory-stores:memories update --memory-store-id <MEMSTORE_ID> --path /business-profile.json --content @business-profile.json
```
The change takes effect on the next scheduled (or manual) run. No agent re-version needed.
(Verify the exact `memories` subcommand flags with `--help`, per the Rules above.)
