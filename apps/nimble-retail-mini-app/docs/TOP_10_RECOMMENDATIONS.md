# Top 10 Recommendations + Sprint 1 Plan

**App:** Nimble Retail Intelligence Experience
**Synthesizes:** `DATA_PIPELINE_AUDIT.md`, `UX_AUDIT.md`, `AI_ARCHITECTURE_REVIEW.md`, `IMPLEMENTATION_ROADMAP.md`, `UNUSED_DATA_OPPORTUNITIES.md`
**Optimizing for:** ① Executive engagement ② Prospect curiosity ③ Nimble differentiation ④ Lead conversion ⑤ Data credibility
**Date:** 2026-06-01 · *Analysis only — no code yet.*

Scores are 1–10. **Priority = (Impact × Confidence) ÷ Effort** (higher = do sooner). Effort is reverse-weighted intentionally — the goal is max impact for min engineering.

---

## The Top 10 (ranked by priority)

| # | Recommendation | Goals | Impact | Effort | Conf | Priority |
|---|---|---|---|---|---|---|
| 1 | **Live-search labeling + demo/live badge** | ②③⑤ | 8 | 2 | 9 | **36.0** |
| 2 | **`productUrl` click-through (live proof)** | ⑤②① | 8 | 2 | 9 | **36.0** |
| 3 | **Sharper, earlier CTAs + Booth #** | ④ | 8 | 2 | 8 | **32.0** |
| 4 | **Discovery chips (brand + keyword)** | ②④ | 7 | 2 | 8 | **28.0** |
| 5 | **Strip fabricated freshness → "What we see right now"** | ⑤①③ | 10 | 4 | 10 | **25.0** |
| 6 | **Promo density + per-retailer availability map** | ②③① | 7 | 3 | 8 | **18.7** |
| 7 | **Exec-verdict cards (Winner/Threat/Opportunity/Watchouts/Most Competitive Retailer)** | ①⑤ | 9 | 4 | 8 | **18.0** |
| 8 | **Seller 1P vs 3P module** | ③① | 9 | 4 | 7 | **15.8** |
| 9 | **Cross-retailer price spread (same product)** | ②③ | 10 | 5 | 7 | **14.0** |
| 10 | **Structured "Ask Nimble" answer cards (w/ `limitations`)** | ①⑤ | 7 | 5 | 7 | **9.8** |

> ⚠️ **Credibility is the gate.** #5 scores mid on the raw formula only because it costs more effort — but it is **non-negotiable and must ship first**. Every other claim in the app rides on the data being trustworthy; leaving fabricated "shelf is moving" content in place caps the ceiling on all four other goals. Treat #5 as the spine of Sprint 1.

---

## Detail

**1. Live-search labeling + demo/live badge** — Add to results: *"Results generated from live Amazon, Walmart & Target search results — powered by Nimble."* Make demo vs live visually obvious. *Cheapest reinforcement of the entire value prop; removes first-load confusion (`UX_AUDIT` §1).*

**2. `productUrl` click-through** — Link product tiles/rows to the live PDP (new tab). Turns every claim into *click-to-verify* proof in front of a skeptic. *(`UNUSED_DATA_OPPORTUNITIES` #4 — already parsed, trivial.)*

**3. Sharper, earlier CTAs + Booth #** — Add a curiosity hook before results ("Curious how your brand compares? Run your category live.") and a `NEXT_PUBLIC_BOOTH_NUMBER` variant; keep tone soft. *(`ROADMAP` §4.)*

**4. Discovery chips** — Surface brand (Quest, Celsius, Monster) and keyword ("sugar free energy drinks", "electrolyte powder") examples, biased toward surprising results, to drive "run your own." *(`ROADMAP` §7.)*

**5. Strip fabricated freshness → "What we see right now"** — Remove hash-seeded rank moves / "changed N× today" / "~Hh ago" / 9am→now timeline / animate-only Re-scan (`insight-engine.ts:367–445`, `live-shelf-pulse.tsx`); reframe `cached-vs-live` as "indexed preview → live"; fix `find-your-brand` copy. Rebuild the panel from real point-in-time facts. *(`DATA_PIPELINE_AUDIT` §5, `ROADMAP` §1.)*

**6. Promo density + availability map** — Populate the new "right now" panel: % of shelf on promo + avg depth (from `originalPrice`), and in-stock vs OOS per retailer (from `inStock`). *(`UNUSED_DATA_OPPORTUNITIES` #8, #10 — synergistic with #5; the new panel needs real content.)*

**7. Exec-verdict cards** — Relabel/regroup the existing deterministic insights into **Biggest Winner · Biggest Threat · Biggest Opportunity · Pricing Watchout · Availability Watchout · Most Competitive Retailer.** Actions, not charts. *(`ROADMAP` §3, `UX_AUDIT` §4.)*

**8. Seller 1P vs 3P** — Classify `seller` and show third-party penetration per retailer. Uniquely Nimble, squarely in the CPG pain set. *(`UNUSED_DATA_OPPORTUNITIES` #1 — needs a 1P/3P heuristic.)*

**9. Cross-retailer price spread** — "Same product, 17% cheaper on Walmart than Target right now." Highest wow, but needs fuzzy product matching across retailers. *(`UNUSED_DATA_OPPORTUNITIES` #2.)*

**10. Structured "Ask Nimble" cards** — Convert `/api/ask` (+ summary, report) to schema output rendered as cards: directAnswer · supportingEvidence · whatItMeans · recommendedNextStep · **limitations**. The `limitations` field pre-empts skeptics. *(`AI_ARCHITECTURE_REVIEW` §4.)*

---

## Sprint 1 plan — "Credibility + Live Proof"

**Theme:** Make every claim true and verifiable, make the live-data story explicit, and convert curiosity into booth conversations. Maximum impact, minimum engineering — six items, all Low/Medium effort, hitting all five goals.

| In Sprint 1 | Why it's in | Effort |
|---|---|---|
| **#5 Strip freshness → "What we see right now"** | The spine — protects credibility (must ship before anything else is believable) | M |
| **#6 Promo density + availability map** | Fills the new panel with real, defensible "right now" content | M (low marginal, shares #5's work) |
| **#1 Live-search labeling + demo/live badge** | Makes the differentiator explicit; near-free | S |
| **#2 `productUrl` click-through** | Live proof; converts skeptics on the spot; trivial | S |
| **#3 CTAs + Booth #** | Direct lead-conversion lever; trivial | S |
| **#4 Discovery chips** | Drives "run your own" → more conversations | S |

**Deliberately deferred to Sprint 2** (higher effort or dependencies): **#7 Exec-verdict cards** (stretch into Sprint 1 only if capacity), **#8 Seller 1P/3P** (needs classifier), **#9 Cross-retailer price spread** (needs product matching), **#10 Structured Ask cards** (schema + render rework).

**Sprint 1 covers all five goals:**
- ⑤ Credibility → #5, #2, #1
- ③ Differentiation → #1, #6
- ② Curiosity → #4, #6, #2
- ④ Lead conversion → #3, #4
- ① Exec engagement → #6 (+ #7 if pulled in)

**Suggested order:** #5 → #6 (same component) → #1 → #2 → #3 → #4. Then ship, gather booth reactions, and start Sprint 2 with the differentiators (#8 seller 1P/3P, #9 price spread) and #10 structured Ask.

**Definition of done (Sprint 1):** no fabricated/trend language remains anywhere; the results view states it's live Amazon/Walmart/Target via Nimble; products link to live PDPs; a curiosity CTA + booth # appears; brand/keyword discovery chips are live; build + lint clean; verified desktop + mobile.
