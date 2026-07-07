# EarningsIQ — AI-Powered Earnings Analysis Dashboard

A full-stack web app that watches for a stock's latest earnings release, pulls the transcript and analyst reactions via **Nimble**, and uses **Claude** to summarize what changed vs. prior guidance — with a live price overlay chart, earnings calendar watchlist, and one-click Google Calendar integration.

Built on **Nimble Web API** (search + extract), **Claude** (analysis), and **Next.js** (full-stack framework). Deployed on Vercel.

**Live demo:** https://nimble-earnings-dashboard.vercel.app

---

## What it does

Enter any stock ticker (e.g. `NVDA`) and the app:

1. **Finds earnings content** — Nimble searches for the latest and prior earnings transcripts on Seeking Alpha and Motley Fool, then extracts full page content
2. **Analyzes with Claude** — Claude reads the transcripts and returns structured JSON: EPS/revenue beat vs. miss, guidance changes, analyst sentiment, bull/bear case, and notable management quotes
3. **Shows what changed** — color-coded bullet list of positives, negatives, and neutral changes vs. the prior quarter
4. **Overlays price + earnings** — 2-year stock price chart with vertical markers at each earnings date; switch between 6M / 1Y / 2Y views
5. **Tracks sentiment** — bullish/neutral/bearish % from analyst reactions pulled via Nimble news search
6. **Watchlist + Calendar** — save tickers, see upcoming earnings on a month calendar, add events to Google Calendar in one click (no OAuth required)

### Dashboard sections

| Section | What it shows |
|---|---|
| Price + Earnings chart | 2-year price history with earnings date overlays |
| Post-earnings moves | +1 day and +5 day price reaction for last 4 earnings |
| What Changed | Claude's color-coded changes vs. prior guidance |
| Bull / Bear Case | Two-paragraph summary of strongest arguments each way |
| EPS Surprise History | 8-quarter bar chart of beat/miss % |
| Guidance vs. Actual | Grouped bars comparing management's guidance to delivery |
| Key Metrics | Gross margin, operating margin, FCF with trend arrows |
| Transcript Highlights | 3 notable quotes from management with sentiment badges |
| Analyst Sentiment | Bullish / neutral / bearish % gauge |
| Analyst Reactions | News articles with sentiment labels |

---

## How it works

```
ticker ──▶ ┌──────────────────── Next.js server component ─────────────────────────┐
           │                                                                         │
           │  nimbleSearch(latest transcript)  ──▶  nimbleExtract(top URLs)         │
           │  nimbleSearch(prior transcript)   ──▶  nimbleExtract(top URLs)         │
           │  nimbleSearch(analyst reactions)  ──▶  nimbleExtract(top URLs)         │
           │                     │                                                   │
           │                     ▼                                                   │
           │            Claude (claude-opus-4-5)                                     │
           │            structured JSON response                                     │
           │                     │                                                   │
           └─────────────────────┼───────────────────────────────────────────────── ┘
                                 ▼
              Yahoo Finance chart API ──▶ price history
              Nimble search ──▶ upcoming earnings dates (for watchlist)
                                 │
                                 ▼
                        Next.js dashboard page
```

### How Nimble is used

| Call | Nimble surface | Purpose |
|------|---------------|---------|
| Latest transcript | **Search** → **Extract** | Find and read the most recent earnings results article |
| Prior transcript | **Search** → **Extract** | Same for the previous quarter, for comparison |
| Analyst reactions | **Search** → **Extract** | Price target changes, upgrades/downgrades post-earnings |
| Upcoming dates | **Search** | Find next earnings date for each watchlist ticker |

All Nimble calls go through `lib/earnings.ts`, `lib/price.ts`, and `lib/upcoming.ts` — server-side only, no client exposure of API keys.

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

## Prerequisites

- Node.js 18+
- A **Nimble** API key
- An **Anthropic** API key

---

## Setup

### 1. Install dependencies

```bash
cd apps/earnings-dashboard
npm install
```

### 2. Configure environment variables

```bash
cp .env.local.example .env.local
```

Edit `.env.local`:

```env
NIMBLE_API_KEY=your_nimble_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

> Without `ANTHROPIC_API_KEY` the app falls back to structured demo data — useful for testing the UI.
> Without `NIMBLE_API_KEY` all data comes from the fallback.

### 3. Run locally

```bash
npm run dev
# → http://localhost:3000
```

---

## Deploy to Vercel

```bash
npm i -g vercel
vercel --prod
# Set env vars when prompted, or via the Vercel dashboard
```

`vercel.json` sets a 60-second timeout on `/api/earnings` — Nimble + Claude calls can take 10–30 seconds for a full analysis.

---

## Project structure

```
apps/earnings-dashboard/
├── app/
│   ├── page.tsx                      # Landing page with ticker search
│   ├── dashboard/[ticker]/page.tsx   # Main earnings dashboard
│   ├── watchlist/page.tsx            # Watchlist + earnings calendar
│   └── api/
│       ├── earnings/route.ts         # → lib/earnings.ts
│       ├── price/route.ts            # → lib/price.ts
│       ├── upcoming/route.ts         # → lib/upcoming.ts
│       └── og/route.tsx              # Dynamic OG image (sharing previews)
├── components/
│   ├── price-chart.tsx               # Stock price + earnings overlay
│   ├── surprise-history.tsx          # 8-quarter EPS surprise bar chart
│   ├── guidance-tracker.tsx          # Guided vs actual grouped chart
│   ├── key-metrics.tsx               # Margin + FCF scorecard
│   ├── post-earnings-moves.tsx       # +1d / +5d price reaction table
│   ├── bull-bear-card.tsx            # Bull / bear case panels
│   ├── transcript-highlights.tsx     # Notable management quotes
│   ├── sentiment-gauge.tsx           # Bullish/neutral/bearish % bar
│   ├── news-feed.tsx                 # Analyst reaction articles
│   ├── watchlist-manager.tsx         # Watchlist + calendar UI
│   └── watch-button.tsx              # Watch/unwatch toggle
├── lib/
│   ├── earnings.ts                   # Nimble search + extract + Claude
│   ├── price.ts                      # Yahoo Finance + earnings dates
│   └── upcoming.ts                   # Upcoming earnings via Nimble
├── types/earnings.ts                 # Shared TypeScript interfaces
├── agent_setup.md                    # Detailed setup + Nimble API guide
└── vercel.json                       # Vercel config (timeouts)
```

---

## Watchlist & Google Calendar

The watchlist is stored in `localStorage` — no backend or auth required. Each ticker's upcoming earnings date is fetched via Nimble search. Clicking a calendar entry opens Google Calendar pre-filled:

```
https://calendar.google.com/calendar/render?action=TEMPLATE
  &text=NVDA+Earnings+—+Q2+2025
  &dates=20250828/20250829
  &details=NVIDIA+Q2+2025+earnings...
```

No Google OAuth required.
