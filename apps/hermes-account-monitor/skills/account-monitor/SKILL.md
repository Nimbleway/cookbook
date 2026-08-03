---
name: account-monitor
description: Daily "who moved" digest for a watchlist of businesses, from cited Nimble research.
version: 0.1.0
author: Nimble
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Monitoring, Research, Web, Citations, GTM]
    category: Research
---

# Account Monitor Skill

Keep a watchlist of businesses and report **only what changed**, with a citation per change.

This is the standing-monitor companion to the plugin's `agent-research` skill. That one answers a
research question once. This one runs on a schedule, accumulates an event ledger, and stays quiet
when nothing has happened.

## When to Use

- The user asks to **watch, track or monitor** a set of companies, accounts or competitors.
- The user asks **"what's new with X"** where X is on an existing watchlist.
- A cron job fires the daily cycle.

Do **not** use for a one-off research question — use `agent-research` for that. Do not use for
product prices or known-URL data: that is deterministic extraction, not research.

## Prerequisites

- `NIMBLE_API_KEY` in the Hermes `.env`. Without it the `nimble_agent*` tools stay hidden.
- The monitor agent exists. Create it once with `python monitor.py --setup` (USE_LIVE=true).

## How a Cycle Works

1. **Batch the watchlist in threes.** Coverage is the reason, not speed: measured row coverage was
   100% at 3 entities per run, 62% at 8, and 10% at 12 — and the 12-entity run still reported
   `high` confidence on 10% of the data. Small batches run concurrently, so wall-clock is ~one run.
2. **Start one run per batch** with `nimble_agent_run_start`, then poll `nimble_agent_run_status`
   tens of seconds apart. Runs take 3-10 minutes. Never busy-poll.
3. **Fetch each result** with `nimble_agent_run_result`. Each finding carries a description, the
   date the event happened, per-claim confidence and a citation.
4. **Record into the ledger.** Deduped on `(business, signal, event_month)` — never on the text.
   First sighting wins, so re-finding an event never re-reports it.
5. **Report only events dated since the last cycle.** This is a date filter, not a comparison.
6. **Deliver** with `hermes send -t <platform>`, or print to stdout.

## Why the Ledger Exists

Do not try to detect change by comparing this cycle's text against last cycle's. It does not work,
and it fails in a way that looks like it is working. Measured over two cycles eight minutes apart,
where the truth is zero change:

| method | false alarms |
|---|---|
| exact text match | 49 |
| extracting facts from the text | 37 |
| asking the agent for a stable label | 49 |
| asking a model to compare the two | 19 |
| **dated ledger** | **0** |

The research is not reproducible enough to diff: each run surfaces a different subset of true
facts. So when something appears today and not yesterday, the data cannot tell you whether it just
happened or was simply missed. The event's own date can.

## Rules

- An event whose date cannot be established is **recorded but never reported**. We cannot prove it
  is new, and a monitor that cries wolf gets muted.
- A `low` confidence claim means unverified, not false. Never raise an alert from one.
- Confidence and citations are **per field**, never per business. A row typically carries ~25 high
  claims beside a few low ones; collapsing that to one row-level value throws away good signals.
- `headcount_signal` is a **state**, not an event. Only report it when the count has moved more
  than 5% against the previous reading, and show the move.
- When nothing has changed, say so in one line and stop. Silence is the correct output.

## Scheduling

```bash
hermes cron create --name account-monitor --schedule "0 8 * * *" \
  --command "python monitor.py --deliver slack"
hermes cron tick        # run due jobs once, for testing
```
