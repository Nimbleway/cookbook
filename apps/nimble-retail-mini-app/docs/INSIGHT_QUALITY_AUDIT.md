# INSIGHT QUALITY AUDIT

**Question:** for each major insight — what came from Nimble, what from deterministic logic, what from Claude? Is Claude adding value or restating data?
**Date:** 2026-06-02 · Ruthless.

---

## PART 3 — Provenance of every major insight

| Insight | Nimble provides | Deterministic logic does | Claude does |
|---|---|---|---|
| **Hero answer** ("Monster · 44% of Amazon") | brands, ranks, sponsored flags | brand-share %, peak-retailer selection, the answer sentence | — nothing — |
| **Hero kicker** ("The best-seller isn't the same on every retailer") | per-retailer leaders | divergence detection + phrasing | — nothing — |
| **3 Things We Found** | raw signals (leaders, OOS, recentSales, prices) | surprise-ranking + the headline/why copy | — nothing — |
| **Cross-retailer matrix** | every metric per retailer | table assembly + divergence flags + spread math | — nothing — |
| **Run My Brand** (found) | placements, prices, ranks | visibility score, gap, opening, winnable retailer, action | — nothing — |
| **Run My Brand** (absent) | full shelf | competitor count, top-3 grip, paid %, entry band, most-open shelf | — nothing — |
| **Selling Now** (demand ≠ visibility) | recentSales + shelf rank | parse + compare | — nothing — |
| **Localization (national)** | brand share, prices | aggregate + lock the city columns | — nothing — |
| **Hero AI summary line** | (via context) | (grounds it) | **authors it** — 1 streamed sentence |
| **Ask answers** | (via context) | (grounds it) | **authors it** — per question |
| **Email exec summary** | (via context) | (grounds it) | **authors it** — 3–4 sentences |

**So: ~95% of the intelligence a prospect sees is Nimble → deterministic. Claude authors exactly three things, and only one of them (Ask) is load-bearing.**

**Is Claude adding value?** In **Ask** — yes (arbitrary interpretation). In the **email summary** — marginally (pleasant polish). In the **hero line** — *not really* (see Part 4). The uncomfortable truth: the most-seen Claude output (the hero line) is the least valuable.

---

## PART 4 — Where Claude is merely restating data (low-value AI)

**The hero summary line is the prime offender.** Its instruction (`INSIGHTS_INSTRUCTION`) asks for "the single most striking non-obvious cross-retailer takeaway" — which is **exactly what the deterministic `heroKicker` and the 3 Things already state, computed instantly and for free.**

- Deterministic kicker: *"The best-seller isn't the same on every retailer."*
- Deterministic finding #1: *"The category leader flips by retailer."*
- Claude hero line (typical): *"Across retailers a different brand leads — Monster on Amazon, Celsius on Target."*

That third line is **restatement, not interpretation.** It's the "Quest leads by 2%" anti-pattern from your brief. It adds a Claude call, a model dependency, and 1–2s of (hidden) latency to say what the engine already said better and faster.

**Secondary, milder:** the **email exec summary** overlaps the verdicts/findings it sits above. It's lower-risk (off critical path, take-home context) but it's still 60% summary, 40% synthesis.

**Ask** can also restate when the question is trivial ("who owns this?") — but that's user-driven and acceptable.

**Verdict:** there is exactly one chronic low-value AI output — the hero line — and it's the one users see most.

---

## PART 5 — Where Claude SHOULD add value (interpretation, not summarization)

The engine is excellent at the **WHAT** (who, how much, what differs). It is structurally incapable of the **WHY** and the **SO-WHAT** — and that is precisely where Claude earns its place.

**The single highest-value untapped Claude role: explain *why* the retailers diverge.**
The engine detects *that* the leader flips (Monster on Amazon, Celsius on Target). Only Claude can hypothesize *why* and *what to do*:

> Deterministic (the what): *"Celsius leads Target; Monster leads Amazon."*
> Claude (the why / so-what): *"Target's shopper skews wellness, so Celsius and Alani Nu win there while legacy energy brands stall. If you're an incumbent, Target is your hardest shelf — lead with a zero-sugar SKU, not your flagship."*

That is interpretation deterministic logic cannot produce, and it's the difference between "interesting" and "I need to talk to these people."

**Concrete reframes (better text, not more text):**
1. **Repurpose the hero line** from restating the divergence → interpreting it: one line of *why this shelf looks the way it does* or *the one thing to watch*. Same call, far higher value.
2. **Ask → Answer / Why It Matters / Evidence / Recommended Action** (see AI Utilization review, Part 6) — force decision support, not chat.
3. **Optional progressive enrichment of the 3 Things' "why" line** — keep the headline deterministic (instant, credible), let Claude sharpen the one-line "why" *after* paint. Strictly additive; never blocks.
4. **"What to investigate next"** — Claude is well-suited to suggest the next pull ("Target's wellness skew may be regional — check it by ZIP"), turning an observation into a reason to engage.

**Principle to enforce everywhere:** Claude explains and recommends; it never recomputes or re-narrates. If a Claude output could be produced by `String(deterministicValue)`, it shouldn't be a Claude call.
