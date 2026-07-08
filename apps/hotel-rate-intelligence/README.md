# Rate Intelligence

A revenue-manager assistant that checks nightly rates for a hotel and its competitors across Booking.com and Expedia, flags rate parity issues and competitive undercutting, and produces a written rate-positioning summary.

Built with Next.js, Vercel AI SDK, Anthropic Claude, and Nimble for live data retrieval.

---

## Before you start

**Nimble API schema changes frequently.** The endpoint URLs and parameter names in `lib/nimble.ts` reflect the API as of mid-2025. Before deploying, verify the current request shape at https://docs.nimbleway.com. The two Nimble calls are:

- `lib/nimble.ts:nimbleSearch` (line ~45) - POST to `/v1/search` for listing URL discovery
- `lib/nimble.ts:nimbleExtract` (line ~75) - POST to `/v1/extract` for rate page content

If the current docs describe different parameter names or endpoint paths, update those two functions.

---

## Setup

### 1. Clone and install

```bash
git clone <repo>
cd rate-intel
npm install
```

### 2. Environment variables

Copy `.env.local` and fill in the required values:

```bash
cp .env.local .env.local.filled  # rename and edit
```

**Required for all modes:**

```
ANTHROPIC_API_KEY=    # your Anthropic API key
NIMBLE_API_KEY=       # your Nimble API key
```

**Required only for cron alerting mode:**

```
KV_REST_API_URL=      # Vercel KV REST URL (from Vercel dashboard)
KV_REST_API_TOKEN=    # Vercel KV REST token
SLACK_WEBHOOK_URL=    # Slack incoming webhook URL for alerts
CRON_SECRET=          # optional: a secret to authorize the cron endpoint
```

If you only want the on-demand check (no saved monitors, no cron), you do not need the KV or Slack variables.

### 3. Run locally

```bash
npm run dev
```

Open http://localhost:3000.

---

## Deployment

```bash
vercel deploy
```

Set all required environment variables in your Vercel project settings before deploying.

The cron job is configured in `vercel.json` to run daily at 08:00 UTC:

```json
{
  "crons": [
    {
      "path": "/api/cron",
      "schedule": "0 8 * * *"
    }
  ]
}
```

The cron endpoint hits `/api/cron`, which loads all saved monitor configs from Vercel KV and runs the same Search + Extract + reasoning flow as the on-demand UI. If results cross the configured threshold, it posts a Slack alert.

---

## Where the Nimble API calls happen

| Function | File | Nimble endpoint |
|---|---|---|
| `nimbleSearch` | `lib/nimble.ts:45` | POST `https://sdk.nimbleway.com/v1/search` |
| `nimbleExtract` | `lib/nimble.ts:75` | POST `https://sdk.nimbleway.com/v1/extract` |

`nimbleSearch` is called from `lib/tools.ts:searchOtaListingsImpl` during listing discovery.
`nimbleExtract` is called from `lib/tools.ts:extractRatePageImpl` during rate extraction.

Both are invoked from `lib/agent.ts:runRateIntelAgent`, which is the shared core function used by both the on-demand UI flow (`/api/agent`) and the cron flow (`/api/cron`).

---

## Architecture

```
app/page.tsx               - UI: form, progress stream, rate grid, flags, summary
app/api/agent/route.ts     - On-demand endpoint: streams SSE progress + final result
app/api/cron/route.ts      - Cron endpoint: runs headlessly for all saved configs
app/api/monitor/route.ts   - CRUD for monitor configs stored in Vercel KV

lib/agent.ts               - Core agent function (shared by UI and cron)
lib/tools.ts               - Nimble tool implementations + AI SDK tool wrappers
lib/nimble.ts              - Nimble API client (Search + Extract)
lib/kv.ts                  - Vercel KV operations for monitor configs and run history
lib/slack.ts               - Slack webhook notification
lib/types.ts               - TypeScript types
lib/dates.ts               - Date range and OTA date parameter utilities
```

The agent flow:
1. **Nimble Search** - finds OTA listing page URLs for each hotel
2. **Nimble Extract** - fetches each listing URL with JS rendering, returns markdown
3. Heuristic parser extracts rates, room types, review ratings from markdown
4. **LLM reasoning** (Claude) - normalizes room categories, flags parity issues and undercutting, generates summary

---

## Storage note

The on-demand check mode is stateless - nothing is persisted.

The cron alerting mode requires Vercel KV for two things:
1. Storing saved monitor configs (hotel, competitors, threshold, Slack URL)
2. Storing recent run results for each config (30-day TTL)

This is the one feature that makes the app non-stateless. If you want a rates history table with longer retention and query capabilities, replacing the KV store with a PostgreSQL table (`hotel_name, ota, date, rate, room_type, run_at`) would be the natural next step.

---

## Next steps (out of scope for v1)

**Review-sentiment analysis:** The current implementation pulls star rating and review count from the listing page markdown. Deeper sentiment analysis (scanning individual review text for recent complaint themes - noise, cleanliness, service) would require additional Extract calls per hotel and significantly more extraction volume. This would make rate gap context much richer but adds cost and latency.

**Additional OTAs:** The search query construction in `lib/tools.ts:searchOtaListingsImpl` and date parameter handling in `lib/dates.ts` are the two places to extend for additional OTAs (Hotels.com, Agoda, etc.). Each OTA has different URL structures and date parameter formats.

**Room-type normalization accuracy:** The current heuristic categorizer in `lib/tools.ts:categorizeRoom` is simple regex matching. A dedicated LLM call per room type (with the full room description) would be more accurate but adds latency. Alternatively, building a small lookup table of known room name patterns per OTA would be fast and predictable.
