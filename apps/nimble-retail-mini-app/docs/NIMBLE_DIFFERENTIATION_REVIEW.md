# Final Nimble Differentiation Review (pre–Sprint 3)

**Premise:** the app is feature-complete. Which insights — from the **live data already parsed** (`nimble-serp.ts`) — does Nimble uniquely provide that executives care about, competitors can't easily show, and that create the strongest aha?
**Date:** 2026-06-01 · *Strategy only.*

Constraint honored: no new dashboards, no more AI, no more charts. These are *insights*, not visualizations.

---

## The 3 highest-value uniquely-Nimble insights

### 1. Seller Intelligence — 1P vs 3P (who's *really* selling your shelf)
- **Field:** `seller` / `sold_by` — **parsed today, surfaced nowhere.**
- **Insight:** "38% of your page-one shelf on Walmart is third-party resellers" / "3 unknown sellers are listing *your* brand."
- **Why it's unique:** seller-of-record at the **search-shelf level, live, across retailers** is something single-retailer tools and daily DSAs structurally don't show. Almost no competitor surfaces this.

### 2. Cross-Retailer Price Intelligence (same product, three prices, right now)
- **Fields:** `price` (+ `originalPrice`, `pricePerUnit`) compared across retailers.
- **Insight:** "The same SKU is 17% cheaper on Walmart than Target right now."
- **Why it's unique:** requires a **simultaneous, live, multi-retailer pull + product matching** — exactly what Nimble does and a single-retailer report can't. *(Partially shipped — `priceGap` in the verdict + divergence engine.)*

### 3. Demand ≠ Visibility (what sells vs what ranks)
- **Field:** `recentSales` vs `rank`.
- **Insight:** "The #6-ranked product is the #1 seller — you're outranked by what shoppers ignore."
- **Why it's unique:** the live synthesis of demand against paid/organic visibility. *(Already shipped — Selling Now.)*

---

## Ranking

Scores 1–10.

| Insight | Exec Value | Conference Appeal | Ease of Understanding | Nimble Differentiation | Status |
|---|---|---|---|---|---|
| **Seller (1P/3P)** | 10 | 8 | 7 | 9 | **Not surfaced** |
| **Cross-Retailer Price** | 9 | 9 | 10 | 8 | Partially shipped |
| **Demand ≠ Visibility** | 8 | 9 | 8 | 7 | Shipped |

- **Executive value:** Seller wins — 3P penetration, unauthorized resellers, MAP erosion, and lost buy-box are top-of-list CPG eCommerce fears tied directly to revenue and brand control.
- **Conference appeal:** Price edges it on instant legibility; Seller is a close second once framed ("third parties are selling *you*").
- **Ease of understanding:** Price is universal; Seller needs one sentence for non-eComm execs (but eComm VPs get it instantly).
- **Nimble differentiation:** Seller is the most defensible — the hardest thing for anyone else to show.

---

## Recommendation: **B — Implement Seller Intelligence (1P vs 3P)** — then stop and polish

**One focused module, then polish.** Not an open-ended Sprint 3.

**Rationale**
- **It's the only top-3 differentiator not already on screen.** Cross-retailer price (C) is already live in the verdict + "What changes across retailers"; deepening it is diminishing returns. Demand≠visibility is shipped. Seller is the highest-value insight we are **completely failing to surface**.
- **Highest executive value + highest Nimble differentiation** of the three — and squarely the CPG eCommerce pain set.
- **Low effort, data already parsed** — `seller`/`sold_by` exists in `RetailerSerpResult`; needs a 1P/3P classifier heuristic (1P = sold by the retailer / Amazon / Walmart; else 3P) and one module ("Who's selling your shelf?" — 1P vs 3P split per retailer, flag brands under unknown 3P sellers). Fits the existing "What we see right now" / verdict patterns.
- **Reinforces the wedge** — it's another **cross-retailer, granular, live** fact a DSA can't produce, deepening the "only Nimble can show you this" story.

**One gate before building:** verify `seller` **fill-rate** on a few live pulls. If the agents populate it reliably → ship it as a core module. If it's sparse on some retailers → present it as a clearly-labeled **capability teaser** (like Localization), never fabricated. Honesty over coverage.

**Why not A (stop now):** we'd leave the single most exec-resonant, most-unique, cheapest insight on the table.
**Why not C:** already represented; marginal lift is low.
**Why not D:** localization needs geo-param verification (not "already available"); structured Ask / scorecard are polish, not differentiation.

**Sequence:** B (Seller Intelligence, gated on fill-rate) → then **A (stop and polish)**: tighten copy, ensure every verdict/difference reads cleanly with partial data, final mobile + live-pull pass. Resist adding more.
