# Prerequisites — Autonomous SEO Strategist

## System
- Python 3.9+
- pip
- git
- Node.js (required by Nimble CLI)

## Nimble
- **Nimble CLI** — install via npm: `npm install -g @nimbleway/nimble`
- **nimble-python** — install via pip: `pip install nimble-python`
  - Note: `nimble-python` is missing from `requirements.txt` — this is a known bug. Install it manually until fixed.

## Python packages
Install with `pip install -r requirements.txt`:
- `anthropic>=0.40.0`
- `python-dotenv>=1.0.0`
- `streamlit>=1.35.0`
- `plotly>=5.0.0`
- `pandas>=1.5.0`

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Phases 1, 3, 5 (extract, map, search) | https://nimbleway.com |
| `ANTHROPIC_API_KEY` | Phases 4, 6, 7, 8 (Claude analysis) | https://console.anthropic.com |

Neither key is needed to run the bundled Stripe.com dashboard.

## Two usage paths

**Path A — Explore the bundled dashboard (no API keys needed)**
- Dataset already included: stripe.com run, 47 pages, 30 terms, full report
- Just install requirements and run: `python3 -m streamlit run dashboard/app.py`

**Path B — Run full pipeline on your own domain**
- Both API keys required
- Edit `config/analysis_config.json` with your target domain
- Run: `python3 run_analysis.py`
