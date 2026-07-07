# FINAL PRODUCT AUDIT

**Lens:** *Get a prospect interested enough to talk to Nimble.* Not feature count.
**Date:** 2026-06-02 · Reviewer brief: be brutal, don't protect the build.
**Verdict in one line:** the *content* is now genuinely "I didn't know that" — the *delivery* still makes a prospect work for it before the payoff lands.

---

## PART 1 — First impression (first 10 seconds)

Two very different entry points, and they behave differently:

**Desktop (booth screen):** hero headline *"Your reports show last week. See your shelf right now."* on the left; a cycling **Example** card on the right rotating real cross-retailer facts ("Folgers owns Walmart coffee — Starbucks owns Amazon"). This is the strongest 10-second asset we have — and most people will under-notice it because it's labeled "Example" and sits to the side.

**Mobile (QR scan — the real conference case):** the example card **stacks below** the hero copy and the search box. So a phone user sees: event bar → headline → sub-paragraph about "15–30× a day" → a search field → category chips. The payoff is offscreen.

- **What they notice:** the headline, the gold "Visit Booth" pill, a search box.
- **What they understand:** "some kind of live retail search tool."
- **What's confusing:** *whose* shelf? Mine? Do I have to know a category? The headline assumes the reader already runs a digital-shelf report ("Your reports show last week") — a CMO or Retail Media Director may not self-identify with that.
- **What's forgettable:** the sub-paragraph. Nobody at a booth reads three lines about refresh frequency.
- **What creates curiosity:** the cycling cross-retailer example — *if* they see it.

**Single biggest reason they leave:** the wow is gated behind an action. The page asks the prospect to *type a category* before anything surprising happens. A QR attendee with 10 seconds and one free hand will not. **We are making the prospect earn the payoff we should be handing them.**

> Fix direction (see Launch doc #1): auto-run a flagship category on load so the live answer + cross-retailer matrix *is* the landing state. Let them edit, don't make them initiate.

---

## PART 2 — Story audit

**Desired flow:** surprising → why it matters → how your brand compares → why retailers differ → proof → what Nimble can do → talk to us.

**Actual flow today:** answer ("Monster owns 44%") → **3 Things We Found** → **cross-retailer matrix** → **Run My Brand** → "Want the numbers" (collapsed) → Ask Nimble → Localization → Conversion → Raw shelf.

Coherence is **good** now — the "3 Things → matrix" spine genuinely reads like a narrated briefing. But two deviations from the stated flow:

1. **It opens with the answer, not the surprise.** "Monster owns 44%" is *expected* (big brand wins). The surprise lives one section down. The hero spends its enormous visual weight on the least surprising fact on the page.
2. **Retailer-differences come BEFORE brand-compare** — the reverse of the desired order. This was a deliberate call (cross-retailer = the wedge, so it's the centerpiece). I'd **keep** retailer-differences first because it's what only Nimble can show — but the stated flow wants brand first. This is a real fork; pick it on purpose (Launch #7), don't leave it accidental.

**Ideal story flow for the booth goal:**

```
1. THE SURPRISE        "A different brand wins on every retailer." (lead with this, not "who owns it")
2. WHY IT MATTERS      one line: your single-retailer report is blind to 2/3 of the shelf
3. WHY RETAILERS DIFFER the matrix (centerpiece, immediately — it IS the proof of #1)
4. HOW YOUR BRAND COMPARES  Run My Brand (the personal hook; absence = the gut-punch)
5. PROOF               freshness timestamp + "what we see right now" (on demand)
6. WHAT NIMBLE CAN DO  any market, any retailer (localization)
7. TALK TO US          one strong, personalized CTA
```

Net change vs today: **demote the "who owns it %" hero, promote the cross-retailer surprise to the top.** Everything else is close.

---

## PART 3 — Nimble differentiation audit

Ranked by how uniquely-Nimble each section is (10 = only Nimble can do this; 1 = any DSA tool ships it):

| Rank | Section | Diff. | Why |
|---|---|---|---|
| 1 | **Cross-retailer matrix** | 9.5 | Reading Amazon+Walmart+Target *live, side by side* is the wedge. Nobody on the floor shows this in one view. |
| 2 | **"What we see right now" + freshness timestamp** | 9 | Real-time truth ("pulled 2:17 PM") is the entire pitch. Static tools physically can't. |
| 3 | **Run My Brand → absence** ("you're not on page one") | 8.5 | The "you're invisible, here's who's taking your space" moment is emotional and only credible with live data. |
| 4 | **Localization (any market)** | 8 | "Same shelf, every city" is a capability story competitors gate behind enterprise sales. |
| 5 | **3 Things We Found** | 7 | The framing is ours; the underlying facts could be reconstructed — but the surprise-curation is differentiated. |
| 6 | **Selling now (demand ≠ visibility)** | 7 | Genuinely novel signal, but buried behind the "numbers" toggle. |
| 7 | **Hero "who owns it %"** | 3 | Jungle Scout, Helium 10, Profitero, Stackline all show share of shelf. **Table stakes.** |
| 8 | **Share of Shelf bars** | 2.5 | The single most generic thing in the app. Every tool has this exact bar chart. |
| 9 | **Ask Nimble (chatbot)** | 2 | In 2026 every analytics tool bolts on a chat box. Ours is well-formatted, but a chat box does **not** say "Nimble is different." |
| 10 | **Raw shelf explorer** | 1.5 | A data table. Anyone can build it. |

**Takeaway:** our strongest differentiation (matrix, freshness, absence, localization) is real — but the page still spends prime real estate (the hero) and an interactive centerpiece (Ask) on our *least* differentiated assets.

---

## PART 4 — Executive attention audit (30 seconds)

**What a VP actually remembers after 30s today:**
1. "Nimble does live retail shelf data." (good)
2. The big brand + % in the hero. (generic — every tool shows this)
3. Possibly nothing else, because the matrix and the CTA both require scrolling.

**What we WANT them to remember:**
1. The shelf is **different on every retailer** — and my reports miss it.
2. Nimble shows it **live**, this second.
3. I should **talk to Nimble** about my brand / my markets.

**The gap is real:** in 30 seconds, the differentiator (matrix) and the ask (CTA) are both below the fold, while the hero burns attention on the one fact competitors also have. We are optimizing the 5-minute read, not the 30-second scan. At a booth, only the 30-second scan exists.

---

## PART 7 — AI audit

- **Ask Nimble:** now returns a bold one-line answer + 2–3 scannable bullets (good — no more prose wall). But strategically it's a **me-too chatbot**. It invites open-ended play that can wander, and it does nothing to differentiate Nimble. It's a *toy*, not a *closer*. Keep it tiny and structured, or cut it from the exec path. Do **not** make it a centerpiece.
- **Hero AI summary line:** a single streamed sentence under the answer. Fine as a touch of life; don't let it grow. It currently competes with the deterministic answer for attention.
- **3 Things / findings:** these are rule-ranked, not AI — good. Keep it that way; determinism = credibility.

**Ideal AI format (already mostly there):** never prose. Always *answer → 2–3 evidence chips → one "so what."* Cap responses. The moment AI emits a paragraph, it reads like every other bolted-on copilot.

**Recommendation:** AI is currently *net neutral* — well-built but not pulling its weight on the conversion goal. Shrink Ask Nimble's footprint; let the deterministic surprises carry the story.

---

## PART 8 — Simplification audit (remove 30%)

**Remove / demote first, in order:**
1. **Raw shelf explorer** — most generic, longest, least exec. Cut from default; link it for the one engineer who asks.
2. **Share of Shelf bars** — redundant with the hero and the matrix. The matrix already shows leadership per retailer. Keep one, not both.
3. **Ask Nimble** — demote to a compact 2-question widget, or move entirely behind "the numbers." It's interactive but off-goal.
4. **Hero sub-paragraph** ("15–30× a day…") — one clause, not three lines.
5. **One of the two dark "live signal" panels** (What we see right now vs Selling now) — they overlap thematically; pick the stronger (freshness) for the default view.

**Emphasize MORE:**
- The **cross-retailer matrix** (it should be impossible to miss — top of the result, not third).
- The **freshness timestamp** (make "pulled 2:17 PM, live" a hero-level badge, not a quiet line).
- **One** CTA, personalized to the brand they ran, repeated at the absence moment and after the matrix.

**Net:** the app is ~30% too long for its audience. Cutting the generic/duplicative third makes the differentiated 70% hit harder.

---

## Bottom line
The story and copy are now executive-grade. The **packaging** is not: the surprise is buried under an expected fact, the differentiator and the ask are below the fold, and a chatbot + a data table dilute a sharp pitch. Fix sequencing and first-paint, not features.
