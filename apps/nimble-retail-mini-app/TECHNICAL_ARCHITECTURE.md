# Technical Architecture

## Stack

Frontend:

* Next.js App Router
* TypeScript
* Tailwind CSS
* shadcn/ui

Deployment:

* Vercel

AI:

* Claude Sonnet

Data:

* Nimble API

Retailers:

* Amazon SERP Agent
* Walmart SERP Agent

---

# Environment Variables

```env
NIMBLE_API_KEY=

ANTHROPIC_API_KEY=

NEXT_PUBLIC_EVENT_NAME=
NEXT_PUBLIC_BOOTH_NUMBER=
NEXT_PUBLIC_BOOKING_URL=
```

---

# Architecture

services/

* nimbleClient
* serpAgentService
* retailerNormalizationLayer
* insightEngine
* aiSummaryService
* askDataService

---

# Data Flow

User Search

↓

Nimble SERP Agents

↓

Normalization Layer

↓

Insight Engine

↓

Immediate Insights

↓

Claude Summary

↓

Ask-The-Data

---

# Performance Requirements

Critical.

Users should receive value immediately.

Requirements:

* Progressive rendering
* Streaming responses
* Skeleton loading states
* Incremental retailer loading
* Async AI summaries

Never block on Claude.

---

# Normalized Schema

```ts
{
 retailer: string;
 keyword: string;
 rank: number;
 productTitle: string;
 brand: string;
 price: number;
 rating: number;
 reviewCount: number;
 sponsored: boolean;
 productUrl: string;
 imageUrl: string;
 availability: string;
 collectedAt: string;
}
```

---

# Insight Engine

Generate immediately:

* Visibility Leader
* Organic Leader
* Paid Leader
* Share Of Shelf
* Sponsored %
* Opportunity Score
* Competitive Intensity

Rule-based first.

AI second.

---

# Modes

## Demo Mode

Uses mock data.

Default.

## Live Mode

Uses Nimble APIs.

---

# Deliverables

* Production-ready application
* Vercel deployment ready
* README.md
* .env.example
* Mock data
* Error handling
* Loading states
* Mobile responsive UI
