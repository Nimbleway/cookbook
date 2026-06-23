# Prerequisites — Real Estate Investment Scout

## System
- Python 3.9+
- pip
- git
- Node.js (required by Nimble CLI)

## Nimble
- **Nimble CLI** — install via npm: `npm install -g @nimbleway/nimble`
- **nimble-python** — install via pip: `pip install nimble-python`
  - Note: this app calls the Nimble REST API directly via `requests` and does not use the `nimble-python` SDK. Install nimble-python anyway so the user has it available for Claude Code inline use.

## Python packages
Install with `pip install -r requirements.txt`:
- `requests`
- `python-dotenv`
- `pandas`
- `pydeck` — 3D map rendering (no Mapbox token required, uses open tiles)
- `plotly`
- `streamlit`
- `anthropic`

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Phases 1 and 3 (Redfin + Zillow data collection) | https://nimbleway.com |
| `ANTHROPIC_API_KEY` | Phase 2 (Claude city scoring and ranking) | https://console.anthropic.com |

Neither key is needed to run the dashboard with the included dataset.

## Nimble agents used (REST API, not SDK)
- `redfin_market_housing_data_community_2026_05_02` — market stats for 100 cities
- `zillow_plp` — active property listings
- `perplexity` — city market reports

## Two usage paths

**Path A — Run the dashboard with included data (no API keys needed)**
- Complete dataset already included: 100 cities, 1,199 listings, 10 market reports
- Just install requirements and run: `streamlit run dashboard.py`

**Path B — Collect fresh data**
- Both API keys required
- Run phases in order: `python phase1_collect.py` → `python phase2_score.py` → `python phase3_collect.py`
- Then: `streamlit run dashboard.py`
