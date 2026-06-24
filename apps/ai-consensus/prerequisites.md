# Prerequisites — AI Consensus Dashboard

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
- `streamlit`
- `nimble-python`
- `anthropic`
- `plotly`
- `python-dotenv`

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Fetching live responses from ChatGPT, Perplexity, Gemini | https://nimbleway.com |
| `ANTHROPIC_API_KEY` | Claude Haiku consensus analysis | https://console.anthropic.com |

Neither key is needed to browse the pre-loaded dataset of 100 questions.

## Two usage paths

**Path A — Browse pre-loaded data (no API keys needed)**
- 100 pre-analyzed questions already included
- Just install requirements and run: `streamlit run app.py`

**Path B — Fetch live responses and re-analyze**
- Both API keys required
- Fetch: `python3 fetch.py` (~30 min, 300 parallel Nimble calls)
- Analyze: `python3 analyze.py` (~2 min, ~$0.16 in Anthropic credits)
