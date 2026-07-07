# Implementation Roadmap

**App:** Nimble Retail Intelligence Experience
**Optimizing for:** (1) Credibility · (2) Executive value · (3) Wow moments · (4) Lead generation · (5) Nimble differentiation
**Date:** 2026-06-01

Two directional decisions are baked in:
- **Credibility remediation = "Strip to right-now facts"** — remove fabricated movement/trend language; lead with defensible point-in-time data.
- This roadmap is the plan; **implementation is separately approved** after review of the audit docs.

Effort key: **S** ≈ <½ day · **M** ≈ 1–2 days · **L** ≈ 3+ days.

---

## High Impact / Low Effort

### 1. Credibility remediation — "strip to right-now facts" 🔴 TOP PRIORITY
Remove the only thing that can break trust with an executive/analyst.
- Gut the hash-fabricated parts of `buildFreshness()` (`insight-engine.ts:367–445`): the "climbed to #1 since this morning" rank move, "climbed N spots", "N new sponsored placements", `changesToday` (18–33), `lastRefreshHours` (~Hh ago).
- Replace `live-shelf-pulse.tsx` with a **"What we see right now"** panel built only on real point-in-time facts: live stockouts, deepest current discount, sponsored count on page one, #1-vs-#2 gap, 1P/3P split. Remove the 9am→now timeline and make **Re-scan** either truly re-pull (`refresh:true`, already supported server-side) or be relabeled/removed.
- Reframe `cached-vs-live.tsx` as **"indexed preview → live"** (never call the mock "yesterday").
- Fix `find-your-brand.tsx` copy: drop "yesterday's report can't show you" / "the moment it changes."
- **Impact:** Business — removes the deal-killer in due diligence. User — trust. Complexity — Low (copy + delete + recompose one component). **Effort: M.**

### 2. "Powered by live search" labeling
Make the differentiator explicit.
- Add to the results header: *"Results generated from live Amazon, Walmart & Target search results powered by Nimble."*
- Visibly distinguish **demo vs live** (badge/state) so first-time users know what they're seeing.
- **Impact:** Business — reinforces the core value prop everywhere. User — clarity. Complexity — Low. **Effort: S.**

### 3. Reframe insight cards into executive verdicts
Executives want actions, not charts. All derivable from current data (deterministic):
- **Biggest Winner** (share leader) · **Biggest Threat** (#1–#2 gap) · **Biggest Opportunity** (over-indexed/under-defended) · **Pricing Watchout** (deepest discount / widest cross-retailer spread) · **Availability Watchout** (stockouts) · **Most Competitive Retailer** (highest concentration/sponsored).
- Keep the existing rule engine; relabel/regroup `cards` + KPIs into these six verdicts.
- **Impact:** Business — exec resonance, memorable. User — instant "so what." Complexity — Low–Med. **Effort: M.**

### 4. CTA upgrades
- Earlier curiosity hook: *"Curious how your brand compares? Run your category live."*
- Add booth-number variant (`NEXT_PUBLIC_BOOTH_NUMBER`): *"Visit Booth #{{BOOTH}}"*; keep "Book a Custom Retail Audit" as a soft option.
- **Impact:** Business — more booth conversations (lead gen). User — clear next step. Complexity — Low. **Effort: S.**

---

## High Impact / Medium Effort

### 5. Structured Claude outputs (cards, not paragraphs)
- Add `ExecutiveSummary` + `AskNimbleAnswer` Zod schemas (see `AI_ARCHITECTURE_REVIEW.md` §4); convert `/api/ask`, summary, and `/api/report` to structured output.
- Render Ask answers as cards: **directAnswer · supportingEvidence (chips) · whatItMeans · recommendedNextStep · limitations**.
- The **`limitations` field doubles as a credibility signal** ("single point-in-time snapshot; no historical trend").
- **Impact:** Business — polish + honesty. User — scannable, trustworthy answers. Complexity — Med. **Effort: M.**

### 6. Pricing & availability showcase ("What we see right now")
Surface the live fields already parsed but unused (`DATA_PIPELINE_AUDIT.md` §3):
- **Cross-retailer price spread** for the same/like product (Amazon vs Walmart vs Target) — a classic "I didn't know that."
- **`pricePerUnit`** true-value comparison; **1P/3P `seller`** mix; **`originalPrice`** discount depth; **`badge`**; **stockouts**.
- **Impact:** Business — concrete, defensible wow moments. User — surprising, actionable. Complexity — Med (parsing exists; needs matching + UI). **Effort: M.**

### 7. Discovery engine
- Add **brand** and **keyword** example chips (Quest, Celsius, Monster; "high protein snacks", "sugar free energy drinks", "electrolyte powder") alongside categories, to drive "run your own."
- Bias examples toward surprising results (dominance, high sponsored %, retailer divergence) to maximize "wow, I didn't know that."
- **Impact:** Business — more hands-on test drives → conversations. User — curiosity. Complexity — Low–Med. **Effort: S–M.**

---

## Future Roadmap

### 8. Localized intelligence ("Retail Intelligence Is Local")
Nimble's biggest differentiator, currently absent.
- **First verify** whether the Nimble SERP agents accept geo params (country/state/city). If yes → **real** National vs NYC vs LA vs Chicago visibility comparison. If not → a **clearly-labeled capability teaser** (no fabricated local numbers), per direction.
- **Impact:** Business — unique to Nimble, high differentiation. Complexity — Med–High (depends on agent geo support). **Effort: M–L.**

### 9. Real freshness via stored snapshots
Re-earn the "the shelf is moving" story honestly: persist pulls (per keyword) so a later visit shows **true** change-over-time deltas. Turns the removed theater into a genuine, defensible capability.
- **Impact:** Business — restores the strongest narrative, legitimately. Complexity — High (storage + scheduling). **Effort: L.**

### 10. Breadth
More retailers (the agent gallery already lists ~20), assortment-gap analysis, and multi-keyword/multi-market batch runs.
- **Impact:** Business — scales the "any retailer, any category, on demand" story. Complexity — Med–High. **Effort: L.**

---

## Suggested sequence

1. **§1 Credibility** (do first — protects everything else)
2. **§2 Live labeling** + **§4 CTAs** (cheap, high-leverage)
3. **§3 Exec verdicts**
4. **§6 Pricing/availability showcase** + **§5 Structured Claude**
5. **§7 Discovery**, then **§8 Localization**, **§9 Snapshots**, **§10 Breadth**
