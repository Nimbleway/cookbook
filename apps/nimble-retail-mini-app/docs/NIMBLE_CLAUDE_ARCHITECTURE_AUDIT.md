# NIMBLE + CLAUDE ARCHITECTURE AUDIT

**Question:** are Nimble data and Claude working together to produce executive-ready intelligence — or is one carrying the other?
**Date:** 2026-06-02 · Grounded in the actual code. Ruthless.

**Headline:** The architecture is already correct — **Nimble → deterministic engine → (thin) Claude amplifier.** Every number and every on-screen insight is Nimble-sourced and deterministically computed. Claude is 3 small, grounded calls. The problem is not too much AI or too little — it's that one of the three Claude calls *restates* what the engine already produced instead of interpreting it.

---

## PART 1 — Every place Claude is used (there are exactly 3)

| # | Component | Model | Inputs | Prompt | Output | User value | Latency | Class |
|---|---|---|---|---|---|---|---|---|
| 1 | **Hero summary line** (`/api/insights` → `useAiInsights` in `results-experience.tsx`, rendered in `hero-insight.tsx` AI box) | `claude-haiku-4-5` | `buildDataContext()` (top-10 brand share, per-retailer breakdown, KPIs) | `INSIGHTS_INSTRUCTION`: "1–2 punchy sentences, single most striking non-obvious cross-retailer takeaway" | One `headline` string, streamed (`streamObject`, schema = headline-only) | One streamed sentence of life in the hero | ~1–2s, **async, non-blocking** (rule content already painted) | **Useful → borderline Unnecessary** |
| 2 | **Ask Nimble** (`/api/ask` ← `ask-the-data.tsx`) | `claude-sonnet-4-6` | `buildDataContext()` + user question | `ANALYST_SYSTEM` + structured task (answer line + 2–3 bullets) | Streamed answer + bullets | Answers **arbitrary** questions the engine can't anticipate | ~2–4s, **user-initiated** | **Essential** |
| 3 | **Email exec summary** (`/api/report`) | `claude-sonnet-4-6` | `buildDataContext()` + summary instruction | "3–4 sentence exec summary: who owns it, surprising cross-retailer dynamic, highest-priority action" | 3–4 sentence paragraph embedded in the emailed HTML | Polishes the take-home report | ~2–3s, **off critical path** (lead already captured) | **Useful** |

**That's the entire Claude footprint.** No Claude on the hero answer, the 3 Things, the matrix, Run My Brand, localization, or Selling Now. All deterministic.

---

## PART 2 — Every place Nimble data is used

**Source:** 3 Nimble Web Search Agents (`amazon_serp`, `walmart_serp`, `target_serp`) via `sdk.nimbleway.com/v1/agents/run` (`src/services/nimble-serp.ts`).

**Per-product fields normalized (up to 24 rows × 3 retailers ≈ 72 live points/pull):**
rank · title · brand (explicit or derived) · price · rating · reviewCount · **sponsored** · productUrl · imageUrl · **availability/inStock** · **recentSales** · **originalPrice** · pricePerUnit · **seller (1P/3P)** · **badge (Amazon's Choice/Prime)** · collectedAt.

**Deterministic calculations on top (`insight-engine.ts`):**
brand share + sponsored/organic split + avg rank · per-retailer concentration (HHI) · cross-retailer divergences (leaders / price / sponsored / availability / promo, surprise-ranked by magnitude) · same-brand cross-retailer price gap · demand velocity (parsed `recentSales` vs shelf rank) · stockouts · live discounts · promo density · paid penetration · leader gap · entry price band (p25–p75) · most-winnable retailer.

**Insights produced (all from the above, zero Claude):** hero answer, hero kicker, 3 Things We Found, cross-retailer matrix, 5 verdicts, Run My Brand (found + absent scorecards), localization (national), Selling Now.

### Is the app A) data-rich/insight-poor, B) balanced, or C) overly AI-driven?

**→ B — Balanced, and specifically: data-rich AND insight-rich, with the insight produced by deterministic logic, not Claude.**

- Not **A**: this is not a metrics dump. The engine produces genuine *interpretation* — "the leader flips by retailer," "Walmart is the most open shelf," "demand ≠ visibility," "you're invisible here, enter at $X." Those are insights, not numbers.
- Not **C**: Claude is 3 thin calls; nothing substantive depends on it. You could unplug all 3 and the intelligence survives (see Executive review, Part 10).
- The honest nuance: the *insight engine is deterministic*, which is a **strength** — it's instant, credible, and cannot hallucinate a number in front of a VP. The risk a "balanced" rating usually implies (AI making up insights) does not exist here.

---

## PART 8 — Latency: which Claude calls are worth the delay

| Call | Delay | Blocking? | Worth it? |
|---|---|---|---|
| Hero summary (Haiku) | ~1–2s | No — fires after deterministic paint | **Latency is fine; the VALUE is the problem** (it restates the kicker — see Insight Quality audit Part 4). The delay is hidden, so this is not a latency issue, it's a redundancy issue. |
| Ask (Sonnet) | ~2–4s | No — user asked | **Worth it.** This is the one call doing something deterministic logic can't. |
| Email summary (Sonnet) | ~2–3s | No — runs after "captured" | **Worth it / harmless.** Off the critical path; pure polish. |

**Maximum insight per second → the rule the app already mostly follows:**
- **Stay deterministic:** hero answer, kicker, 3 Things, matrix, Run My Brand, localization, Selling Now. (Instant, credible — never put Claude here.)
- **Use Claude:** Ask (arbitrary interpretation) and the email summary (polish).
- **Remove or repurpose:** the hero summary line. It costs a call to restate what the engine already says. Either cut it, or make it *interpret* (the "why," see Insight Quality Part 5).

---

## PART 9 — Ideal architecture vs. current

**Ideal:**
```
Nimble  →  Deterministic calculations  →  Insight engine  →  Claude interpretation  →  Executive output
```

**Current (actual):**
```
Nimble (nimble-serp.ts)
  → Deterministic calc + Insight engine (insight-engine.ts: shares, divergences, verdicts, findings, matrix)
  → Executive output (the UI / email)
        �‖  (beside the output, grounded in buildDataContext = the serialized deterministic output)
        Claude amplifier: hero line · Ask · email summary
```

**Verdict: the app follows the ideal model — with one inversion to fix.** Claude is correctly positioned *downstream of* and *grounded in* the deterministic engine (`buildDataContext` serializes the computed insights; Claude never sees raw Nimble JSON and never computes a number). The single deviation: the **hero Claude line currently summarizes the engine's output rather than interpreting it.** In the ideal model, "Claude interpretation" means *the why / the so-what*, not a re-narration of the what. Fix that one call and the architecture is textbook.

**One structural strength worth stating plainly:** because `buildDataContext` feeds Claude the *already-computed* insights (not raw rows), Claude physically cannot invent a brand, price, or share. That's the right guardrail and it's already in place.

---

## Bottom line
Nimble is the foundation; the deterministic engine is the spine; Claude is a deliberately thin amplifier. That is the correct design. The work is not to add Claude — it's to (1) make Ask a real decision tool (Answer/Why/Evidence/Action), and (2) stop the hero line from echoing the engine. See the companion docs.
