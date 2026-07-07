# EarningsIQ — Agent Setup Guide

EarningsIQ is an AI-powered earnings analysis dashboard built on Next.js, deployed on Vercel, and powered by **Nimble APIs** for live web data and **Claude AI** for analysis.

**Live URL:** https://nimble-earnings-dashboard.vercel.app

---

## What it does

1. User enters a stock ticker (e.g. `NVDA`)
2. Nimble searches for the latest and prior earnings transcripts on Seeking Alpha / Motley Fool
3. Nimble extracts full content from those pages
4. Claude analyzes the content and returns structured JSON covering:
   - EPS and revenue beat/miss vs. estimates
   - Guidance changes vs. prior quarter
   - 8-quarter EPS surprise history
   - Key metrics (gross margin, operating margin, FCF)
   - Analyst sentiment (bullish/neutral/bearish %)
   - Bull case and bear case summary
   - Transcript highlights (notable management quotes)
5. Yahoo Finance provides live 2-year price history
6. Nimble searches for upcoming earnings dates for the watchlist

---

## Stack

| Layer | Tech |
|---|---|
| Framework | Next.js 14 (App Router, TypeScript) |
| Styling | Tailwind CSS + shadcn/ui |
| Charts | Recharts |
| AI Analysis | Anthropic Claude (`claude-opus-4-5`) |
| Web Data | Nimble Web API (search + extract) |
| Price Data | Yahoo Finance public chart API |
| Deployment | Vercel |
| Watchlist | Browser localStorage |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NIMBLE_API_KEY` | ✅ | Nimble Web API key — used for all search + extract calls |
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API key — used to run Claude analysis |

Without `ANTHROPIC_API_KEY` the app still works, falling back to structured demo data. Without `NIMBLE_API_KEY` the app falls back entirely to demo data.

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/charliek-dot/earnings-dashboard.git
cd earnings-dashboard

# 2. Install dependencies
npm install

# 3. Set environment variables
cp .env.local.example .env.local
# Edit .env.local and add your keys:
#   NIMBLE_API_KEY=your_key_here
#   ANTHROPIC_API_KEY=your_key_here

# 4. Run dev server
npm run dev
# → http://localhost:3000
```

---

## Project Structure

```
earnings-dashboard/
├── app/
│   ├── page.tsx                    # Landing page with ticker search
│   ├── dashboard/[ticker]/page.tsx # Main earnings dashboard
│   ├── watchlist/page.tsx          # Watchlist + earnings calendar
│   └── api/
│       ├── earnings/route.ts       # → lib/earnings.ts
│       ├── price/route.ts          # → lib/price.ts
│       ├── upcoming/route.ts       # → lib/upcoming.ts
│       └── og/route.tsx            # OG image generation
├── components/
│   ├── price-chart.tsx             # Stock price + earnings overlay chart
│   ├── surprise-history.tsx        # 8-quarter EPS surprise bar chart
│   ├── guidance-tracker.tsx        # Guided vs actual grouped bar chart
│   ├── key-metrics.tsx             # Gross margin / op margin / FCF cards
│   ├── post-earnings-moves.tsx     # +1d / +5d price reaction table
│   ├── bull-bear-card.tsx          # Bull case / bear case panels
│   ├── transcript-highlights.tsx   # Notable management quotes
│   ├── sentiment-gauge.tsx         # Bullish/neutral/bearish %
│   ├── news-feed.tsx               # Analyst reaction articles
│   ├── watchlist-manager.tsx       # Watchlist + calendar (localStorage)
│   └── watch-button.tsx            # Watch/unwatch toggle on dashboard
├── lib/
│   ├── earnings.ts                 # Nimble search + extract + Claude analysis
│   ├── price.ts                    # Yahoo Finance price data + earnings dates
│   └── upcoming.ts                 # Upcoming earnings date lookup via Nimble
└── types/earnings.ts               # Shared TypeScript interfaces
```

---

## How Nimble is Used

### Search (`POST /v1/realtime/serp`)
Called in three places:
- **Latest earnings transcript** — searches Seeking Alpha / Motley Fool for the most recent results
- **Prior earnings transcript** — same for the previous quarter (for comparison)
- **Analyst reactions** — searches for price target changes, upgrades/downgrades after earnings
- **Upcoming earnings dates** — searches earnings calendar sites for each watchlist ticker

```ts
await fetch('https://api.nimbleway.com/v1/realtime/serp', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${NIMBLE_API_KEY}` },
  body: JSON.stringify({
    query: `${ticker} earnings transcript Q4 2024 site:seekingalpha.com`,
    search_engine: 'google_search',
    num_results: 5,
    country: 'US',
  }),
})
```

### Extract (`POST /v1/realtime/url`)
Called on the top URLs returned by search to get full page content as markdown:

```ts
await fetch('https://api.nimbleway.com/v1/realtime/url', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${NIMBLE_API_KEY}` },
  body: JSON.stringify({
    url: 'https://seekingalpha.com/article/...',
    render: true,
    output_format: 'markdown',
  }),
})
```

---

## Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd earnings-dashboard
vercel --prod

# Set env vars in Vercel dashboard or via CLI:
vercel env add NIMBLE_API_KEY
vercel env add ANTHROPIC_API_KEY
```

The `vercel.json` sets a 60-second timeout on the `/api/earnings` route (Nimble + Claude calls can take 10–30 seconds for a full analysis).

---

## Watchlist & Google Calendar

The watchlist is stored in `localStorage` — no backend or auth required. Each ticker's upcoming earnings date is fetched via Nimble search. Calendar entries link directly to Google Calendar's pre-filled event URL:

```
https://calendar.google.com/calendar/render?action=TEMPLATE
  &text=NVDA+Earnings+—+Q2+2025
  &dates=20250828/20250829
  &details=NVIDIA+Q2+2025+earnings+release...
```

No Google OAuth is required — the user just clicks "Save" in Google Calendar.
