# market-mapper — Map Any Market with an ICP Prompt

A Streamlit app that turns an Ideal Customer Profile into a living market map — powered by [Nimble](https://nimbleway.com) Web Search Agents and LangChain. Describe the companies you're looking for in plain language; get back a Supabase table of real companies, each enriched with firmographics, funding, contacts, and buying signals — and every field carrying its own confidence score and citations.

![Market Mapper](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20LangChain-edc602)

## What it does

1. **Map** — a `dataset_building` agent discovers companies matching your ICP, treating size, geography, vertical, and funding stage as hard constraints. Companies already in your CRM are excluded via an upload list.
2. **Enrich** — an `enrichment` agent visits each discovered company and fills 12 fields: funding stage, total raised, investors, headcount, tech stack, key contacts with LinkedIn URLs, buying signals.
3. **Trust** — every enriched field carries a claim with its own citations and confidence (high/medium/low), straight from the Web Search Agents trust framework. Low-confidence rows are flagged, never hidden.
4. **Expand** — one click re-runs the mapper with `previous_interaction_id`, extending the same map with companies it hasn't returned yet.
5. **Chat** — ask natural-language questions over the full map ("who raised most recently?", "which companies have a VP Engineering listed?").
6. **Export** — download the enriched map as CSV; everything also lives in your Supabase tables.

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — discovery + enrichment agents, cloned from the `gtm-lead-discovery` and `lead-enrichment` gallery templates
- [LangChain](https://python.langchain.com) + [Claude](https://anthropic.com) — chat over the mapped dataset
- [Supabase](https://supabase.com) — Postgres storage for runs, companies, and trust data (free tier)
- [Streamlit](https://streamlit.io) — UI

## Setup

**1. Clone and install**

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/market-mapper
pip install -r requirements.txt
```

**2. Create the Supabase tables**

Create a free project at [supabase.com](https://supabase.com), then in **SQL Editor → New query**, paste and run `supabase/schema.sql`. This creates `mm_runs` and `mm_companies`.

> Free-tier projects pause after ~1 week of inactivity — restore from the dashboard if your project is asleep.

**3. Add your keys**

```bash
cp .env.example .env
```

Fill in: `NIMBLE_API_KEY` ([get one](https://nimbleway.com)), `ANTHROPIC_API_KEY` ([console](https://console.anthropic.com)), `SUPABASE_URL` + `SUPABASE_KEY` (project Settings → API, service_role key).

**4. Create your agents**

```bash
python setup_agents.py
```

Creates two Web Search Agents in your Nimble workspace (idempotent — safe to re-run) and writes their ids to `agents.json`.

**5. Run**

```bash
streamlit run app.py
```

## Usage

Describe an ICP — e.g. `"AI-powered vertical SaaS companies in healthcare, 11-200 employees, US or Israel, Series A or later"` — and click **Map the market**. Discovery takes several minutes (the agent is doing real research); enrichment fans out from there, 10 companies at a time.

`USE_LIVE=false` in `.env` replays the bundled sample dataset through the same code paths — useful for exploring the UI without API calls. A banner shows when sample data is active.

**Headless (no UI):** the full collection pipeline also runs from the command line — map, enrich, and land in Supabase without Streamlit:

```bash
python3 mapper.py "fintech infrastructure startups in Europe, seed to Series B" --exclude crm_domains.txt
```

This is the embed path: call `mapper.map_market()` / `mapper.enrich_pending()` directly from your own product or scheduler.

## Project structure

```
market-mapper/
├── setup_agents.py       # creates + configures the two Web Search Agents (run once)
├── mapper.py             # agents API client, map→enrich pipeline, expand, chat — also a headless CLI
├── app.py                # Streamlit UI
├── supabase/schema.sql   # table DDL — run once in the Supabase SQL editor
├── data/sample_run/      # verbatim raw responses from a real run (replay mode)
├── requirements.txt
└── .env.example
```

## Output

Two Supabase tables:

| Table | Contents |
|---|---|
| `mm_runs` | One row per mapping run: ICP prompt, exclusion list, run/interaction ids, raw discovery result |
| `mm_companies` | One row per company: 10 discovery fields, 12 enrichment fields, per-field `claims` (citations + confidence), verbatim raw responses, enrichment status |

## Going further

- **Raise the enrichment cap** — `ENRICH_CAP` in `.env` (each enrichment is one agent run; cost scales linearly)
- **Change the effort tiers** — edit `setup_agents.py` (`max` for discovery depth, `high`→`medium` for cheaper bulk enrichment)
- **Point it at any ICP** — the agents are domain-agnostic: fintech in Europe, robotics in Japan, CPG brands in LATAM
- **Tighten the sources** — the mapper's allow list is a hard whitelist; edit `MAPPER_SOURCES` to restrict discovery to the directories you trust

## Requirements

- Python 3.9+
- Nimble API key · Anthropic API key · Supabase free-tier project
