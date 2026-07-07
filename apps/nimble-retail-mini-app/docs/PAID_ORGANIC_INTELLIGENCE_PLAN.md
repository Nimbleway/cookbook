# Paid vs Organic Intelligence — Implementation Plan

**Priority:** #1 (highest-value remaining analysis).
**Core question:** *Are brands winning because they earned visibility — or because they bought it?*
**Status of data:** ✅ Reliable on all three retailers; ~80% already computed in [insight-engine.ts](../src/lib/insight-engine.ts).

---

## 1 · Why this is the strongest opportunity

- The `sponsored` flag is present and consistent across **Amazon (~50%), Walmart (~30%), Target (~25%)** in every category sampled. It is the most reliable signal we have that isn't already a headline.
- "Earned vs bought" is a question every CMO / brand lead instantly understands — no explanation needed.
- It's a **cross-retailer, live** view of paid pressure, which is genuinely hard to assemble elsewhere → high Nimble differentiation.
- The engine already computes the inputs and then **discards** them: `organicLeader`, `paidLeader` ([insight-engine.ts:144-150](../src/lib/insight-engine.ts#L144-L150)), per-brand `sponsoredCount`/`organicCount` on `BrandShare`, and per-retailer `sponsoredPct`. There's even a built "Sponsored vs Organic" card the UI no longer renders.

---

## 2 · Metrics — all computable deterministically (today's data)

| Output | Definition | Source |
|---|---|---|
| **Organic Leader** | Most non-sponsored page-one placements | `organicLeader` (already computed) |
| **Paid Leader / Most Aggressive Advertiser** | Most sponsored placements | `paidLeader` (already computed) |
| **Sponsored Share %** | Sponsored ÷ total page-one, overall + per retailer | `sponsoredPct` (already computed) |
| **Paid Dependence %** (per brand) | `sponsoredCount ÷ count` for a brand | trivial from `BrandShare` |
| **Most Efficient Organic Brand** | High `organicCount`, low/zero `sponsoredCount`, strong `avgRank` | derive from `brandShare` |
| **"Earned vs Bought" gap** | Does the visibility leader lead because of ads or merit? | compare leader's paid dependence vs organic leader |

### The aha, in one line (deterministic templates)
- *"{Leader} owns {share}% of the shelf — but {dep}% of it is paid."*
- *"{OrganicLeader} earned the most slots without paying. {PaidLeader} bought the most."*
- *"On Amazon, half of page one is an ad. On Target, a quarter. Same category, different game."*

---

## 3 · Where Claude adds value (utilize Claude)

Deterministic numbers are the **foundation and the demo-safe fallback**. Claude is the **interpreter** layered on top — never the source of a number.

| Layer | Owner | Why |
|---|---|---|
| The numbers (leaders, %, dependence) | **Deterministic** | Reliable, instant, demo-safe, never fabricated. |
| The **verdict / narrative** ("earned vs bought", who's vulnerable) | **Claude** | Turns 5 numbers into one executive sentence with a point of view. |
| Per-brand **characterization** ("propped up by ads" vs "winning on merit") | **Claude** | Nuance a template can't carry; reads as analyst-quality. |
| The **"so what" / recommended watch** | **Claude** | Strategic framing tailored to the specific split. |

**Implementation of the Claude layer (reuses existing infrastructure — no new pattern):**
- Add a small structured Claude call modeled on the existing structured `/api/ask` route (Sonnet, structured output: `{ verdict: string, leaderCharacter: string, soWhat: string }`), fed *only* the deterministic paid/organic summary object. This keeps Claude interpreting, not inventing.
- **Demo-safe fallback:** if `ANTHROPIC_API_KEY` is absent or the call fails, render the deterministic template sentences (section 2). The module is fully functional without Claude; Claude makes it sing.
- Cost/latency: one short call, only when the section renders (or fold into the existing insights amplifier so it's not a separate round-trip). Cache by keyword like the live pull.

> This directly answers the brief's three sub-questions: *metrics that exist* → all of section 2; *deterministic insights* → section 2 templates; *what Claude interprets* → section 3.

---

## 4 · Best insight format & visualization

A compact, scannable module — **not** another KPI grid. Proposed layout:

```
┌─ EARNED vs BOUGHT ─────────────────────────────────────────────┐
│  Claude verdict (1 sentence, bold):                             │
│  "Monster owns this shelf — but half its visibility is paid.    │
│   Quest earned its spot."                                       │
│                                                                 │
│  ┌── Organic leader ──┐     ┌── Paid leader ──┐                 │
│  │  Quest             │     │  Monster        │                 │
│  │  9 earned slots    │     │  7 ads          │                 │
│  └────────────────────┘     └─────────────────┘                 │
│                                                                 │
│  Paid dependence (top brands) — how much is bought:             │
│  Monster   ███████████░░░░░  58% paid                           │
│  Celsius   ██████░░░░░░░░░░  31% paid                           │
│  Quest     █░░░░░░░░░░░░░░░   8% paid   ← earns it               │
│                                                                 │
│  Sponsored share by retailer:  Amazon 50% · Walmart 30% · Target 25% │
│                                                                 │
│  └ Claude "so what" line + [Ask Nimble about this →]            │
└─────────────────────────────────────────────────────────────────┘
```

- **Two-card contrast** (Organic leader vs Paid leader) is the instant read.
- **Paid-dependence bars** for the top 3–4 brands are the "I didn't know that" — a brand that looks dominant but is mostly ads pops immediately.
- **Sponsored-share-by-retailer** strip reinforces the cross-retailer differentiation.
- Keep it to one screen; no tables of every brand.

---

## 5 · Best placement

Directly **after Cross-Retailer Intelligence**, before Top Takeaways. The two strongest, hardest-to-replicate differentiators sit back-to-back: *"a different brand leads each store"* → *"and the leaders that look strong are often just buying it."* Also make a paid/organic finding **eligible for the "3 things we found"** list so the surprise can lead when it's the most striking signal.

## 6 · Best CTA

Two, both low-friction:
- Inline: **"Ask Nimble about this shelf's paid pressure →"** (pre-fills the Ask box with *"Who's winning organically vs buying visibility?"*).
- The module's "so what" naturally feeds the monitoring teaser ("paid pressure moves weekly — track it") and the report capture.

---

## 7 · Build checklist

1. **Engine:** add a `paidOrganic` object to `InsightPayload` (organic leader, paid leader, overall + per-retailer sponsored %, top-N brands with paid-dependence %, most-efficient-organic brand). Pure derivation from existing `brandShare`/`perRetailer` — no new fetch.
2. **Claude layer:** structured interpreter call (verdict / leaderCharacter / soWhat) with deterministic fallback. Reuse the `/api/ask` structured-output approach.
3. **Component:** `paid-organic.tsx` — two contrast cards + dependence bars + retailer strip + verdict/so-what. Demo-mode-first (works on mock data).
4. **Placement:** after `cross-retailer-diff`; register in `NAV_SECTIONS` (e.g. `{ id: "paid-organic", label: "Paid vs organic" }`) with `scroll-mt-32`.
5. **Findings:** add a paid/organic candidate to `buildFindings` so it can surface in "3 things."
6. **Email/report:** mirror the verdict + two-card contrast in `report-html.ts`.
7. **Validation before stage:** confirm the `sponsored` flag reflects real ad detection (the constant Amazon 12/24, Target 6/24 warrants one sanity check). Until confirmed, **lead with the relative story** ("Amazon is far more pay-to-play than Target") rather than precise single percentages.

**Effort:** Low. Most of the math exists; the work is one derived object, one component, and a thin Claude interpreter with a deterministic fallback.
