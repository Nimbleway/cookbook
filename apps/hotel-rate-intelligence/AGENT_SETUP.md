# Agent Setup Guide

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/hotel-rate-intelligence
cp .env.example .env.local   # fill in your API keys
npm install
npm run dev                  # open http://localhost:3000
```

For deployment and cron alerting setup, see the sections below.

---

## API keys

You need two keys to run the app. Add them to `.env.local`.

**Nimble** (web data retrieval — required)
1. Sign up at [nimbleway.com](https://nimbleway.com)
2. Dashboard > API Keys > Create new key
3. Paste it as `NIMBLE_API_KEY` in `.env.local`

**Anthropic** (AI reasoning — required)
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. API Keys > Create Key
3. Paste it as `ANTHROPIC_API_KEY` in `.env.local`

---

## Where Nimble is used

This app uses two Nimble Web API endpoints. Both are in `lib/nimble.ts`.

**Search API** (`lib/nimble.ts` — `nimbleSearch` function)
Finds the Booking.com and Expedia listing page URLs for each hotel. Uses `search_depth: "lite"` (titles + URLs only, 1 credit per call) and `focus: "shopping"` to weight OTA property pages.

```
POST https://sdk.nimbleway.com/v1/search
Authorization: Bearer <NIMBLE_API_KEY>

{
  "query": "\"The Plaza Hotel\" New York site:booking.com hotel",
  "max_results": 5,
  "search_depth": "lite",
  "focus": "shopping",
  "include_domains": ["booking.com", "expedia.com"]
}
```

**Extract API** (`lib/nimble.ts` — `nimbleExtract` function)
Fetches each listing page with JS rendering enabled and returns markdown. OTA hotel pages are dynamic React/Vue apps — `render: true` and `driver: "vx10"` (stealth headless browser) are needed to get past bot detection and render nightly rates.

```
POST https://sdk.nimbleway.com/v1/extract
Authorization: Bearer <NIMBLE_API_KEY>

{
  "url": "https://www.booking.com/hotel/us/the-plaza.html?checkin=2025-07-12&checkout=2025-07-13&...",
  "render": true,
  "driver": "vx10",
  "formats": ["markdown"],
  "country": "US"
}
```

> The Nimble API schema evolves quickly. If you hit errors, verify the current parameter names at [docs.nimbleway.com](https://docs.nimbleway.com) — the two functions above are the only places that need updating.

---

## How the agent flow works

```
Input: your hotel + competitors + date range
         |
         v
1. Nimble Search  (lib/tools.ts: searchOtaListingsImpl)
   For each hotel, search booking.com + expedia to discover listing URLs
         |
         v
2. Nimble Extract  (lib/tools.ts: extractRatePageImpl)
   For each listing URL x each date: fetch page, extract rates + room types + reviews
   Runs in parallel batches of 5 to avoid rate limits
         |
         v
3. LLM Reasoning  (lib/agent.ts -- Claude claude-sonnet-4-6)
   Normalizes room categories (Standard / Deluxe / Suite)
   Flags rate parity issues (same hotel, different OTA rates >5% apart)
   Flags competitive undercutting (competitor below you for same room type)
   Contextualizes with review ratings ("priced below you AND rated higher")
   Calls out date-specific patterns (Fri/Sat only, weekday only, etc.)
   Produces a written summary a revenue manager can act on
         |
         v
Output: rate grid (hotel x date), flag list, written summary, source URLs
```

The core function is `lib/agent.ts: runRateIntelAgent`. It is called identically by:
- `app/api/agent/route.ts` -- on-demand UI check (streams SSE progress)
- `app/api/cron/route.ts` -- scheduled cron job (runs headlessly, sends Slack alert)

---

## Deploy to Vercel

```bash
vercel deploy --prod
```

Set environment variables in the Vercel dashboard (Settings > Environment Variables):

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | All modes |
| `NIMBLE_API_KEY` | Yes | All modes |
| `KV_REST_API_URL` | Cron only | From Vercel KV / Upstash Redis integration |
| `KV_REST_API_TOKEN` | Cron only | From Vercel KV / Upstash Redis integration |
| `SLACK_WEBHOOK_URL` | Cron only | Slack incoming webhook for alerts |
| `CRON_SECRET` | Optional | Bearer token to authorize the `/api/cron` endpoint |

After setting env vars, redeploy: `vercel deploy --prod`

---

## Cron alerting mode

The cron job runs daily at 08:00 UTC (configured in `vercel.json`). It calls `/api/cron`, which:

1. Loads all saved monitor configs from Vercel KV
2. For each config, runs the full Search + Extract + reasoning flow
3. If any competitor undercuts your rate by more than the configured threshold, posts a Slack alert

**Setting up Vercel KV (Upstash Redis)**
1. Vercel dashboard > your project > Storage > Connect Store > Upstash Redis (or KV)
2. Copy `KV_REST_API_URL` and `KV_REST_API_TOKEN` into your environment variables
3. Redeploy

**Setting up Slack alerts**
1. Go to [api.slack.com/apps](https://api.slack.com/apps) > Create New App > From scratch
2. Incoming Webhooks > Activate > Add New Webhook to Workspace > pick a channel
3. Copy the webhook URL and set it as `SLACK_WEBHOOK_URL`

Alternatively, set the webhook URL per monitor config in the UI (Cron monitor tab > New monitor > Slack webhook URL field). Per-config webhooks take precedence.

---

## Extending this app

**Additional OTAs**
The search query construction is in `lib/tools.ts: searchOtaListingsImpl`. The date parameter helpers are in `lib/dates.ts`. Each OTA needs its own URL filter pattern and date query string format.

**Review-sentiment analysis**
Currently pulls star rating and review count from the listing page markdown. Scanning individual review text for complaint themes (noise, cleanliness, service) would require additional Extract calls per hotel. The reasoning prompt in `lib/agent.ts` already has a placeholder for this context -- the main change is in the extraction step.

**Rates history table**
Replace the Vercel KV run-result storage with a PostgreSQL table: `(hotel_name, ota, date, rate, room_type, run_at)`. This enables trend queries ("is this competitor's gap widening?") that the current 30-day KV TTL does not support.

---

## Troubleshooting

- **All rates show "--"** -- the Extract calls are succeeding but the heuristic parser (`lib/tools.ts: parseRatesFromMarkdown`) is not finding price patterns. Check the raw markdown by adding a `console.log(markdown)` in `nimbleExtract`, then adjust the regex in `parseRatesFromMarkdown`.
- **Search returns no property pages** -- the URL filter in `searchOtaListingsImpl` may not match the current OTA URL structure. Add a `console.log(searchResults)` to see what Nimble is returning and adjust the `.filter()` condition.
- **Nimble Extract returns empty content** -- try switching `driver` from `vx10` to `vx10-pro` in `lib/nimble.ts`. Some OTAs require the headful stealth browser.
- **KV errors in cron mode** -- confirm `KV_REST_API_URL` and `KV_REST_API_TOKEN` are set and the KV store is linked to your Vercel project in the Storage tab.
