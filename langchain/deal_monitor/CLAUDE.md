# Claude Code setup — Deal Monitor

Use this file as the Claude Code context prompt when opening `langchain/deal_monitor`.

## Goal

Help the user run, adapt, and deploy the Deal Monitor cookbook.

The app monitors a live web search query with Nimble, filters out URLs it has already seen, summarizes only new results with an OpenRouter-compatible model, posts the digest to Slack, and persists local state for the next run.

## Product framing

Position this as a live web alerting workflow, not just a LangChain demo.

One-line description:

> Watch any live-web query and get a Slack alert when something new appears.

Nimble's role:

- Nimble provides live web search via `NimbleSearchTool` from `langchain-nimble`.
- LangGraph orchestrates the workflow.
- OpenRouter-compatible chat models summarize new matches.
- Slack is the default notification destination and can be swapped.

## Setup steps

```bash
cd langchain/deal_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```bash
NIMBLE_API_KEY=...
OPENROUTER_API_KEY=...
SLACK_WEBHOOK_URL=...
MONITOR_QUERY=developer tools funding news this week
```

## Verification

Run without external calls first:

```bash
python3 agent.py --dry-run
```

Expected result:

- logs a dry-run Nimble search
- finds one example result
- prints a Slack alert preview
- does not write `.state.json`

Run live mode only after credentials are set:

```bash
python3 agent.py
```

## Safe customisations

Common changes:

- change `MONITOR_QUERY` for a different market or competitor
- change Nimble search settings in `.env`
- replace `notify_slack()` with email, Discord, a database insert, or another webhook
- add a scoring node between `filter_seen` and `summarize_results`
- replace `.state.json` with Redis, Postgres, S3, or another persistent store

## Guardrails

- Keep `--dry-run` working without credentials.
- Do not commit `.env`, `.state.json`, `monitor.log`, `.venv/`, `__pycache__/`, or `.pyc` files.
- Keep Nimble's role explicit: live web search is the data layer; LangGraph, Slack, and the model are swappable.
- Prefer concrete use cases such as funding alerts, competitor launches, acquisition news, pricing/page changes, regulatory updates, hiring signals, and product mentions.
