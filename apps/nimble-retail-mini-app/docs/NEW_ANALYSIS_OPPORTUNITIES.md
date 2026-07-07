# New Analysis Opportunities — Review & Recommendation

**Mode:** final launch-polish. No new generic dashboards, no new KPI cards, no new AI summaries, no fabricated history.
**Goal:** more "I didn't know that" moments that showcase Nimble's *unique* value and start conversations — not more analytics.

This doc is the master decision. The three companion plans go deeper:
- [PAID_ORGANIC_INTELLIGENCE_PLAN.md](PAID_ORGANIC_INTELLIGENCE_PLAN.md)
- [RATINGS_REVIEWS_EVALUATION.md](RATINGS_REVIEWS_EVALUATION.md)
- [HISTORICAL_MONITORING_TEASER_PLAN.md](HISTORICAL_MONITORING_TEASER_PLAN.md)

---

## 0 · Ground truth: what data we actually have

Everything below is anchored to an **empirical field-coverage probe** — 3 live categories (energy drinks, protein bars, cold brew coffee), cache bypassed, counting how many of the ~24 page-one rows per retailer actually carry each field.

| Signal | Amazon | Walmart | Target | Reliability verdict |
|---|---|---|---|---|
| `sponsored` (paid flag) | ~50% of rows | ~30% | ~25% | ✅ **Present & consistent on all three** |
| `price` | 100% | 100% | 100% | ✅ Universal |
| `rating` | 100% | ~95% | **0%** | ⚠️ Strong on Amazon/Walmart, **none on Target** |
| `reviewCount` | ~65% | ~95% | **0%** | ⚠️ Partial Amazon, none Target |
| `recentSales` ("5K bought…") | ~100% | 0 | 0 | 🟡 **Amazon-only**, but rock-solid there |
| `inStock` | 0 | 100% | 0 | 🟡 **Walmart-only** |
| `originalPrice` (promo depth) | 0 | sparse (0–4 rows) | 0 | 🔴 Rare — weak signal |
| `badge` (Amazon's Choice) | 0 | 0 | 0 | 🔴 **Never populated — dead code** |

**The single most important takeaway:** `sponsored` is the richest, most reliable signal we have that *isn't already surfaced as a headline*. It's present on **all three retailers**, in **every category**, and it answers a question every brand executive cares about — **are we winning because we earned it or because we bought it?** That makes Paid vs Organic the strongest remaining opportunity, and it's ~80% already computed in the engine.

> ⚠️ **One validation flag, not a blocker:** Amazon returns *exactly* 12/24 sponsored and Target *exactly* 6/24 in every category sampled. The presence is reliable; the suspiciously round constants mean we should sanity-check whether the agent is detecting true ad slots vs. a positional heuristic before we quote *exact* percentages on stage. The **relative** story (Amazon is far more pay-to-play than Walmart/Target) is defensible regardless. See the Paid/Organic plan for how we frame this safely.

---

## 1 · Scoring the three opportunities

Scale 1–5 (5 = best). "Effort" is inverted for readability: **Low/Med/High** = build cost.

| Opportunity | Exec Value | Nimble Differentiation | Conference Appeal | Ease of Understanding | Effort | Data ready? |
|---|---|---|---|---|---|---|
| **1. Paid vs Organic** | 5 | 5 | 5 | 5 | **Low** | ✅ Yes — already computed |
| **2. Ratings & Reviews** | 4 | 3 | 4 | 5 | **Med** | ⚠️ Partial — Target = 0 ratings |
| **3. Historical Monitoring Teaser** | 4 | 5 | 5 | 5 | **Low–Med** | ✅ N/A (capability teaser, no data) |

### Why these scores

**Opp 1 — Paid vs Organic (the standout).** "Earned vs bought visibility" is a board-level question, the data is reliable across all three retailers, and the aha lands in one sentence: *"Monster owns the shelf — but 50% of that is paid. Quest earned its spot."* Highest differentiation (cross-retailer **live** paid intelligence is genuinely hard to get elsewhere) and lowest effort (the engine already has `organicLeader`, `paidLeader`, per-brand `sponsoredCount`/`organicCount`, per-retailer `sponsoredPct`). It is currently computed and **thrown away** — there's a "Sponsored vs Organic" card built in the engine that the UI no longer renders.

**Opp 2 — Ratings & Reviews (compelling but data-gated).** The insight *"the most visible product is not the highest rated"* is a great surprise — **but Target returns zero ratings**, so any cross-retailer rating claim is broken, and any matrix row would show Target blank (reads as "broken" at a booth). The one place it's bulletproof is **Amazon**, which carries rating + reviewCount + recentSales + rank on the *same* rows — enabling a "loved/best-selling but buried" finding. Note: this is close to the trust-vs-visibility insight previously declined. Recommend **defer**, or ship only as a single Amazon-scoped finding with honest framing.

**Opp 3 — Historical Monitoring Teaser (the conversion close).** We have no history and must not fake it. But continuous monitoring over time *is* Nimble's core product, and it's the literal payoff of the homepage thesis ("your reports can't keep up with the shelf"). A **visibly-locked** "track this over time" panel communicates the capability honestly and is a natural bridge into "book 15 minutes." Low data risk (it shows no numbers), high conference appeal.

---

## 2 · Audit of existing analyses (be ruthless)

| Section | Verdict | Notes |
|---|---|---|
| Hero / Search | **Keep** | Entry point; FOMO thesis is working. |
| Results hero ("Who owns the shelf right now?") | **Keep** | The answer-first moment. |
| **Cross-Retailer Intelligence** (matrix + divergence) | **Keep — centerpiece** | Strongest differentiator. **But fix the "Out of stock" matrix row** (below). |
| Top Takeaways ("3 things we found") | **Keep** | Strong, plain-voice surprises. Paid/Organic should become eligible to appear here. |
| Run My Brand | **Keep** | Personalization hook. |
| Localization Teaser | **Keep** | Capability teaser; just moved up under Run My Brand. |
| Ask Nimble | **Keep** | Follow-up layer. |
| Supporting Evidence drawer (Share of Shelf · What we see now · Selling now · raw shelf) | **Keep, collapsed** | Right altitude — buried by design. |
| Report Capture | **Keep** | Conversion. Email-only now (PDF removed). |

### Problems to fix / remove (make room without adding clutter)

1. 🔴 **"Out of stock" cross-retailer matrix row is a credibility bug.** `inStock` is **Walmart-only**, so the row shows Walmart's real count next to **"0" for Amazon and Target** — which reads as "Amazon & Target never go out of stock." They do; they just don't report it. **Fix:** render OOS only for retailers that report availability (show "—"/"not reported" for the others), or drop the row from the cross-retailer matrix and keep stockouts as a Walmart-scoped finding only. This is exactly the kind of thing that erodes trust at a booth.
2. 🔴 **Dead "Amazon's Choice" badge card** — `badge` is never populated (0/0/0). The "Who Owns the Default Buy" card can never fire. Remove from the engine (cleanup, not user-facing).
3. 🟡 **Retired-but-present dead code:** the 5-card `verdicts` builder and `kpis`/`InsightCards`/`KpiRow` are computed/shipped but not rendered. Harmless, but they bloat the payload and confuse future edits. Optional cleanup; safe to defer.
4. 🟡 **"What we see right now" facts are uneven:** the availability fact is Walmart-only and the promo fact rarely fires (sparse `originalPrice`). The sponsored-penetration and leader-gap facts are solid. Consider trimming to the two reliable facts, *or* let the new Paid/Organic module absorb the sponsored fact.

---

## 3 · Recommendation

### ✅ Implement before launch
1. **Paid vs Organic Intelligence** — a dedicated, executive-legible module ("earned vs bought"). Highest value, lowest effort, reliable data. Full spec: [PAID_ORGANIC_INTELLIGENCE_PLAN.md](PAID_ORGANIC_INTELLIGENCE_PLAN.md).
2. **Historical Monitoring Teaser** — a tasteful, visibly-locked "track this over time" panel as the conversion bridge. No fabricated data. Full spec: [HISTORICAL_MONITORING_TEASER_PLAN.md](HISTORICAL_MONITORING_TEASER_PLAN.md).
3. **Fix the OOS matrix row** (credibility) and **remove the dead badge card** (hygiene).

### ⏸ Defer
- **Ratings & Reviews** — until Target ratings are available, or unless we accept an **Amazon-only** "loved but buried" finding with explicit framing. Rationale + the narrow option: [RATINGS_REVIEWS_EVALUATION.md](RATINGS_REVIEWS_EVALUATION.md).

### ✂️ Remove / fix to make room
- The misleading **OOS matrix row** (fix to "reported retailers only" or drop).
- The **dead badge card** in the engine.
- Optionally trim the two weakest "What we see right now" facts.

### Utilizing Claude (cross-cutting principle)
Both new modules use **Claude as the interpreter, deterministic math as the foundation**:
- **Deterministic** owns every number (leaders, %, paid-dependence, today's snapshot) → reliable, instant, demo-safe, never fabricated.
- **Claude** owns the *verdict and the framing* — "earned vs bought," who's vulnerable, and "what we'd watch for you" — fed only the deterministic summary so it interprets rather than invents.
- Every Claude layer has a **deterministic fallback string**, so the booth demo works even if the model call is unavailable. Reuse the existing structured `/api/ask` approach; no new pattern, ideally folded into the existing amplifier to avoid extra round-trips.

This is the right place to lean on Claude harder than we do today (currently only Ask + email use it): the paid/organic verdict and the monitoring "what we'd watch" line are exactly the analyst-quality touches that make it feel like intelligence, not a dashboard.

### Net effect on the story
Two new differentiated moments, both on-thesis:
- **"Earned vs bought"** — a surprise about *how* brands win the shelf (Paid/Organic).
- **"This is just today — Nimble watches it change"** — the monitoring close (teaser).

Both push toward the one goal: *make them say "I didn't know that," then talk to us.*

---

## 4 · Suggested final section order (if both new modules ship)

```
Hero answer
→ Cross-Retailer Intelligence (centerpiece)        [fix OOS row]
→ Paid vs Organic ("earned vs bought")             [NEW — pairs with cross-retailer]
→ Top Takeaways (3 things; paid/organic eligible)
→ Run My Brand
→ Localization
→ Ask Nimble
→ Monitoring Teaser ("track this over time")       [NEW — bridge to capture]
→ Report Capture
→ Supporting Evidence (collapsed)
```

Rationale: the two strongest, hardest-to-replicate differentiators (cross-retailer divergence + earned-vs-bought) sit back-to-back at the top; the monitoring teaser sits right before the capture CTA so the "we watch this over time → book time" hand-off is seamless.

> **Ask Nimble placement note (answering the open question):** with a Paid/Organic module added up top, Ask is best left as the *follow-up* layer after the core story — a top-of-page Ask entry would compete with the new differentiated moments for the first 60 seconds. If we still want an early Ask affordance, use a single suggested-question chip near the hero that scrolls to the Ask section, rather than a second full Ask block.
