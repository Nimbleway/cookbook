# influencer-finder — Influencer Finder

Build an outreach-ready influencer dataset for any niche. Describe who you want — a niche, platform, follower band, and geography — and a [Nimble](https://nimbleway.com) Web Search Agent discovers matching creators with their handle, follower count, engagement, and profile URL. Run several queries and the dataset accumulates in Supabase, deduplicated.

![Built with Nimble + Supabase](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20Supabase-edc602)

## What it does

1. **Query** — describe a segment, e.g. "sustainable-fashion micro-influencers on Instagram, 10k–100k followers, US"
2. **Discover** — a `dataset_building` agent searches the named platforms and creator directories and returns matching creators: handle, platform, follower count, engagement, niche, location, public contact, profile URL
3. **Accumulate** — each query's results are parsed, standardized, and upserted into a Supabase `influencers` table, deduplicated on `(platform, handle)`; run more queries to grow the dataset
4. **Work the list** — a Streamlit dashboard filters by platform / category / follower size and exports the current view to CSV

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — one `dataset_building` agent per query; hard filters on niche, platform, follower band, geography
- [Supabase](https://supabase.com) — the `influencers` table (hosted Postgres); the dataset accumulates here across queries
- [Streamlit](https://streamlit.io) — the dashboard, filters, and CSV export
- [pandas](https://pandas.pydata.org) — dedup, follower parsing, sorting
- Python 3.10+

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/influencer-finder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY; Supabase optional (see below)
```

The repo ships a 120-influencer demo cache, so the dashboard runs immediately with no keys:

```bash
streamlit run app.py
```

To run discovery live:

```bash
python setup_agent.py    # creates the agent (once; id in agents.json)
python discover.py       # runs each query in data/queries.txt, ~15-20 min each, resumable
```

## Supabase (optional store)

Without Supabase creds the app reads/writes the local cache (`data/influencers.json`). To use the live backend:

1. Create the table once — paste `schema.sql` into the Supabase SQL editor.
2. Set `SUPABASE_URL` and `SUPABASE_KEY` (service role) in `.env`.

`discover.py` then upserts into the `influencers` table (dedup on `platform, handle`) and the dashboard reads from it. If the table or creds are missing, it falls back to the cache automatically.

## Usage

Queries live one-per-line in `data/queries.txt` (niche + platform + follower band + geography). A single query returns ~5–15 creators; the point is to run several and accumulate. `discover.py` caches each query's raw result to `data/raw/<slug>.json` and rebuilds the deduped dataset; rerunning skips completed queries and retries failed ones. `--build-only` rebuilds the dataset from cache with no API calls.

## Project structure

```
├── config.py          # env, paths, Supabase creds
├── agent_config.py    # the discovery agent config
├── setup_agent.py     # creates the agent
├── discover.py        # run queries (resumable), parse, dedup, upsert Supabase + cache
├── supabase_store.py  # Supabase client: upsert / fetch, graceful fallback
├── schema.sql         # the influencers table DDL
├── app.py             # Streamlit dashboard (filters + CSV export)
├── data/queries.txt   # the discovery queries
├── data/raw/*.json    # cached agent results (the demo cache)
└── data/influencers.json  # the built dataset the dashboard reads
```

## Output

The `influencers` table / `data/influencers.json`, one row per creator:

| column | contents |
|---|---|
| `platform` | normalized platform (TikTok, Instagram, YouTube, X, LinkedIn) |
| `handle` | creator handle |
| `category` | clean query-derived category (the discovery segment) |
| `follower_count` / `follower_count_num` / `followers_display` | verbatim, parsed integer, and standardized K/M form |
| `engagement_rate` | verbatim engagement when shown |
| `niche` | the agent's free-text niche label |
| `location`, `contact` | geography; public business email when listed |
| `profile_url` | the creator's real profile page |
| `query`, `observed_at` | provenance |

## Going further

- **More coverage** — add queries to `data/queries.txt` (more niches, platforms, geographies) and rerun; the dataset accumulates and dedupes
- **Scoring** — add a fit score per creator against a brief and sort by it
- **Any vertical** — the agent is niche-agnostic; B2B (LinkedIn), gaming (YouTube/TikTok), etc. all work

## Notes

- **A single run returns ~5–15 creators**, not hundreds; the dataset grows by running many queries (the demo ships 15 queries → 120 creators)
- **Follower counts are standardized** to K/M form from the parsed number, so mixed agent formats ("48.2K", "50,290") display consistently
- **Platform casing is normalized** so "tiktok" and "TikTok" don't split the filter
- **Public contact only** — the agent returns a business email only when publicly listed, else null; it never guesses
- **Resumable** — failed/timeout queries are retried on the next run; only completed ones are skipped
