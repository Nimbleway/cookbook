# Prerequisites — Startup.Delivery

## System
- Python 3.11+
- Node.js 18+ (required for the web frontend)
- pip
- git

## Python packages
Install with `pip install -r agent/requirements.txt` (inside a venv):
- `fastapi` + `uvicorn` — agent bridge
- `requests` — Nimble + name.com HTTP calls
- `python-dotenv` — environment variable loading
- `pydantic` — data contracts (`schemas.py`)

## Node packages
Install with `npm install` inside `web/`:
- SvelteKit + Vite
- `html-to-image` — PNG receipt generation
- `@sveltejs/adapter-vercel` — Vercel deploy target

## API keys
Set in `.env` (copy from `.env.example`):

| Key | Required for | Where to get it |
|---|---|---|
| `NIMBLE_API_KEY` | Step 1 — live competitor recon (SERP + Extract) | https://nimbleway.com |
| `NAMECOM_USERNAME` + `NAMECOM_API_TOKEN` | Step 3 — domain availability + pricing | https://www.name.com (account settings → API) |
| `OPENROUTER_API_KEY` | Steps 2 & 4 — gap analysis, name generation, verdict, landing copy | https://openrouter.ai/keys |

Web app also needs `web/.env` (copy from `web/.env.example`):

| Key | Required for | Value |
|---|---|---|
| `AGENT_URL` | Pointing the web frontend at the agent bridge | `http://127.0.0.1:8787` (local) |
| `BRIDGE_SECRET` | Optional — must match agent `.env` if set | Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |

## Important: name.com production API
The app must use the **production** name.com API (`https://api.name.com`), not the sandbox.

The sandbox (`https://api.dev.name.com`) reports already-registered domains (e.g. `google.com`) as available, which defeats the purpose of the domain check. The app runs a control-check at startup and surfaces an honest provenance badge (`domainSource` on `/health`) — if it shows "sandbox", the username or token is pointed at the test environment.

## Nimble APIs used (REST, not SDK)
- SERP: `POST https://api.webit.live/api/v1/realtime/serp` — Google Search for competitor discovery
- Extract: `POST https://sdk.nimbleway.com/v1/extract` — competitor page extraction for positioning and pricing

## Two run modes

**CLI (agent only)**
- Python 3.11+, venv, `agent/requirements.txt`
- Nimble + name.com + OpenRouter keys
- `python -m agent.orchestrator "your idea here"`

**Full web app**
- All CLI requirements plus Node.js 18+ and `web/npm install`
- `./scripts/dev.sh` — boots bridge (:8787) + web UI (:5173)
- `MOCK=1 npm run dev` in `web/` for UI-only mode (no bridge, no API calls)
