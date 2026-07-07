# Product Strategy Review (pre–Sprint 2)

**App:** Nimble Retail Intelligence Experience
**Lens:** Product / UX / positioning / insight / conversion — not technical.
**Date:** 2026-06-01 · *Strategy only — nothing implemented.*

---

## 1. The 5 biggest remaining weaknesses

**1. It answers "who owns the category" — not "where do *I* stand."**
The default experience is category-level ("Premier Protein owns 50% of Walmart"). Interesting, but generic. The thing a VP actually cares about — *their* brand's position, gap, and blind spots — is opt-in (Find Your Brand, mid-page). The experience should be **brand-relationship-first**, not category-first.

**2. The aha is below the fold; the first screen states a fact, not a surprise.**
The hero answer is a *fact*. The genuinely counterintuitive signals (demand ≠ visibility, sponsored intensity, price divergence, 3P) live in Act 2/3. A 30-second visitor leaves with "nice share chart," not "wow." The surprise needs to be in the **first screen**.

**3. Positioning over-indexes on "live" and under-indexes on "what I can't get elsewhere."**
"Right now / your reports show last week" is the whole wedge today. But a VP assumes data can be pulled — *freshness alone isn't a budget line*. What they'll pay for is **completeness + breadth + the cross-retailer/3P/localized insight their DSA can't produce**. We're selling speed when we should be selling **coverage + the unseen**.

**4. Conversion is soft and unearned.**
CTAs are all "come meet us / booth." There's no capture at the **peak of curiosity** ("email me this audit for my brand"), and the follow-up isn't personalized enough to be worth a sales conversation. The email report exists but is buried in Act 3, after attention has peaked.

**5. Insights are descriptive, not prescriptive or competitive.**
Cards explain *what's happening*. Executives want a **verdict**: who's winning, who's the threat, where's the opening, what to do Monday. No competitive tension, no ranked "winner/threat/opportunity." It reads like analytics, not a briefing.

> Credibility (the Sprint 1 fix) is no longer a top-5 weakness — the data is now defensible. The gap now is **relevance, surprise, and positioning**, not trust.

---

## 2. VP of eCommerce, 30 seconds — what's still unclear

- **"Is this my data or a generic demo?"** Demo-vs-live is still subtle; they haven't searched their brand, so it feels like a canned showcase.
- **"What do I *do* with this?"** No verdict, no recommended action, no threat call-out.
- **"What can Nimble do that my DSA / Stackline / 84.51° can't?"** The unique wedge is never stated. They already own dashboards.
- **"What's the scope?"** Only 3 retailers, national, one keyword. A VP covers 15+ retailers and multiple geographies/countries — the **scale story is invisible**.
- **"Is this genuinely real-time?"** Asserted in copy; the proof (click-through to the live PDP, the timestamp) is buried, not front-and-center.

---

## 3. QR scan — what makes them want to talk to Nimble

**What works today**
- Zero-friction, no signup, instant, visually credible and on-brand.
- Interactive — they can run their own category; that beats a static booth banner.
- The **demand ≠ visibility** ("selling now" vs rank) contrast is genuinely intriguing.
- **Find Your Brand** FOMO ("you're not on page one") is a real hook when used.

**What doesn't**
- **No immediate personalization** — they must *think of* a category; the page doesn't pull them to "your brand."
- **Reason-to-talk is "this is cool," not "I'm missing something / I need this."** No tailored gap.
- **Breadth/scale invisible** — 3 retailers, national only. Doesn't signal "any retailer, any market, any cadence, at scale."
- **Localization — Nimble's biggest differentiator — is entirely absent.**
- The CTA asks for a conversation before delivering a *personal* reason to have one.

---

## 4. Top 10 live fields not surfaced prominently enough

(Already parsed in `nimble-serp.ts`; ranked by how much prominence would change the demo. Full detail in `UNUSED_DATA_OPPORTUNITIES.md`.)

| # | Field | Why it matters | Example insight | Wow |
|---|---|---|---|---|
| 1 | **`seller` (1P/3P)** | 3P penetration = price erosion, unauthorized resellers, counterfeit — a top CPG fear | "38% of your page-one shelf on Walmart is third-party resellers." | 9 |
| 2 | **Cross-retailer price spread** (from `price`) | Same SKU priced differently across retailers right now = channel conflict, MAP leakage | "The same product is 17% cheaper on Walmart than Target right now." | 10 |
| 3 | **`recentSales`** (demand velocity) | What sells ≠ what ranks; the gap is the opportunity | "The #6-ranked product is the #1 seller — you're outranked by what shoppers ignore." | 9 |
| 4 | **`inStock` / availability** | OOS on page one = capturable demand (rival's, or your own lost sales) | "3 competitors are out of stock right now — open demand today." | 8 |
| 5 | **`originalPrice`** (promo depth/density) | Promo intensity = competitive pressure & margin environment, by the hour | "41% of the shelf is on promo right now, led by Walmart at 24% off." | 8 |
| 6 | **`productUrl`** (click-to-verify) | Turns every claim into live proof in front of a skeptic | *click* → the real PDP confirms it on the spot. | 8 |
| 7 | **`pricePerUnit`** (true value) | Sticker price hides pack-size games; unit price is the real comparison | "You look pricier by sticker but are 12% cheaper per ounce." | 7 |
| 8 | **`reviewCount`** (demand moat) | Review volume ≠ shelf rank; entrenchment the rankings don't show | "You lead the shelf, but a rival has 3× your review base." | 6 |
| 9 | **`rating`** (quality vs paid visibility) | Are top results actually good, or is spend carrying weak products? | "The #2 sponsored result rates 4.1 vs the 4.6 category norm." | 6 |
| 10 | **`badge`** (Amazon's Choice / Prime) | "Amazon's Choice" is the default-buy for voice/quick purchase | "A rival holds Amazon's Choice for your #1 keyword." | 6 |

**The pattern that matters:** the highest-wow items (1, 2, 3, 4) are all **cross-retailer divergence** or **what-you-can't-see-in-one-tool**. That's the wedge.

---

## 5. Ideal page structure if rebuilt from scratch

Discovery-first, personal, an **executive briefing** — not a dashboard. Six zones:

```
① SEARCH-FIRST HERO
   "See your brand on the shelf — right now."
   One big input · Category / Brand / Keyword tabs · (geo selector — teaser)
   Sub: "Live from Amazon, Walmart & Target search. No login."

② THE VERDICT (first screen, above the fold)  ← the aha, immediately
   3–4 exec cards from the live pull:
     Biggest Winner · Biggest Threat · Biggest Opportunity · Watchout
   Each: one line + one number + retailer color. "So what," not charts.
   Proof strip: "Pulled live 2:17 PM · click any product to verify ↗"

③ YOUR BRAND (auto when a brand is detected/searched)
   Rank · share · gap to leader · "where you're invisible"
   → the personalized FOMO that earns the conversation

④ WHAT YOU CAN'T GET ELSEWHERE  ← the differentiators, stacked
   • Cross-retailer price gap (same SKU, 3 prices)
   • 1P vs 3P seller mix
   • Demand ≠ visibility
   • Localized: National vs NYC vs LA (real or clearly-labeled teaser)
   Each framed: "Your single-retailer report would never show this."

⑤ ASK NIMBLE AI (structured cards)
   directAnswer · evidence chips · what it means · next step · limitations

⑥ CONVERSION (at peak curiosity, not the end)
   "Run my brand → email me this live audit" (capture)
   + "See it at scale across your 15 retailers — Booth #A-42"
```

Key shifts vs today: **verdict before analytics**, **brand-personal before category**, **differentiators promoted out of Act 3**, **scale/breadth made visible**, **capture at the peak**.

---

## 6. Sprint 2 initiatives — ranked

Scores 1–10. Effort is raw cost (higher = more work).

| Initiative | Impact | Effort | Exec appeal | Conf appeal | Take |
|---|---|---|---|---|---|
| **Run My Brand** (personalize the whole view to a brand) | 10 | 5 | 9 | 9 | **Biggest lever** — drives relevance, aha, AND conversion |
| **Executive Verdict Cards** | 9 | 4 | 10 | 7 | **Cheapest high-impact** — reframes everything for execs |
| **Cross-Retailer Price Gap** | 9 | 6 | 9 | 10 | **Highest wow** — needs product matching |
| **Localization Teaser** | 8 | 3* | 9 | 9 | Unique wedge; *teaser cheap, real geo medium |
| **Seller Intelligence (1P/3P)** | 8 | 4 | 9 | 8 | Unique, CPG-resonant, unused data |
| **Demand Velocity Intelligence** | 7 | 3 | 8 | 9 | Deepen the best existing aha (selling-now) |
| **Retailer Comparison Scorecard** | 7 | 5 | 8 | 7 | Good, but overlaps the verdict cards |
| **Promotion Intelligence** | 6 | 3 | 7 | 6 | Partly shipped in "right now" panel |
| **Availability Intelligence** | 6 | 2 | 7 | 6 | Partly shipped; cheap to elevate |
| **Structured Ask Nimble AI** | 6 | 5 | 6 | 5 | Polish; lower urgency |

**Biggest impact, in order:** ① **Run My Brand** ② **Executive Verdict Cards** ③ **Localization Teaser** ④ **Cross-Retailer Price Gap** (wow centerpiece) ⑤ **Seller 1P/3P**.

**Recommended Sprint 2:** **Executive Verdict Cards + Run My Brand + Localization Teaser**, with **Cross-Retailer Price Gap** as the wow module if effort allows. Rationale: this trio fixes weaknesses #1, #2, #3, and #5 simultaneously (relevance + surprise + positioning + verdict), and Price Gap delivers the single most shareable "I didn't know that." Demand Velocity / Promo / Availability are mostly cheap *elevations* of what's already there and can be folded in. Structured Ask and the Scorecard are Sprint 3.

---

## 7. What makes a prospect say "Wow, I didn't know that" — most consistently

The most *reliable* surprises contradict an assumption **and** can't be seen in a single-retailer tool. In order of consistency:

1. **Cross-retailer divergence** — the leader, the price, and the promo are *different* on Amazon vs Walmart vs Target. Always present, always counterintuitive ("I assumed it was the same everywhere"). **This is the engine** — it's true for virtually any keyword.
2. **Demand ≠ visibility** — the top seller isn't the top-ranked product. Reliably surprising and uniquely "live."
3. **3P on your own brand** — "third parties are selling *you* on page one." Visceral and personal.
4. **Localized difference** — "you're #2 in NYC, #9 in Chicago." Highest ceiling, but needs geo data.
5. **Sponsored intensity** — "62% of page one is paid." Surprising the first time.

**The most consistent single move:** lead with a **"3 ways this shelf differs across Amazon, Walmart & Target right now"** verdict — divergence is the most dependable wow because it's always there and it's the thing their single-retailer reports structurally cannot show. Personalize it to their brand (Run My Brand) and it becomes "wow, I didn't know that *about us*."
