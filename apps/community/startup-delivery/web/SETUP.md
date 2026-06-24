# web/ — SvelteKit frontend

SvelteKit UI that proxies to the Python agent bridge (`agent/server.py`). No delivery logic in the frontend.

## Local dev

```bash
# Terminal 1 — agent bridge
source agent/.venv/bin/activate
uvicorn agent.server:app --port 8787 --reload

# Terminal 2 — UI (MOCK=1 works without the bridge)
cd web
npm install
npm run dev        # http://localhost:5173
```

Environment (optional, in `web/.env`):

```bash
AGENT_URL=http://127.0.0.1:8787
BRIDGE_SECRET=          # must match agent bridge if set
MOCK=1                  # SSE mock stream for UI-only dev
```

## Scripts

- `npm run dev` — Vite dev server
- `npm run build` — production build
- `npm run check` — `svelte-check`

## History

Past deliveries are stored in **browser localStorage** until a Tower list API exists. The History drawer reads that store.

## Deploy

Uses `@sveltejs/adapter-vercel` (see `svelte.config.js`). GitHub → Vercel import with root `web`; no CLI required.
