# Agent Setup — Nimble Retail Intelligence

A Next.js 16 app that pulls live shelf data from Amazon, Walmart, and Target via Nimble SERP agents and generates AI-powered insights with Claude Sonnet. It includes a lead-capture form that forwards to HubSpot and an optional Slack webhook.

**Two modes:**
- **Demo Mode (default)** — deterministic mock data for 5 categories, no keys required.
- **Live Mode** — real-time Nimble agent calls, activated when `NIMBLE_API_KEY` is set.

---

## 1. Install dependencies

```bash
cd apps/nimble-retail-mini-app
npm install
```

Requires Node 20+.

---

## 2. Configure environment variables

```bash
cp .env.example .env.local
```

Then fill in `.env.local`:

| Variable | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | AI features | Claude Sonnet narrative + "Ask the data". Get one at console.anthropic.com |
| `NIMBLE_API_KEY` | Live Mode | Authenticates Nimble agent calls. Get one at app.nimbleway.com |
| `NIMBLE_AMAZON_SERP_AGENT_ENDPOINT` | Live Mode | Agent name or URL — default `amazon_serp` |
| `NIMBLE_WALMART_SERP_AGENT_ENDPOINT` | Live Mode | Agent name or URL — default `walmart_serp` |
| `NIMBLE_TARGET_SERP_AGENT_ENDPOINT` | Live Mode | Agent name or URL — default `target_serp` |
| `HUBSPOT_PORTAL_ID` | Lead capture | Found in the HubSpot form embed code |
| `HUBSPOT_FORM_GUID` | Lead capture | Found in the HubSpot form embed code |
| `HUBSPOT_REGION` | Lead capture | `na1` or `eu1` (default `eu1`) |
| `LEAD_WEBHOOK_URL` | Optional | Slack incoming webhook URL for instant lead pings |
| `NEXT_PUBLIC_CONTACT_EMAIL` | Optional | Fallback email shown in the lead form |
| `NEXT_PUBLIC_EVENT_NAME` | Optional | Set to show an event banner at the top |
| `NEXT_PUBLIC_BOOKING_URL` | Optional | Overrides the mailto fallback in the lead form |

Demo Mode works with **no keys at all**. Add only `ANTHROPIC_API_KEY` to enable the AI layer in Demo Mode.

---

## 3. Run locally

```bash
npm run dev
# → http://localhost:3000
```

To force Demo Mode even when Nimble keys are present (useful for offline testing):

```bash
FORCE_DEMO=1 npm run dev
```

Other useful commands:

```bash
npm run build        # production build — run this before deploying
npm run lint         # ESLint
npm run health       # checks that configured Nimble agents are reachable
```

---

## 4. Deploy

### Vercel (recommended)

```bash
npm install -g vercel
vercel              # preview deploy
vercel --prod       # production deploy
```

Set environment variables in the Vercel dashboard under **Project → Settings → Environment Variables**, or via CLI:

```bash
vercel env add ANTHROPIC_API_KEY
vercel env add NIMBLE_API_KEY
# etc.
```

### Netlify

A `netlify.toml` is already included. Connect the repo in the Netlify dashboard or use the CLI:

```bash
npm install -g netlify-cli
netlify deploy --build           # draft deploy
netlify deploy --build --prod    # production deploy
```

Set environment variables under **Site → Environment variables** in the Netlify dashboard.

---

## 5. Key files

| Area | File |
|---|---|
| Search API (streaming, parallel) | `src/app/api/search/route.ts` |
| AI narrative + Ask the data | `src/app/api/ask/route.ts` |
| Lead capture → HubSpot / Slack | `src/app/api/lead/route.ts` |
| Nimble agent calls + normalizer | `src/services/nimble-serp.ts` |
| Rule-based insight engine | `src/lib/insight-engine.ts` |
| Demo data (5 categories) | `src/lib/mock-data.ts` |
| Retailer + agent config | `src/lib/retailers.ts` |
| Contact / event config | `src/lib/config.ts` |
| Homepage hero | `src/components/hero-search.tsx` |
| Results layout | `src/components/results-experience.tsx` |
| Lead capture modal | `src/components/lead-modal.tsx` |

---

## 6. Architecture notes

```
User search
   ↓
/api/search  →  3 Nimble SERP agents IN PARALLEL  →  normalization
   ↓  (streams each retailer as it returns — NDJSON)
Rule-based insight engine  →  insight cards + KPIs  (renders immediately)
   ↓  (async, non-blocking)
Claude Sonnet  →  streaming narrative + Ask-the-data
```

- If one retailer fails, the other two still render — the experience never fully breaks.
- Claude is never on the critical path. Rule-based insights always render first.
- This is **Next.js 16** with React 19. APIs and conventions differ from older versions — read `node_modules/next/dist/docs/` before touching framework-level code.
