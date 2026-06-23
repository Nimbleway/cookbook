# Prerequisites — EV Deal Finder

## System
- Python 3.9+
- pip
- git
- Node.js (required by Nimble CLI)

## Nimble
- **Nimble CLI** — install via npm: `npm install -g @nimbleway/nimble`
- **nimble-python** — install via pip: `pip install nimble-python`
  - Note: `nimble-python` is listed in `requirements.txt` and will install automatically.

## Python packages
Install with `pip install -r requirements.txt`:
- `nimble-python`
- `python-dotenv`
- `streamlit`
- `plotly`
- `pandas`

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Refreshing the dataset from eBay and Carvana | https://nimbleway.com |

No API key is needed to run the dashboard with the included dataset.

## Two usage paths

**Path A — Run the dashboard with included data (no API keys needed)**
- 818 pre-scored EV listings already included in `data/listings.json`
- Just install requirements and run: `streamlit run app.py`

**Path B — Refresh the dataset with live listings**
- `NIMBLE_API_KEY` required
- Uses WSA agents: `ebay_search_results_community_2026_03_23`, custom Carvana agent
- See `BUILD_RECAP.md` for full collection approach
