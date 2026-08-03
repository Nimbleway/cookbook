# AI Setup — Account Monitor

Drop this file into Claude Code (or any coding agent) and follow it top to bottom. It sets up a
Hermes agent that watches a list of businesses and reports only what changed.

## Step 1 — Check prerequisites

**Python 3.11 or newer.** `hermes-agent` requires it, and macOS ships 3.9.

```bash
python3 --version
python3.12 --version || python3.13 --version || python3.11 --version
```

Use whichever 3.11+ interpreter you have below.

## Step 2 — Clone and enter the app

```bash
git clone https://github.com/Nimbleway/cookbook.git
cd cookbook/apps/hermes-account-monitor
```

## Step 3 — Install

```bash
python3.12 -m venv .venv          # substitute your 3.11+ interpreter
.venv/bin/pip install -r requirements.txt
```

## Step 4 — Fast path: see it work with no keys

```bash
.venv/bin/python monitor.py
```

Prints the cached digest immediately — four dated, cited events across four accounts. No API calls.

Then open `data/sample_MEMORY.md`. That is the event ledger: 161 events across 15 companies, each
dated and sourced. It is the file that makes the design make sense, and its header states the rule —
*an event listed here has already been reported and will not be reported again.*

## Step 5 — Get keys

- **Nimble API key** — https://online.nimbleway.com/account-settings/api-keys
- **A model provider key** for the Hermes loop (Anthropic, OpenAI, or any of Hermes' 18+ providers)

```bash
cp .env.example .env
# fill in NIMBLE_API_KEY and your model provider key
```

## Step 6 — Set up Hermes

Use an isolated profile so this does not touch your personal Hermes config:

```bash
export HERMES_HOME=$PWD/.hermes_home
mkdir -p $HERMES_HOME/skills
cp .env $HERMES_HOME/.env

.venv/bin/hermes plugins enable nimble-agent
cp -r skills/account-monitor $HERMES_HOME/skills/
```

Verify the plugin's tools reached the agent loop — this is worth doing, because they stay silently
hidden if `NIMBLE_API_KEY` is missing:

```bash
.venv/bin/hermes -z "List every tool whose name starts with nimble_. Names only." -m claude-sonnet-4-6
```

You should see five: `nimble_agents_list`, `nimble_agent_bootstrap`, `nimble_agent_run_start`,
`nimble_agent_run_status`, `nimble_agent_run_result`.

## Step 7 — Create the agent, once

```bash
USE_LIVE=true .venv/bin/python monitor.py --setup
```

Writes `data/monitor_agent.json`. Note it creates a **custom** agent rather than cloning a gallery
template — see the note at the bottom.

## Step 8 — Run a cycle

```bash
USE_LIVE=true .venv/bin/python monitor.py
```

15 businesses in 5 concurrent batches of 3. Expect 4–10 minutes; batches finish independently.

The first cycle seeds the ledger and reports nothing — correctly, because every event in it predates
the cycle. Run it again tomorrow and you get a real digest.

To see a digest immediately without waiting a day, widen the window: the digest reports events dated
after the previous cycle, so a longer gap surfaces more.

## Step 9 — Edit the watchlist

Open `monitor.py` and change the `WATCHLIST` list near the top. Keep batches at 3 (see notes).

## Step 10 — Schedule it

```bash
mkdir -p $HERMES_HOME/scripts
cat > $HERMES_HOME/scripts/account-monitor.sh <<EOF
#!/bin/sh
cd "$PWD" && USE_LIVE=true "$PWD/.venv/bin/python" -W ignore monitor.py
EOF
chmod +x $HERMES_HOME/scripts/account-monitor.sh

.venv/bin/hermes cron create "0 8 * * *" --name account-monitor \
  --script account-monitor.sh --no-agent --deliver local
.venv/bin/hermes cron run account-monitor      # force a run to test
```

For unattended firing: `.venv/bin/hermes gateway install`.

## Step 11 — Slack delivery (optional)

Needs two tokens, because the Slack adapter uses Socket Mode:

```bash
.venv/bin/hermes plugins enable slack-platform
.venv/bin/hermes slack manifest > slack-app.json
```

Create a Slack app from that manifest at api.slack.com/apps, install it, then add to
`$HERMES_HOME/.env`:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...     # scope: connections:write
```

`/invite` the bot to your channel, then:

```bash
USE_LIVE=true .venv/bin/python monitor.py --deliver slack
```

Note the manifest requests 16 scopes including channel history, because it is the full conversational
bot. Many workspaces require admin approval for that.

## Notes

**Do not try to detect change by comparing cycles.** It fails while appearing to work — 49 false
alarms across 13 of 15 accounts on two cycles eight minutes apart. Research is not reproducible
enough to diff; each run surfaces a different subset of true facts. The ledger keys on the event's
own date instead, which is stable.

**Keep batches at 3.** Coverage collapses with size: 3 entities returned 100% of the grid, 8 returned
62%, 12 returned 10% — and the 12-entity run still reported `high` confidence on that 10%.

**The agent is custom, not a template clone.** No gallery template fits: `lead-enrichment` is
configured for one specific company, `financial-intelligence` assumes public tickers,
`hiring-intelligence` is careers-only. Source groups use empty `domains` arrays so priority is
expressed without whitelisting the agent out of company newsrooms.

**`output_schema` is capped at 20 columns** (422 otherwise) and is **not validated at agent-create
time** — the agent is created happily and every run then fails. Value + key + date for 6 signals is
22 columns, which is why there are 5 signals rather than 6.
