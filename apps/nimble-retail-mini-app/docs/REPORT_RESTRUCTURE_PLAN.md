# Report & Page Restructure Plan

**Goal:** the experience and the email both read **Verdict → Why it matters → Retailer differences → How your brand compares → Evidence → CTA** — a strategic briefing, not a dashboard. Analytics support the story; they don't lead it.
**Date:** 2026-06-01 · *Plan only — waiting for approval.*

---

## Part A — Brand normalization (P0, lands first)

Per `BRAND_NORMALIZATION_AUDIT.md`: add `src/lib/brand-normalize.ts` (`canonicalizeBrand`), apply it once at the top of `buildInsights` so every row's `brand` is canonical (preserve `brandRaw`/`productTitle`). No other logic changes — all brand-keyed insights inherit the fix. **This ships before the restructure**, since verdicts/share/Run-My-Brand depend on correct brands.

---

## Part B — Page restructure (`results-experience.tsx`)

### Current order
Hero → Verdict → **Run My Brand** → Retailer Tabs → KPIs → Share-of-Shelf + What-We-See-Now → **Email capture** → Cross-Retailer → Selling Now → +signals → Localization → Ask → Raw Shelf

### New order
Hero → **Verdict** → **What Changes Across Retailers** → **Run My Brand** → **Email/Report capture** → **Supporting Evidence** (Tabs, KPIs, Share-of-Shelf, What-We-See-Now, Selling Now, +signals) → Localization → Ask Nimble → Raw Shelf

Net moves: Cross-Retailer **up** (to #2 after the verdict); Run My Brand **down** (below differences); Email capture **down** (after brand); all analytics **down** into a "Supporting Evidence" block; Ask + Raw Shelf stay last.

### Updated page wireframe
```
┌─ HERO ───────────────────────────────────────────────┐
│ "your reports show last week — see your shelf now"    │  keep
└───────────────────────────────────────────────────────┘
  Category: {keyword} · live from Amazon · Walmart · Target

▌ 1. EXECUTIVE VERDICT                         (the answer)
   Winner · Opportunity · Threat · Pricing · Availability
   each: what → why it matters → action

▌ 2. WHAT CHANGES ACROSS RETAILERS?            (the wow — moved UP)
   ▸ lead: "A different brand leads each shelf"
     Amazon → … · Walmart → … · Target → …
   ▸ price / sponsored / availability / promo divergences
   "your single-retailer report would never show this"

▌ 3. RUN MY BRAND                              (now show ME)
   [ type your brand ]  → Visibility Score · Category Leader
   · Gap to Leader · Biggest Opportunity · Recommended Action

▌ 4. TAKE THIS REPORT WITH YOU                 (capture, after value)
   Email it · Download PDF

──────────────  supporting evidence (analytics live below)  ──
▌ 5. SUPPORTING EVIDENCE
   Retailer toggle · KPI strip · Share of Shelf ·
   What We See Right Now · Selling Right Now · + more signals

▌ 6. RETAIL INTELLIGENCE IS LOCAL              (capability teaser)
▌ 7. ASK NIMBLE AI                             (exploration)
▌ 8. EXPLORE THE RAW SHELF                     (last)
```

**Notes**
- Retailer **toggle tabs** move down with the evidence block; the verdict/differences/brand sections render the all-retailers view (the tabs still recompute everything when used, as today).
- "Supporting Evidence" gets a clear divider/label so it reads as *support*, not the main event.
- The keyed-by-retailer remount currently wraps KPIs + Share + What-We-See; it stays around the evidence block.

---

## Part C — Email report restructure (`report-html.ts`)

### Current email order
Verdict → Brand → Cross-Retailer → What-We-See-Now → Analyst summary → Evidence (tables) → Localization → CTA

### New email order (mirror the app)
1. **Executive Verdict**
2. **What Changes Across Retailers**
3. **How Your Brand Compares** (only if a brand was run; else FOMO)
4. **Key Evidence** (What We See Right Now + Share-of-Shelf + By-Retailer tables, condensed)
5. **Localization Capability** (teaser, no fabricated data)
6. **CTA** (Curious how your brand compares? · Booth # / Custom Audit)

The optional Nimble-AI analyst summary moves to a small line **under the verdict** (not a lead block). No KPI grid up top — evidence/tables sit in §4.

### Updated email wireframe
```
┌ NIMBLE RETAIL INTELLIGENCE REPORT ───────────────────┐
│ {Category} · Generated {ts} · Query · Amazon•Walmart•Target │
└───────────────────────────────────────────────────────┘
EXECUTIVE VERDICT
  ▸ Winner / Opportunity / Threat / Pricing / Availability
    (what · why it matters · → action)
  [small] Analyst summary · Nimble AI (1–2 lines)

WHAT CHANGES ACROSS RETAILERS
  ▸ lead divergence (dark callout) + supporting differences

HOW {BRAND} COMPARES            (if brand provided)
  Visibility Score · Leader · Gap · Opportunity · Action
  (or FOMO block if absent)

KEY EVIDENCE
  What we see right now (facts)
  Share of shelf (table) · By retailer (table)

RETAIL INTELLIGENCE IS LOCAL    (capability teaser)

CTA  — Curious how your brand compares? · Visit Booth #{{N}}
        (Download PDF bar stays on the in-app report view)
```

Both the page and the email then tell the identical story, verdict-first.

---

## Files touched (when approved)
- **New:** `src/lib/brand-normalize.ts` (+ apply in `insight-engine.ts` `buildInsights`; add `brandRaw` to `RetailerSerpResult` in `types.ts`).
- **Reorder:** `src/components/results-experience.tsx` (section order + a "Supporting Evidence" divider).
- **Reorder:** `src/lib/report-html.ts` (section order; analyst summary demoted; "Key Evidence" grouping).
- No new dependencies. Brand normalization is deterministic and current-pull only.

## Verification (when built)
1. **Normalization:** Energy Drinks live → Monster appears once; share = sum of sub-lines; Winner/Threat/Run-My-Brand consolidated. Protein Bars → Premier Protein consolidated.
2. **Page order:** verdict → differences → brand → capture → evidence → local → ask → raw; build + lint clean; desktop + 390px mobile, no overflow.
3. **Email order:** regenerate `docs/sample-report.html` → verdict-first, differences second, brand third, evidence in §4; Download PDF bar still present in-app.
