# DYNAMIC HERO RECOMMENDATIONS

**The final hero system to implement.** Intent-aware, dynamic, grounded in real engine data (every `{token}` maps to a field we already compute — nothing fabricated; tokens that have no data fall back, never invent). **Design only — not implemented.**
**Date:** 2026-06-02

---

## Intent detection (deterministic, no AI)

On submit, classify the query:
- **Category** — matches `CATEGORIES`/aliases in `mock-data` (e.g. "energy drinks", "pet food").
- **Brand** — `canonicalizeBrand()` returns high confidence, or it's in `CANONICAL_BRANDS` (e.g. "Quest", "Celsius").
- **Keyword** — everything else (a shopper phrase, e.g. "best protein bar").
- **Default** — no search yet (landing).

Brand intent resolves to the brand's **category** shelf so there's a competitive field to place the brand in (see Strategy Review §5).

Each `{token}` below is suppressed (line falls back) if its data is missing — so a thin pull never produces a broken or fabricated headline.

---

## ① DEFAULT / DEMO HERO  (pre-search landing)
**Mindset:** "What is this, and why is it different?" → make them feel *retailers don't tell the same story.*

- **Headline:** **A different brand wins on every retailer.**
- **Subheadline:** Amazon, Walmart & Target rarely agree on who's leading, what it costs, or who's paying for placement — and your reports usually watch one. Nimble reads all three, live.
- **Supporting copy:** a **rotating live proof** (cycles every ~3.5s — reuse the existing `HeroPreview` cycle, but make each a cross-retailer *contrast*, not a single share stat):
  - "Folgers owns Walmart coffee. Starbucks owns Amazon."
  - "Celsius leads Target energy drinks. Monster leads Amazon."
  - "Spindrift wins Target sparkling water. LaCroix wins Amazon."
  - "Same can, 30% different per-unit price across shelves."  ← price kept as ONE proof, not the headline
- **CTA:** primary search ("Try your category, brand, or keyword") + category/brand/keyword chips. Secondary: "Reading live · Amazon · Walmart · Target" (the favicon cluster) as the credibility line.

*Tokens:* the rotating proofs come from `HeroPreview.PREVIEWS` (already real sample contrasts). Freshness ("live") = the `liveAvailable` state. No per-pull data needed (pre-search).

---

## ② CATEGORY HERO  (search = a category)
**Mindset:** "Who owns my shelf, and how do retailers differ?" → "I didn't know Amazon and Walmart looked this different."

- **Headline (dynamic):** **{leader} leads {category} on {topRetailer} — but not on {divergentRetailer}.**
  - *Fallback* (one brand leads everywhere): **Who owns {category}? It's closer than the national number says.**
- **Subheadline (composite divergence — the breadth, not one axis):** Across all three shelves: **{uniqueLeaders} different leaders**, a **{priceSpread}% per-unit price spread**, and **{sponsoredGap}-pt gap in sponsored pressure** — right now.
  - Each clause drops if its divergence isn't present (so it reads honestly for tame categories).
- **Supporting copy:** "Your single-retailer report sees one of these. The matrix below shows all three."
- **CTA:** "See the full {category} breakdown ↓" (scrolls to the cross-retailer matrix) + "Run your brand against it."

*Tokens → data:* `leader` = `brandShare[0].brand`; `topRetailer` = `heroInsight.retailerLabel` (peak); `divergentRetailer` = a `perRetailer` shelf whose `brands[0]` ≠ leader; `uniqueLeaders` = distinct `perRetailer[].topBrand`; `priceSpread` = matrix `avgPrice` row spread; `sponsoredGap` = matrix `sponsored` row gap. All already computed.

---

## ③ BRAND HERO  (search = a brand → resolved to its category)
**Mindset:** "How does *my* brand compare?" → state-aware (absent is the strongest moment).

**If the brand is ABSENT from page one** (highest-conversion case):
- **Headline:** **{brand} isn't on page one for {category}. Here's who's taking the space.**
- **Subheadline:** {leader} ({leaderPct}%) and {second} own the shelf {brand} needs — and {winnableRetailer} is the cheapest door in.
- **Supporting:** "Live across Amazon, Walmart & Target. The scorecard below shows the gap and where to win first."
- **CTA:** "See {brand}'s opening ↓" + the booth/Book-a-demo CTA (this is where intent peaks).

**If the brand is PRESENT:**
- **Headline:** **{brand} is #{rank} of {total} on the {category} shelf — strong on {bestRetailer}, exposed on {weakRetailer}.**
  - *Fallback* (leads everywhere): **{brand} owns the {category} shelf — here's what's coming for it.**
- **Subheadline:** {visibilityScore}/100 visibility · {gap}-pt {behind/ahead of} {leader} · the one move that matters next.
- **Supporting:** "Where {brand} shows up, where it doesn't, and the fastest shelf to win."
- **CTA:** "See {brand}'s full position ↓" + "Compare another brand."

*Tokens → data:* all from `analyzeBrand()` — `rank/total/score/gap/leader/leaderPct/second/winnableRetailer`, plus per-retailer presence for best/weak shelf. (`bestRetailer`/`weakRetailer` = retailers where the brand's share is highest/lowest.)

---

## ④ KEYWORD HERO  (search = a shopper phrase)
**Mindset:** "What do customers actually see?" → "This is how shoppers really experience search."

- **Headline (dynamic):** **For "{keyword}," {retailerA} shows {brandA}. {retailerB} shows {brandB}.**
  - *Fallback* (same top brand everywhere): **For "{keyword}," here's the shopper's first screen — and what's paid vs earned.**
- **Subheadline:** This is the shopper's first screen across Amazon, Walmart & Target — {sponsoredPct}% of it is sponsored. The brands that win attention aren't always the ones that win the cart.
- **Supporting:** "Search visibility, paid vs organic, and shelf placement — exactly as a shopper sees it, live."
- **CTA:** "See who wins '{keyword}' ↓" + "Run a brand against it."

*Tokens → data:* `retailerA/brandA`, `retailerB/brandB` = top organic brand per retailer (where they differ) from `perRetailer`; `sponsoredPct` = overall paid penetration. All computed.

---

## Shared rules (so it never breaks or fabricates)
- **Token-missing → fallback line.** Every dynamic headline has a static fallback; if `{divergentRetailer}` etc. is absent, use it. Never render a half-empty template.
- **Freshness stays loud** in every state (the green "LIVE · pulled HH:MM" badge already does this).
- **The kicker (`heroKicker`) is replaced by this system.** Leadership/visibility divergence becomes the umbrella; price/sponsored/availability become *supporting* proofs (the composite subheadline), per the Strategy Review critique.
- **Intent is deterministic** — no extra AI call, no latency added to first paint.

---

## Build shape (when approved)
- `src/lib/intent.ts` (new, small): `classifyIntent(query) → "category" | "brand" | "keyword"` using existing `CATEGORIES` + `canonicalizeBrand`.
- `src/lib/hero-copy.ts` (new): pure function `heroCopy(intent, insights, query) → { headline, subheadline, support, cta }` with the templates + fallbacks above. Deterministic, unit-testable.
- `hero-insight.tsx`: render `heroCopy(...)` instead of the fixed question + `heroKicker`.
- `hero-search.tsx`: the default-state headline + rotating cross-retailer proofs.
- Brand→category resolution: a `brandCategory(brand)` lookup (from the `CATEGORIES` rosters for demo; a light inference/chip for live).

Net: ~2 new pure-logic files + copy swaps in 2 components. No new data, no new AI, no new dashboards.

---

## The one decision to make before building
**Brand→category resolution** (Strategy Review §5): a brand search must run the brand's *category* shelf to have competitors to compare against. Confirm the approach — (a) lookup table from the category rosters (clean for the known set), or (b) a "did you mean {category}?" chip for unknown live brands. Recommend **(a) with (b) as the fallback** for brands not in the roster.
