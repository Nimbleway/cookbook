# hermes-account-monitor — Nimble × Hermes Agent

Run Nimble Web Search Agents from Hermes, on a schedule, delivered to Slack.

## The integration

```bash
pip install hermes-nimble-agent
hermes plugins enable nimble-agent
```

Two commands. The plugin adds five tools to your Hermes agent, which it can then call in
conversation, from a cron job, or through the gateway:

| tool | what it does |
|---|---|
| `nimble_agents_list` | find existing Web Search Agents on your account |
| `nimble_agent_bootstrap` | create one from a gallery template |
| `nimble_agent_run_start` | start a research run — returns immediately with durable ids |
| `nimble_agent_run_status` | poll it |
| `nimble_agent_run_result` | fetch the cited answer, whenever you come back |

The plugin also ships a skill, `agent-research`, for one-shot cited research: ask a question, get
told "started", collect the answer minutes later from any session.

**Requires** `NIMBLE_API_KEY` in the Hermes `.env` — without it the tools stay silently hidden.
Python 3.11+.

Verify the tools reached the agent loop:

```bash
hermes -z "List every tool whose name starts with nimble_. Names only." -m claude-sonnet-4-6
```

## What this cookbook adds

The plugin's own skill answers a question **once**. This turns it into a **standing monitor**.

Give it a watchlist of 15 accounts. Each cycle it runs Web Search Agents across them, records
findings in a dated ledger, and reports only what is genuinely new — with a citation per change.

```
*Account Monitor* — 4 change(s) across 4 account(s) since 2026-07-04

*Ramp*
  📈 headcount 1,200 -> 2,666: Ramp listed 2,666 employees on LinkedIn as of August 2026.  [high]
      ↳ https://linkedin.com/company/ramp

*Figma*
  📌 headline development: Figma acquired Orchids on July 7, 2026.  [high]
      ↳ https://crunchbase.com/organization/figma/company_overview/overview_timeline
```

When nothing has happened it says so in one line and stops. Silence is the correct output.

It uses four Hermes primitives the plugin alone doesn't touch:

| Hermes primitive | role here |
|---|---|
| **cron** | fires the cycle; runs span ticks, so work survives restarts |
| **memory** | the event ledger lives in Hermes' own `MEMORY.md`, shared with the agent |
| **skill** | `skills/account-monitor` — drives a cycle and enforces the reporting rules |
| **gateway** | delivers the digest to Slack, Telegram or Discord |

Because the ledger is in Hermes memory, you can also just ask:

```bash
hermes -z "What's new with Figma and Rippling? Use MEMORY.md only." -m claude-sonnet-4-6
```

It answers in prose with source links, from accumulated memory, with no new research and no cost.

## Setup

**Python 3.11 or newer** (hermes-agent requires it; macOS ships 3.9).

```bash
python3.12 -m venv .venv          # substitute your 3.11+ interpreter
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # NIMBLE_API_KEY + a model provider key

export HERMES_HOME=$PWD/.hermes_home
mkdir -p $HERMES_HOME/skills && cp .env $HERMES_HOME/.env
.venv/bin/hermes plugins enable nimble-agent
cp -r skills/account-monitor $HERMES_HOME/skills/
```

## Usage

Run **Setup** above first — these commands use the venv's interpreter directly, so no `activate` is
needed, but `.venv` has to exist.

```bash
.venv/bin/python monitor.py                            # cached digest, no keys needed
USE_LIVE=true .venv/bin/python monitor.py --setup      # create the agent, once
USE_LIVE=true .venv/bin/python monitor.py              # run a cycle, then digest
USE_LIVE=true .venv/bin/python monitor.py --deliver slack
```

Edit the `WATCHLIST` list at the top of `monitor.py` to change the accounts.

### Schedule it

```bash
hermes cron create "0 8 * * *" --name account-monitor \
  --script account-monitor.sh --no-agent --deliver slack
hermes cron tick        # run due jobs once, for testing
```

Unattended firing needs the scheduler running: `hermes gateway install`.

### Slack

Needs two tokens, because the Slack adapter uses Socket Mode:

```bash
hermes plugins enable slack-platform
hermes slack manifest > slack-app.json     # create the Slack app from this
```

Then `SLACK_BOT_TOKEN=xoxb-…` and `SLACK_APP_TOKEN=xapp-…` (scope `connections:write`) in
`$HERMES_HOME/.env`, and `/invite` the bot to your channel.

## Output

| file | what |
|---|---|
| `data/sample_digest.txt` | the digest, as delivered |
| `data/sample_MEMORY.md` | the event ledger as Hermes sees it — 161 events, dated and sourced |
| `data/signals.db` | ledger plus per-cycle snapshots |
| `data/runs/` | raw agent responses, saved before any transform |

## Using the integration in your own Hermes agent

**Batch Web Search Agent work in threes.** Coverage, not speed, sets the limit: 3 entities per run
returned 100% of the expected rows, 8 returned 62%, and 12 returned **10%** — while still reporting
`high` confidence on that 10%. Small batches run concurrently, so wall-clock stays around one run.

**Don't detect change by comparing one cycle's research to the last.** It fails while appearing to
work — 49 false alarms across 13 of 15 accounts on two cycles eight minutes apart. Research isn't
reproducible enough to diff: each run surfaces a different subset of true facts, so an item appearing
today and not yesterday tells you nothing about whether it just happened. Key on the event's own
date instead, which is stable, and let the ledger accumulate.

**Confidence and citations are per field, not per record.** A record typically carries ~25 `high`
claims beside a few `low` ones; collapsing that to one value marked 10 of 15 accounts `low` and
suppressed every good signal on them. A `low` claim means unverified, not false — never alert on one.

**`nimble_agent_bootstrap` doesn't copy the template's goals or sources**, so a bootstrapped agent
runs with no source whitelist. This app patches the config afterwards; tracked as
Nimbleway/hermes-nimble-agent#2, and the patch can go once that ships.

**`output_schema` is capped at 20 columns** and isn't validated at agent-create time — the agent is
created happily and every run then 422s.

## Reference

- `hermes-nimble-agent`: https://github.com/Nimbleway/hermes-nimble-agent
- Hermes Agent: https://hermes-agent.nousresearch.com
- Nimble Web Search Agents: https://docs.nimbleway.com
