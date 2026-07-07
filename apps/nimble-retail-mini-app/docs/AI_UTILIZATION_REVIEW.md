# AI UTILIZATION REVIEW

**Focus:** Ask Nimble + Executive Verdicts — is Claude structured for decision support, or does it feel like ChatGPT?
**Date:** 2026-06-02 · Ruthless.

---

## PART 6 — Ask Nimble AI

**Current implementation:**
- Prompt: `ANALYST_SYSTEM` ("punchy analyst, lead with the surprise, connect a number to so-what") + a task that asks for *a one-line answer, then 2–3 "why it's interesting" bullets* (`/api/ask`, `claude-sonnet-4-6`, streamed text).
- Render: `ask-the-data.tsx` `Answer` component splits the first line (bold) from the bullets.

**Assessment:** this is already a big step up from prose — but it's "interesting facts," not **decision support**, and "interesting" is exactly what reads as ChatGPT. The bullets explain *why it's interesting*; they don't tell an exec *what to do*. There's no fixed, scannable contract.

**Target structure you asked for:**
> **Answer** → **Why It Matters** → **Evidence** → **Recommended Action**

**Recommendation (concrete):**
1. **Switch from free text to a typed schema** — use `streamObject` with `{ answer, whyItMatters, evidence: string[], action }` (mirror the existing `insightsSchema` pattern in `ai-context.ts`). A schema *guarantees* the four parts every time; today's "first line + bullets" parsing is best-effort and can drift.
2. **Rewrite the prompt** around the four roles, grounded hard in the data: *answer ≤ 18 words; whyItMatters = the strategic consequence; evidence = 2–3 specific numbers/contrasts pulled from the context; action = one concrete next step a brand manager could take this week.*
3. **Render four labeled blocks** (Answer bold; Why It Matters; Evidence as chips; Recommended Action in a gold-accented row) so it's identical to the Run-My-Brand / verdict visual language — reinforces "this is a tool," not "a chatbot."
4. **Keep Sonnet** here — interpretation + action is worth the reasoning; Haiku would flatten the "why."
5. **Keep it grounded** — `buildDataContext` already prevents fabrication; the schema makes the *shape* reliable too.

**Net:** Ask stops being "ask the data a question and get a paragraph" and becomes "ask a question, get a decision." This is the single most valuable Claude change in the app — because Ask is the one place Claude does something deterministic logic can't.

---

## PART 7 — Executive Verdicts (now "3 Things We Found" + the 5 `verdicts`)

**Provenance:** **100% Nimble + deterministic. 0% Claude.** `buildFindings` / `buildVerdicts` rank existing signals and write the copy from templates. Nimble supplies the facts; deterministic logic selects, ranks, and phrases.

**Should Claude be more involved here? — No, not on the critical path.** Three reasons:
1. **Credibility.** These are the boardroom claims. A deterministic verdict cannot hallucinate a share, a leader, or a price in front of a VP. That guarantee is worth more than prettier prose.
2. **Speed.** They render instantly with the data. A Claude verdict path would add latency to the most important content.
3. **Consistency.** Templated verdicts are stable across pulls; an LLM would vary phrasing run-to-run, which reads as flaky in a live demo.

**Should Claude be *less* involved? — It already is (zero).** Correct.

**The one defensible Claude role here is additive, not core:** *progressive enrichment* of the one-line "why" under each finding — keep the deterministic headline + why on screen instantly, then let Claude optionally sharpen the "why" sentence after paint (never blocking, falls back to the deterministic line on error/timeout). Treat as a nice-to-have, not a requirement. **Do not move the verdict WHAT onto Claude.**

---

## Classification recap & the deterministic/Claude/remove split

| Claude call | Classification | Recommendation |
|---|---|---|
| Hero summary line | Useful → **borderline Unnecessary** (restates the engine) | **Repurpose** to interpretation (the "why"/"watch") — or **remove** and let the deterministic kicker stand. |
| Ask Nimble | **Essential** | **Upgrade** to Answer/Why/Evidence/Action via `streamObject` schema. |
| Email exec summary | **Useful** | **Keep** (off critical path) — or align it to the same 4-part shape. |

**Stay deterministic (never Claude):** hero answer, kicker, 3 Things headlines, matrix, Run My Brand, localization, Selling Now.
**Use Claude:** Ask (interpretation + action), email summary (polish), optional async enrichment of "why" lines.
**Remove/repurpose:** the hero summary line as it exists today.

**The principle:** *more Claude is not the goal; better-placed Claude is.* Today Claude is slightly mis-deployed (one redundant call) and under-deployed (Ask not yet a decision tool). Fix both and Claude becomes a true amplifier instead of a narrator.
