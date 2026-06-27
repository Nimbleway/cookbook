# Prerequisites — Financial Comparison Agent

## System
- Python 3.9+
- pip
- git

## Nimble
- **nimble-python** — install via pip: `pip install nimble-python`
  - Note: listed in `requirements.txt` and installs automatically. The Nimble CLI is not required — this app calls the Python SDK directly.

## Python packages
Install with `pip install -r requirements.txt`:
- `nimble-python`
- `langchain`, `langgraph`, `langchain-anthropic`
- `chainlit`
- `supabase`
- `pandas`, `plotly`
- `python-dotenv`

## API keys & services
This is a live agent with no bundled dataset — **all of the following are required.** Set them in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Live financials, peer discovery, catalysts | https://nimbleway.com |
| `ANTHROPIC_API_KEY` | Claude — peer curation, tool loop, verdict | https://console.anthropic.com |
| `SUPABASE_URL` | Persisting / reopening runs | Supabase → Project Settings → API |
| `SUPABASE_KEY` | Backend writes (use `service_role` / `sb_secret_…`, not anon) | Supabase → Project Settings → API |

## Supabase setup
1. Create a free project at https://supabase.com.
2. In **SQL Editor**, run the contents of `supabase_setup.sql` to create the `comps_runs` and `comps_metrics` tables.
3. Copy the **Project URL** and a **`service_role`** (or `sb_secret_…`) key from **Project Settings → API** into `.env`.

## Run
```bash
chainlit run app.py
```
Opens at http://localhost:8000
