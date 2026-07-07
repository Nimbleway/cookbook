# Nimble Retail Intelligence Experience

A conference-ready demo that proves **live retail intelligence beats static Digital Shelf Analytics** — in under 30 seconds. Pick a category and instantly see who owns page-one search across **Amazon, Walmart, and Target**, why it matters, and what to do about it.

Built on [Nimble](https://nimbleway.com) Web Search Agents (live retailer data) + Claude Sonnet (AI analysis).

![Next.js](https://img.shields.io/badge/Next.js-16-black) ![Nimble](https://img.shields.io/badge/Data-Nimble-5b3df5) ![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet-d97757)

---

## Why this exists

Traditional DSA tools give you last week's data in a fixed dashboard. This experience answers **"what can Nimble tell me about my category right now?"** and is engineered for one outcome: a prospect saying *"I want to run my own category."*

- **Demo Mode (default)** — rich, realistic mock data for 5 categories. Zero config, instant wow.
- **Live Mode** — real-time Amazon/Walmart/Target search via Nimble agents (when configured).

## Quick start

```bash
npm install
cp .env.example .env.local   # add your ANTHROPIC_API_KEY (Nimble vars optional)
npm run dev                  # → http://localhost:3000
```

Demo Mode needs **no keys at all**. Add `ANTHROPIC_API_KEY` to enable the AI narrative and "Ask the data". Add Nimble vars to switch typed searches to live data.

## How it works

```
User search
   ↓
/api/search  →  3 Nimble SERP agents IN PARALLEL  →  normalization layer
   ↓ (streams each retailer as it returns — NDJSON, never waits for the slowest)
Rule-based insight engine  →  instant insight cards + KPIs   ← renders in seconds
   ↓ (async, non-blocking)
Claude Sonnet  →  streaming narrative + "Ask the data"
```

**Real-time signal modules** (what static reports can't show — powered by live agent fields):
- **Selling right now** — Amazon `recent_sales` velocity; surfaces what's actually *bought*, not just what ranks (the "demand ≠ visibility" aha).
- **Stockout radar** — live `out_of_stock` flags = a rival's slot to take *today*.
- **Live price move** — `price` vs `original_price` discount depth, captured this minute.
- **Who owns the default buy** — `amazons_choice` badge ownership.
- **Email me this report** — branded report via Resend (and lead capture either way).

**Design principles enforced in code:**
- **Insights before analytics** — hero answer → why it matters → what to do; tables come last and collapsed.
- **Never block on Claude** — rule-based insights render immediately; AI streams in after.
- **Fault tolerant** — if one retailer fails, the other two still render. The experience never fully fails.
- **Discovery-first** — click any retailer to see the shelf change; click any brand for a competitive drilldown.
- **CTAs after value** — "Book a custom audit" appears only once insights are on screen.

## Project structure

```
src/
  app/
    page.tsx                 # server: detects Live vs Demo, renders the app
    api/search/route.ts      # streaming NDJSON search (parallel, fault-tolerant)
    api/ask/route.ts         # Claude Sonnet streaming (summary + Ask-the-Data)
  lib/
    types.ts                 # normalized RetailerSerpResult + InsightPayload
    retailers.ts             # NIMBLE_AGENTS config + retailer metadata
    mock-data.ts             # deterministic Demo Mode data (5 categories)
    insight-engine.ts        # rule-based insights incl. cross-retailer
    ai-context.ts            # grounding context + analyst system prompt
    use-search.ts            # client hook: streams results, recomputes insights
    config.ts                # Conference Mode (NEXT_PUBLIC_*)
  components/                # hero, KPIs, insight cards, brand drilldown, Ask-the-data, …
  services/
    nimble-serp.ts           # live Nimble agent calls + tolerant normalizer
```

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | for AI | Claude Sonnet narrative + Ask-the-Data |
| `NIMBLE_API_KEY` | for Live | Authenticates Nimble agent calls |
| `NIMBLE_{AMAZON,WALMART,TARGET}_SERP_AGENT_ENDPOINT` | for Live | Agent name (e.g. `amazon_serp`) or full URL |
| `NEXT_PUBLIC_EVENT_NAME` | optional | Shows the Conference Mode banner |
| `NEXT_PUBLIC_BOOTH_NUMBER` | optional | Booth number in banner + CTA |
| `NEXT_PUBLIC_BOOKING_URL` | optional | "Book a custom audit" link |
| `NEXT_PUBLIC_BOOTH_URL` | optional | "Visit booth" link |

## Deploy

```bash
vercel            # preview
vercel --prod     # production
```

Set the env vars in the Vercel dashboard (or `vercel env add`). Demo Mode works on a fresh deploy with only `ANTHROPIC_API_KEY`.

## Spec

The product spec lives alongside the code: `PRD.md`, `UI_UX_GUIDELINES.md`, `TECHNICAL_ARCHITECTURE.md`, `NIMBLE_AGENT_INTEGRATION.md`, `AHA_MOMENT.md`.

---

Built by Solutions Consulting @ Nimble.
