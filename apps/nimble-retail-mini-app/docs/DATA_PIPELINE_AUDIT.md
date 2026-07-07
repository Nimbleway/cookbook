# Data Pipeline Audit

**App:** Nimble Retail Intelligence Experience (conference/prospect-facing)
**Scope:** Where every widget's data comes from, how Nimble is integrated, and which insights are trustworthy vs. illustrative.
**Date:** 2026-06-01

---

## 0. TL;DR

- The app runs a **two-phase pipeline**: an instant **deterministic mock "preview"**, then a **live Nimble swap** (Amazon / Walmart / Target SERP agents).
- The **rule-based insight engine** (`src/lib/insight-engine.ts`) is honest and deterministic for everything *except* one module.
- **The single credibility risk is `buildFreshness()`** — the "this shelf is moving right now" content (rank moves, "changed N× today", "~Hh ago", "N new sponsored placements", the 9am→now timeline) is **fabricated from a keyword hash**, not from historical data.
- The genuinely **defensible, point-in-time signals are strong**: share-of-shelf, sponsored %, stockouts, live price/discount, demand velocity (`recentSales`), badges, cross-retailer fragmentation.
- Several **live fields are parsed but under-surfaced**: `pricePerUnit`, `seller` (1P/3P), `originalPrice`, `badge`, `rating`, `reviewCount`.

---

## 1. Data flow per module

`Component ↓ Source ↓ Transformation ↓ UI`

| Component | Source | Transformation | UI |
|---|---|---|---|
| **Hero insight** (`hero-insight.tsx`) | Live SERP (or mock preview) | `buildInsights` → peak single-retailer brand share | "Brand · X% of {Retailer}" + count-up |
| **AI summary line** (in hero) | Claude Haiku (`/api/insights`) | `streamObject` headline | Streamed italic sentence (non-blocking) |
| **KPI row** (`kpi-row.tsx`) | Live SERP | Deterministic counts (visibility leader, sponsored %, organic leader, share, opportunity score) | 4–5 stat tiles |
| **Insight cards** (`insight-cards.tsx`) | Live SERP → rule engine; top-3 swapped for Claude Haiku cards when ready | `buildInsights.cards` (≤8) / `insightsSchema` | Card grid (title/what/why/action/tone) |
| **Share of shelf** (`share-of-shelf.tsx`) | Live SERP | `computeBrandShare` (placements, organic/sponsored split, avg rank) | Ranked bars + logos |
| **Find your brand** (`find-your-brand.tsx`) | Live SERP `brandShare` | Client-side match → rank/share/gap; FOMO if absent | Result card + Share-of-Shelf highlight |
| **Selling now** (`selling-now.tsx`) | **Live only** (`recentSales`) | `topSelling` (parse "5K+", sort by velocity) | Velocity strip (demand ≠ visibility) |
| **Live shelf pulse** (`live-shelf-pulse.tsx`) | **Mixed — see §5** | `buildFreshness` (real stockouts/price + **hash-fabricated** rank/count/timeline) | "This shelf is moving" deltas + timeline + Re-scan |
| **Cached-vs-live** (`cached-vs-live.tsx`) | Mock preview vs live | Diff of `previewInsights` vs live `insights` | "Live just landed" banner |
| **Retail explorer** (`retail-explorer.tsx`) | Live SERP raw rows | Sort/filter `results[]` | Sortable product table |
| **Retailer tabs** (`retailer-tabs.tsx`) | Live SERP per retailer | Recompute `buildInsights` for one retailer | Amazon/Walmart/Target toggle |
| **Email report** (`report-html.ts`, `/api/report`) | Live SERP + optional Claude exec summary | Deterministic HTML; Claude adds 3–4 sentence summary (best-effort) | Branded HTML email |

---

## 2. Two-phase search flow

**Phase 1 — instant indexed preview** (`src/lib/use-search.ts` `demoResultsFor` → `getMockResults`)
- On search, the app renders a fully deterministic **mock** SERP + insights immediately (Nimble live pulls take ~9–15s; too long to stare at a spinner at a booth).
- Everything is mock at this stage: product rows, prices, ratings, `recentSales`, and all derived insights. Mock `collectedAt` is hardcoded (`2026-05-30T15:00:00.000Z`, `mock-data.ts`).
- Mock is seeded by `hashStr(category:retailer)` via `mulberry32`, so the same keyword always yields the same preview (stable demo).

**Phase 2 — live Nimble swap** (`/api/search` NDJSON stream)
- Client `fetch("/api/search", { keyword, mode: "live" })`; server streams one `{type:"retailer", result}` line per retailer as it settles, then `{type:"done"}`.
- Client keeps showing the preview while the "pulling live (n/3)" progress advances, then **swaps wholesale** to live and recomputes `buildInsights` (`liveSwapped: true`).
- One retailer failing never blocks the others (parallel `Promise.all`, explicit per-retailer `ok`/`error`).

**Cache** (`src/lib/live-cache.ts`)
- In-memory, 10-min TTL, keyed by lowercased keyword. Verified repeat pulls drop **21.6s → 0.39s**.
- `{ refresh: true }` bypasses the cache (force-fresh). Opt-in `PREWARM_LIVE=true` warms prepared categories on first live request.
- Per-instance memory (great on a booth machine / warm Fluid Compute instance; cold serverless instances start empty — only ever faster, never staler).

---

## 3. Nimble integration (`src/services/nimble-serp.ts`)

| Item | Detail |
|---|---|
| Endpoint | `POST https://sdk.nimbleway.com/v1/agents/run` (env URL override supported) |
| Auth | `Authorization: Bearer ${NIMBLE_API_KEY}`, `Content-Type: application/json` |
| Body | `{ agent, params: { keyword } }` |
| Agents | `amazon_serp`, `walmart_serp`, `target_serp` (override via `NIMBLE_<RETAILER>_SERP_AGENT_ENDPOINT` — full URL or agent name) |
| Timeout | 24s per retailer (`AbortController`); results capped at 24/retailer |
| Failure model | Per-retailer `{status:"error"}`; never fails the whole experience |
| Response | `data.parsing` → `findResultsArray()` (tries `results`/`products`/`organic_results`/`search_results`/`items`/`listings`/`data`, then recursive scan) → `normalizeRow()` |

### Field map (`RetailerSerpResult`)

| Field | Source aliases | Status |
|---|---|---|
| `rank` | `rank`/`position`/`index` (+1) | live |
| `productTitle` | `title`/`name`/`product_title`/… | live (row rejected if missing) |
| `brand` | `brand`/`brand_name`/`manufacturer` → else `deriveBrand(title)` | live / derived |
| `price` | `price`/`current_price`/`sale_price`/… | live, usually present |
| `rating` | `rating`/`stars`/`average_rating` | live, **under-surfaced** |
| `reviewCount` | `reviews`/`review_count`/`ratings_total` | live, **under-surfaced** |
| `sponsored` | `sponsored`/`is_sponsored`/`ad` | live |
| `imageUrl` | `image`/`image_url`/`thumbnail`/… | live, sometimes empty |
| `availability`/`inStock` | `product_out_of_stock` (Walmart bool) / `availability` regex | live |
| `badge` | `amazons_choice` / `prime_eligible` | live, **under-surfaced** |
| `recentSales` | `recent_sales`/`bought_recently`/`purchase_count` | **live, high-value, often empty** |
| `originalPrice` | `original_price`/`list_price`/`was_price` | live, **under-surfaced** |
| `pricePerUnit` | `price_per_unit`/`unit_price` | live, **under-surfaced** (true value/oz) |
| `seller` | `seller`/`sold_by` | live, **under-surfaced** (1P vs 3P) |
| `collectedAt` | synthesized `new Date().toISOString()` | derived |

**Available but not surfaced as insights today:** cross-retailer price spread for the same product, `pricePerUnit` true-value comparison, 1P/3P `seller` mix, `rating`/`reviewCount` as a quality signal. These are strong, defensible aha-moment candidates (see Roadmap §6).

---

## 4. Insight engine — Live vs Mock vs Hashed

`buildInsights(keyword, retailerResults)` (`src/lib/insight-engine.ts`)

| Output | Basis | Verdict |
|---|---|---|
| `heroInsight` | Peak single-retailer brand share | ✅ Deterministic from data |
| `kpis` (5) | Counts / Herfindahl concentration | ✅ Deterministic |
| `cards` (≤8) | visibility, sponsored, retailer-competitiveness, over-index, threat, demand-velocity*, stockout*, discount*, badge* | ✅ Deterministic (*live-signal-dependent) |
| `brandShare` / `perRetailer` | Aggregations | ✅ Deterministic |
| `topSelling` | Filter `recentSales`, parse, sort | ✅ Deterministic (empty without live `recentSales`) |
| **`freshness`** | **`hashKeyword` seed** | ⚠️ **Hash-fabricated — see §5** |

---

## 5. Data credibility audit

The app has **no historical snapshots** — every pull is a single point in time. Any UI that implies change-over-time is therefore unsupported. The fabrication is concentrated in `buildFreshness()` (`insight-engine.ts:367–445`) and its consumers.

### Flagged (illustrative presented as fact)

| Location | Quote | Backing | Severity |
|---|---|---|---|
| `insight-engine.ts:384` | `climbed to #1 on {Retailer} since this morning` | hash-seeded, no rank history | **HIGH** |
| `insight-engine.ts:427,435` | `climbed {spots} spots` (`spots = 2 + rng(3)`) | fabricated | **HIGH** |
| `insight-engine.ts:415,421` | `{newAds} new sponsored placements appeared` (`1 + rng(3)`) | fabricated count | **HIGH** |
| `live-shelf-pulse.tsx:~113–131` | "#1 on the shelf today" 9am→12pm→3pm→now timeline | illustrative fiction (top brands rotated) | **HIGH** |
| `insight-engine.ts:373,442–443` / `live-shelf-pulse.tsx:~96–100` | `changed {N}× today` / `~{H}h ago` | hash-seeded (18–33 / 14–22h) | **MEDIUM** |
| `cached-vs-live.tsx:~75–78,107` | "yesterday's snapshot" vs the **mock** preview | mock framed as a real historical report | **MEDIUM** |
| `find-your-brand.tsx:~245,250` | "yesterday's report can't show you" / "the moment it changes" | unsupported (single snapshot, no continuous monitoring) | **MED/LOW** |

Also note: the **Re-scan now** button (`live-shelf-pulse.tsx`) only **animates** (rotates the delta list, bumps the counter) — it does not re-pull Nimble, despite implying a fresh detection.

### Defensible right now (no history needed — lead with these)

- **Share of shelf** — brand placements, organic/sponsored split, avg rank (current SERP).
- **Sponsored %** — paid penetration of page one (current count).
- **Stockouts** — `inStock === false` on page one (real availability).
- **Price / discount** — `price` vs `originalPrice` right now; "retail prices change by the hour, a static report may already be wrong" is honest.
- **Demand velocity** — `recentSales` ("5K+ bought in past month") is a live aggregated signal; demand-vs-visibility contrast is two current facts.
- **Badges** — Amazon's Choice / Prime (current status).
- **Cross-retailer fragmentation** — concentration & sponsored differences across Amazon/Walmart/Target (current data).

> **Remediation direction (approved):** *Strip to right-now facts.* Remove the hash-fabricated freshness and reframe `live-shelf-pulse` as a "What we see right now" panel built only on the defensible signals above. Details in `IMPLEMENTATION_ROADMAP.md` §1.
