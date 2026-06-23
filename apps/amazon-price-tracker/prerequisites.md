# Prerequisites — Amazon Price Intelligence Dashboard

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
- `streamlit`
- `pandas`
- `plotly`
- `pyarrow` — required for Parquet/efficient dataframe handling
- `requests`
- `python-dotenv`

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Collecting fresh Amazon data (Phase 1) | https://nimbleway.com |

No API key is needed to run the dashboard with the included dataset.

## Nimble agents used (REST API, not SDK)
- `amazon_pdp` — product detail pages (price, availability, reviews, best-seller rank)

## Two usage paths

**Path A — Run the dashboard with included data (no API keys needed)**
- Complete processed dataset already included: 479,000+ data points across 500 products and 10 zip codes
- Just install requirements and run: `streamlit run dashboard.py`

**Path B — Collect fresh data**
- `NIMBLE_API_KEY` required
- Run in order: `python phase1_collect.py` → `python phase1_process.py` → `python phase3_process.py` → `python phase4_process.py`
- Then: `streamlit run dashboard.py`
- Note: full collection requires scheduled hourly runs — see BUILD_RECAP for approach
