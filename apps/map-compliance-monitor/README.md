# map-compliance-monitor — MAP Compliance Monitor

A brand's protected SKUs go in; every online seller undercutting the Minimum Advertised Price comes out — each with cited evidence, ranked by repeat offender, and filed into a Google Sheets enforcement tracker with a Google Doc notice per case. One [Nimble](https://nimbleway.com) Web Search Agent discovers every seller of a product across the **open web** (not a fixed retailer list — that's where gray-market violations hide); the app computes the violations deterministically and acts on them.

![Built with Nimble + Google Workspace](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20Google-edc602)

## What it does

1. **Discover** — for each SKU, a `dataset_building` agent searches the open web for every seller offering that exact product, capturing the advertised price with a cited excerpt and source URL. Sources use empty-domain **category groups** (marketplaces, independent stores, discounters) — a steer, not a whitelist — so unauthorized long-tail sellers surface, not just Amazon/Walmart
2. **Detect** — the app parses each advertised price and flags below-MAP violations **deterministically** (`advertised_price < MAP`). The legally-consequential math is auditable code, never an LLM judgment
3. **Rank** — violations roll up by **seller domain** into a repeat-offender leaderboard: who undercuts the most of your SKUs, and by how much (avg / max gap %)
4. **Act** — the full violation list writes to a **Google Sheets** enforcement tracker (the worklist); the most severe cases get a **Google Doc** notice each (seller, listing URL, advertised price vs MAP, gap, cited evidence). No Google credentials? It falls back to local `.md` notices + a CSV tracker
5. **Investigate** — a Streamlit dashboard leads with the discovery-fan-out headline (listings × sellers × violations), the leaderboard, and a per-violation evidence drill-down

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — one `dataset_building` agent: open-web seller discovery per SKU, with field-level trust (every price maps to a citation)
- [Google Sheets + Docs](https://developers.google.com/workspace) — the enforcement tracker and per-violation notices (optional; local fallback when absent)
- [Streamlit](https://streamlit.io) + [Altair](https://altair-viz.github.io) — the dashboard (severity-coded, repeat-offender leaderboard, evidence drill-down)
- [SQLite](https://sqlite.org) — the offers/violations store
- Python 3.10+ — resumable concurrent discovery, deterministic violation math

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/map-compliance-monitor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Keys you need: `NIMBLE_API_KEY` ([nimbleway.com](https://nimbleway.com)). Google is **optional** — set `GOOGLE_SA_JSON` / `GOOGLE_SHEET_ID` / `GOOGLE_DRIVE_FOLDER_ID` to write the tracker + notices to Google Workspace; leave them unset to use the local fallback. See `.env.example` comments.

The repo ships a full pre-built demo cache (50 SKUs of discovery results in `data/`), so the dashboard runs immediately with no API calls:

```bash
streamlit run app.py
```

To run the pipeline live end-to-end:

```bash
python setup_agent.py        # creates the Web Search Agent (once; id in agents.json)
python discover.py           # one run per SKU, resumable, ~19 min/SKU @ concurrency 8
python compute_violations.py # deterministic below-MAP detection + seller rollup
python actions.py            # writes the tracker + notices (Google or local fallback)
streamlit run app.py
```

Or all at once: `python run_all.py` (add `--limit 3` for a quick sample).

## Usage

The brand's protected SKUs live in `data/skus.csv` (`sku_id, brand, product_name, size, map_price`) — the demo ships 50 professional-haircare SKUs (Olaplex + Kérastase) with their MSRP as the MAP. Discovery runs one agent per row; `compute_violations.py` joins each seller's advertised price against that SKU's MAP and flags anything lower.

Point it at a different brand by replacing `data/skus.csv` and rerunning. Discovery is resumable — rerunning `discover.py` skips SKUs already fetched; `--skus OLA-002,KER-003` targets specific rows.

## Project structure

```
├── config.py            # env, paths, concurrency, severity/notice thresholds
├── agent_config.py      # the canonical Web Search Agent config (open-web sources) + per-SKU prompt
├── setup_agent.py       # creates the agent (id saved to agents.json)
├── discover.py          # resumable concurrent discovery: one run per SKU, re-attaches to in-flight runs
├── compute_violations.py# deterministic price parse + below-MAP detection + seller-domain rollup -> SQLite + JSON
├── actions.py           # Google Sheets tracker + Google Doc notices, with local .md/CSV fallback
├── test_google.py       # read-only preflight: confirms the service account can reach the Sheet + Drive folder
├── app.py               # Streamlit dashboard (KPIs, severity, leaderboard, evidence drill-down)
├── run_all.py           # one-command pipeline
├── data/skus.csv        # the protected SKU list + MAP
├── data/raw/*.json      # full agent results per SKU (the demo cache; provenance for every price)
└── data/*.json          # built cache the dashboard reads: offers, violations, seller_rollup, summary
```

## Output

`compute_violations.py` writes both JSON (for the dashboard) and SQLite (`data/mcm.db`):

| artifact | contents |
|---|---|
| `offers` (table + `offers.json`) | one row per distinct seller listing: seller name/domain/type, advertised price (raw + parsed), currency, in-stock, listing URL, cited evidence excerpt + URL, price-claim confidence |
| `violations` (table + `violations.json`) | offers where `advertised_price < map_price`: adds gap ($ and %), MAP, and the cited evidence |
| `seller_rollup.json` | repeat-offender leaderboard by seller domain: distinct SKUs undercut, total listings, avg/max gap % |
| `summary.json` | headline totals: listings scanned, unique sellers, violations, sellers in violation, top offender |
| Google Sheet | the enforcement tracker: every violation as a row, low-confidence prices flagged "verify manually" |
| Google Docs | one notice per most-severe violation, in the configured Drive folder |

## Going further

- **Different brand or category** — replace `data/skus.csv` with any products + their MAP; the agent is domain-agnostic
- **Recurring monitoring** — schedule `discover.py` + `compute_violations.py`; diff `violations.json` between runs to alert on new violators (the production Monitor story)
- **Deeper recall on thin SKUs** — `discover.py` flags SKUs returning few sellers; re-run just those at higher effort with `python discover.py --skus <ids> --effort max --force`
- **Real MAP vs MSRP** — the demo uses MSRP as a MAP proxy; drop in the brand's actual MAP sheet for true violations

## Notes

- **Open-web sources are a steer, not a whitelist.** The agent's `sources.allow` uses empty-domain category groups so it can surface unauthorized/independent sellers. Listing concrete domains would turn it into a whitelist and hide exactly the gray-market violations MAP monitoring exists to catch
- **Seller identity = domain.** Marketplace 3P seller names are noisy free-text ("(Walmart Marketplace)", "sold by X", casing); the domain is the deterministic, enforceable unit (one Brand Registry takedown per marketplace)
- **Prices are strings until parsed.** The agent returns advertised prices verbatim; `compute_violations.py` parses them deterministically caller-side (handles `$`, currency suffixes, commas)
- **Run time.** Open-web discovery averages ~15–25 min per SKU; `discover.py` runs them concurrently and is resumable (re-attaches to in-flight runs, so an interrupted batch never wastes credits)
- **Trust policy.** Low-confidence price claims still appear in the tracker but are flagged "verify manually" and excluded from auto-generated notices — a wrong violation notice is worse than a missed one
- **Google storage.** A service account has no personal Drive quota, so Doc notices must target a **Shared Drive** folder (Workspace); the code sets `supportsAllDrives`. The Sheet tracker works on any shared Sheet
