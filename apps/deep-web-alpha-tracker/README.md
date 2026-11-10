# Deep Web Alpha Tracker

Deep web context on a 50-name tech watchlist, researched by nine Nimble Web Search Agents, so your fund sees signals before they reach consensus. Every datapoint carries citations and a confidence grade, and meaningful changes go to Slack.

![stack](https://img.shields.io/badge/Next.js-16-black) ![db](https://img.shields.io/badge/Supabase-Postgres-3ecf8e) ![nimble](https://img.shields.io/badge/Nimble-Web%20Search%20Agents-5b93f8)

## What it tracks

| Agent (gallery template) | What the tracker uses |
|---|---|
| Fundamental deep dive (`hf-fundamental-deep-dive`) | Moat factors and their trend, off-consensus signals, risks |
| Channel check (`hf-channel-check`) | Hiring, pricing, promotions, partner listings, lead times, incidents, each against a prior value |
| Filing change detector (`hf-filing-changes`) | Added, removed and modified disclosures in the latest 10-Q / 10-K |
| Forensic red-flag screen (`hf-forensic-red-flags`) | Auditor changes, restatements, SEC letters, related parties, short reports |
| Management track record (`hf-management-track-record`) | Commitments vs outcomes, leadership exits, Form 4 insider trades |
| Catalyst calendar (`hf-catalyst-calendar`) | Dated events with date certainty |
| Customer and supplier map (`hf-customer-supplier-map`) | Counterparties, disclosed revenue share, relationship status |
| Competitor momentum scan (`hf-competitor-momentum`) | Dated rival moves, including private companies |
| Government contract exposure (`hf-government-contracts`) | Awards, obligations vs ceilings, bid protests |

The merger arbitrage and credit agents from the same gallery set are left out: they track deals and borrowers, not a tech equity watchlist.

## Tabs

- **Watchlist**: one row per name with an alpha score (hover for its breakdown), channel momentum, hiring change, rivals gaining, forensic risk, management hit rate, insider net buying, next catalyst, government obligations, top customer share, confidence mix and source count. Click a row for the full evidence drawer.
- **Signal feed**: every meaningful change, filterable by agent and direction, with counts by agent, bullish vs bearish by sleeve, and net signal leaders and laggards.
- **Catalysts**: weekly catalyst density for the next 26 weeks and a dated table filterable by type and horizon.
- **Channel & competition**: a heatmap of channel-check changes across names and measures, plus the rivals gaining ground across the most names.
- **Risk & governance**: a forensic red-flag matrix, management credibility table and high-relevance filing changes.
- **Supply chain**: counterparties shared across the watchlist (hidden concentration) and disclosed customer concentration.
- **Government**: obligated vs ceiling by company, obligations by agency and every award and protest.

The **confidence filter** (high / medium / low) applies everywhere: rows below the selected grades drop out and every metric, score and chart recomputes. The **↗n** button on any row lists the pages behind it and whether each is a primary source.

## How data flows

1. **Refresh** (top right) queues one run per company × selected agent at the chosen effort (low, medium, high, x-high).
2. Runs start up to `MAX_CONCURRENT_RUNS` at a time. While the page is open it advances the refresh every 15 seconds; the daily Vercel cron advances it too.
3. Each finished run is mapped to rows (with confidence from the run's trust claims and citations), saved to Supabase, and diffed against the previous live result.
4. When the refresh finishes, changes of magnitude 2+ that are not low confidence are posted to Slack.

All data lives in Supabase (`supabase/schema.sql`): `dwa_companies`, `dwa_agent_data` (latest result per company × agent), `dwa_agent_history` (every result), `dwa_runs` (each Nimble run with its raw output), `dwa_refreshes` and `dwa_changes`.

Until the first refresh, the tracker shows a generated sample in the same shape as live results, marked **Sample data**. Live results replace sample rows cell by cell.

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook.git
cd cookbook/apps/deep-web-alpha-tracker
npm install
cp .env.example .env.local
```

1. **Supabase**: create a project, run `supabase/schema.sql` in the SQL editor, and set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
2. **Nimble**: set `NIMBLE_API_KEY`. Create the nine agents from the hedge fund gallery templates (agent names `gallery-hf-…`), then run `npm run agents:find` and paste the printed `NIMBLE_AGENT_*` lines into `.env.local`.
3. **Slack** (optional): set `SLACK_WEBHOOK_URL` to an incoming webhook and `APP_URL` to the deployed URL.
4. Load the watchlist and sample: `npm run seed`.
5. Run it: `npm run dev`.

### Deploy to Vercel

```bash
vercel link
vercel env add NIMBLE_API_KEY   # and the other variables in .env.example
vercel deploy --prod
```

Set `REFRESH_KEY` on a shared deployment so only people with the key can start runs.

## Run volume

A full refresh is 50 names × 9 agents = 450 runs. Nimble accounts default to 30 concurrent runs and 200 runs per day, so a full refresh at default limits spans more than one day: pick fewer agents in the refresh menu, or ask Nimble to raise the limits. At `high` effort a run costs $0.50 (see [efforts](https://docs.nimbleway.com/nimble-sdk/web-search-agents/efforts)).

## Project structure

```
app/page.tsx              loads the snapshot from Supabase
app/api/refresh/route.ts  GET status (advances an open refresh), POST start
components/               dashboard shell, tabs, company drawer, UI primitives
lib/agents.ts             agent registry: prompts and output mappers
lib/refresh.ts            run queue, result storage, diffing, Slack
lib/diff.ts               rules for meaningful changes
lib/metrics.ts            confidence filter, alpha score, KPIs
lib/sample.ts             sample snapshot
supabase/schema.sql       tables
scripts/seed.ts           loads companies and sample rows
scripts/find-agents.ts    prints agent IDs for .env
test/core.test.ts         mappers, diff rules, filter, Slack payload
```

`npm test` runs the unit tests.
