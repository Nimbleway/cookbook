# Setup: Nimble × Mastra cookbook (example app: supply chain event monitor)

You are helping the user set up and run the Nimble × Mastra cookbook. It shows how to use the
`@nimble-way/mastra` integration in a Mastra app, through an example supply chain event
monitor. Follow these steps in order. Check each prerequisite before proceeding. Tell the user
what you're doing at each step.

The app runs in two modes. **Demo mode** replays real research results saved in the repo and
needs no API keys. **Live mode** starts real Nimble research runs, which are billed. Set up demo
mode first, then offer live mode.

---

## Step 1 — Check prerequisites

**Node.js 22.13 or later.** `@nimble-way/mastra` requires it.

```bash
node --version
```

If it reports a version below 22.13, ask the user to install a current Node.js (for example
`brew install node` on macOS, or from https://nodejs.org) before continuing.

**git**

```bash
git --version
```

---

## Step 2 — Clone the repo

If a `cookbook` directory already exists, pull instead of cloning.

```bash
if [ -d cookbook ]; then cd cookbook && git pull && cd ..; else git clone https://github.com/Nimbleway/cookbook; fi
cd cookbook/apps/mastra-supply-chain-monitor
```

---

## Step 3 — Install dependencies

```bash
npm install
cp .env.example .env
npm test
```

Install takes about a minute. `npm test` runs offline in a few seconds. Every test should pass
(`fail 0`). If any test fails, show the user the output and stop.

---

## Step 4 — Run the demo

```bash
npm run sweep
npm run collect
```

`sweep` returns in a second with three `sample-…` run IDs, one per product. `collect` replays
the saved results. It reports `"collected": 3` and `"newEvents": 4`, and prints one Slack-style
alert to the console (there is no Slack webhook yet). It also writes today's digest to
`data/digests/`.

Show the user the digest:

```bash
npm run digest
```

Explain what they're looking at:

- Each event names the products it reaches, where and when it happened, its status, and how it
  reaches the product.
- **Sources** come from Nimble's per-claim trust data, not from a model's summary.
- **Leads the sweep saw but could not confirm** are things the research found but couldn't tie
  to the date window or to a product. Some record a negative result, for example "no strike or
  outage at Bac Ninh was reported in the window".

If the user runs `npm run sweep` again within an hour, it's refused ("minimum gap is 60 min").
That's deliberate: the guard stops extra billed runs. `npm run sweep -- --force` overrides it.

---

## Step 5 — Get API keys (for live mode and the investigator chat)

Ask the user whether they want to run the live monitor. If yes, they need:

- **Nimble API key**: https://online.nimbleway.com/settings/api-keys. Tell the user: "Every
  research run is a Nimble Web Search Agent run. The scheduled sweep starts three per tick."
- **Anthropic API key**: https://console.anthropic.com. Tell the user: "Claude scores new events
  against the products and powers the investigator chat. It's a few calls a day."
- **Slack incoming webhook (optional)**: tell the user that without one, alerts print to the
  console.

---

## Step 6 — Configure the environment

Open `.env` and fill in the keys:

```
NIMBLE_API_KEY=<their Nimble key>
ANTHROPIC_API_KEY=<their Anthropic key>
SLACK_WEBHOOK_URL=<optional>
```

Then create the two Web Search Agents. Creating an agent is free; runs are what's billed.

```bash
npm run setup-agents
```

It prints two lines, `NIMBLE_SWEEP_AGENT_ID=wsa_…` and `NIMBLE_DEEP_DIVE_AGENT_ID=wsa_…`. Add
both to `.env`. Run `setup-agents` only once: each run creates new agents, and a reused agent
keeps memory across runs.

For live mode, also set:

```
USE_LIVE=true
```

---

## Step 7 — Run it live

**Ask the user to confirm before this step: it starts three billed research runs at high
effort.**

```bash
npm run sweep
```

Live mode keeps its own ledger (`data/monitor.db`, separate from the demo's `data/demo.db`), so
the demo run doesn't affect it. The sweep returns in seconds with three `task_run_…` IDs. The research runs on Nimble and typically takes 5–15 minutes.

Wait a few minutes, then:

```bash
npm run collect
```

If it reports `"stillRunning"` above 0, wait and run it again. Collecting is free: it only
reads results. When `"stillRunning"` is 0, show the user `npm run digest`.

A sweep can legitimately find nothing in a quiet window. Don't present an empty result as a
failure. Point the user to the leads section, which shows what was checked.

---

## Step 8 — Orient the user in Mastra Studio

```bash
npm run dev
```

Open http://localhost:4111. Point the user to the "Patterns in this cookbook" table in
README.md, which maps each way of using the integration to the file that shows it. Then show
the user:

- **Workflows → sweep and collect:** the same code paths as the npm scripts, with each step's
  input and output visible.
- **Agents → Supply chain investigator:** a chat agent that answers from what the monitor has
  found, and can start a deep-dive research run.

Questions to try:

1. "What did the monitor find for the laptop this week, and which of it matters most?"
2. "Which events touch both the earbuds and the smartwatch?"
3. "Start a deep dive on the most severe event." This starts a billed run, even in demo mode.
   The agent reports a run ID.
4. "Is the deep dive ready?" Asked too early, the agent should say not yet and keep the run ID,
   without starting a second run.

---

## Step 9 — Scheduling (optional)

If the user wants the monitor to run on its own three times a day, walk them through the "Run
it on a schedule" section of README.md: `mastra deploy`, the platform variables (always set
`MONITOR_API_KEY` on a deployed server), and the GitHub Actions workflow in
`.github/workflows/supply-chain-monitor.yml`.

---

## Notes

- **Live results vary.** Each run researches the live web, so events, wording, and counts differ
  run to run. Read the output rather than expecting a fixed result.
- **Confidence** grades what the run claimed, not how much it covered. An event with `low`
  confidence goes to the digest's "Unconfirmed" section and never to Slack.
- **A run that fails to start** is recorded in the digest. If its outcome is `unknown`, a run may
  exist anyway: check the Nimble dashboard before starting another.
- **"triage failed; recording events untriaged"** means the model call failed, most often a
  missing `ANTHROPIC_API_KEY`. The events are kept and appear under "Not yet triaged".
- **Changing the model:** set `MODEL` in `.env` to any provider Mastra's model router supports,
  with that provider's key.
- **Never commit `.env`.** It's in `.gitignore`.
