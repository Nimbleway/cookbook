# Claude Utilization Audit

**Question:** exactly how is Anthropic used today, what value does each call deliver, and what's the right balance of deterministic logic vs Nimble data vs Claude?
**Date:** 2026-06-01 · **Goal: max user value + credibility — NOT max Claude.**

---

## 0. TL;DR

Claude is used in **3 routes** as a thin narrative layer on top of a deterministic engine. That architecture is correct. But two things are wasteful after the Sprint-2 redesign:

- **`/api/insights` generates a headline + 3 cards, but the UI only renders the headline.** The 3 cards are discarded every search → pure waste (tokens + latency).
- **`/api/ask`'s `summary` mode is dead code** — only `ask` is ever called.

Claude is **value-additive narration, not load-bearing**: the app's core value and every number survive without it. That's the right place for it.

---

## 1. Every Claude call

### A. `/api/insights` — hero headline (+ discarded cards)
- **Location:** `src/app/api/insights/route.ts`; consumed by `useAiInsights` in `results-experience.tsx` → the italic line under the hero ("Nimble AI is reading the live shelf… → {headline}").
- **Model / SDK:** `claude-haiku-4-5`, `streamObject`, Zod `insightsSchema` (`{ headline, cards[3] }`), `maxOutputTokens: 700`, temp 0.4. Prompt-cached system + context.
- **Prompt:** `ANALYST_SYSTEM` + `buildDataContext(payload)` + `INSIGHTS_INSTRUCTION` ("punchy headline + EXACTLY 3 cards…").
- **Inputs:** aggregated facts only (brand share top-10, per-retailer breakdown, KPI label/values). Never raw rows.
- **Outputs:** `headline` (1–2 sentences) **+ 3 cards** — **only the headline is rendered; cards are discarded.**
- **Est. tokens:** ~650 in / ~290 out (headline ~40 + 3 cards ~250). **Headline-only would be ~50 out.**
- **Latency:** ~1–2s to first headline token; non-blocking (fires after the real insights are on screen).
- **User value:** an analyst-voice one-liner on the hero. The rule-based hero answer is already there, so this is flavor, not substance.
- **Classification:** headline = **Useful** · the 3 cards = **Unnecessary (discarded).**

### B. `/api/ask` — Ask Nimble AI (and a dead summary mode)
- **Location:** `src/app/api/ask/route.ts`; consumed by `ask-the-data.tsx` (Act 3, "Ask Nimble AI").
- **Model / SDK:** `claude-sonnet-4-6`, `streamText`, freeform text. `ask` ≤500 out · `summary` ≤180 out. Prompt-cached prefix.
- **Prompt:** `ANALYST_SYSTEM` + `buildDataContext` + either the user's question ("answer using only the data above") or `SUMMARY_INSTRUCTION`.
- **Inputs:** aggregated facts + the user's typed question.
- **Outputs:** freeform answer (paragraph).
- **Est. tokens:** ~670 in / ~200 out per question. On-demand only.
- **Latency:** ~1–3s streamed, user-initiated (never blocks).
- **User value:** the only genuinely *interactive* AI moment — a "test drive" hook at the booth. Real, but low-frequency.
- **Classification:** `ask` mode = **Useful** (keep) · `summary` mode = **Unnecessary (dead — never invoked; hero headline comes from `/api/insights`).**

### C. `/api/report` — emailed executive summary
- **Location:** `src/app/api/report/route.ts`; consumed in the emailed HTML (`report-html.ts`) as a small "Analyst summary · Nimble AI" line under the verdict. **The PDF-download route does NOT call Claude (instant).**
- **Model / SDK:** `claude-sonnet-4-6`, `generateText` (not streamed), `maxOutputTokens: 260`, wrapped in try/catch (best-effort — report still sends without it).
- **Prompt:** `ANALYST_SYSTEM` + `buildDataContext` + "3–4 sentence executive summary: who owns the category, the most surprising cross-retailer dynamic, the single highest-priority action."
- **Inputs:** aggregated facts.
- **Outputs:** 3–4 sentence summary.
- **Est. tokens:** ~650 in / ~180 out. Fires only on email submit (and email send isn't wired yet, so currently fires on lead capture).
- **Latency:** ~2–3s, off the critical path (graceful fail).
- **User value:** a nice human-readable opener in the take-home report.
- **Classification:** **Useful** (keep, best-effort). Only matters once email delivery is wired.

### Summary table

| Call | Model | Output used? | ~tokens (in/out) | Latency | Value | Class |
|---|---|---|---|---|---|---|
| `/api/insights` headline | Haiku 4.5 | ✅ hero line | 650 / 40 | ~1–2s, async | flavor on hero | **Useful** |
| `/api/insights` 3 cards | Haiku 4.5 | ❌ discarded | +~250 out | adds to above | none | **Unnecessary** |
| `/api/ask` (ask) | Sonnet 4.6 | ✅ chat | 670 / 200 | on-demand | interactive test-drive | **Useful** |
| `/api/ask` (summary) | Sonnet 4.6 | ❌ never called | — | — | none | **Unnecessary** |
| `/api/report` summary | Sonnet 4.6 | ✅ email line | 650 / 180 | ~2–3s, best-effort | report opener | **Useful** |

**Guardrail (good):** every call sees only `buildDataContext` (aggregated facts) and is told "never invent products, brands, prices, or numbers." Claude narrates; it never sources data.

---

## 2. Deterministic insights — could/should Claude improve them?

| Insight (deterministic today) | Could Claude improve? | Should it? | Why |
|---|---|---|---|
| **Executive Verdicts** (Winner/Threat/Opportunity/Pricing/Availability) | Marginally (phrasing) | **No** | The credibility spine. Deterministic = exact, instant, zero hallucination. Letting Claude rewrite the verdict invites drift on the numbers execs are reading. |
| **Cross-retailer differences** | Slightly punchier lead line | **No (optional)** | Facts must stay exact; the hero headline already supplies the narrative voice. |
| **Run My Brand recommended action** | Yes — more natural/consultative wording | **Maybe (low priority)** | It's per-brand and template-based today. A *structured* Haiku call could personalize the action, but it adds a per-run call + latency. Defer; templates are credible and instant. |
| **KPIs · Share of Shelf · What We See Now · price gap** | No | **No** | Pure numbers. Claude must never touch these. |
| **Hero one-liner** | — | already Claude | The right place: narration over a fact that's already on screen. |

**Principle:** Claude improves *language*, never *numbers*. Anywhere a number lives, deterministic wins on credibility and speed.

---

## 3. Recommendation — the ideal balance

**Nimble data → Deterministic logic → Claude narration.** In that order, with Claude as a thin glaze.

- **Nimble data = the only source of truth.** Every fact traces to a live pull.
- **Deterministic logic = everything quantitative:** brand normalization, share, rankings, verdicts, cross-retailer differences, "what we see now." Instant, reproducible, defensible under scrutiny. This is the product.
- **Claude = narration on top of those facts, constrained to them:** (1) the hero headline (analyst voice), (2) Ask Nimble AI (interactive exploration — the one true AI moment), (3) the emailed exec summary. Nothing that emits a number.

**Concrete moves (reduce surface, keep value):**
1. **Make `/api/insights` headline-only** — drop the 3 cards from the schema/generation. Same on-screen value, ~5× less output, faster headline, lower cost. (The cards have been dead since verdicts went deterministic.)
2. **Remove the dead `summary` mode** from `/api/ask` (and `SUMMARY_INSTRUCTION`). Dead code = confusion.
3. **Keep** Ask Nimble AI and the email summary as-is (best-effort, off critical path).
4. **Do not** push Claude into verdicts, differences, or any KPI. Leave the numbers deterministic.
5. Optional, later: a *structured* Haiku call for the Run-My-Brand action — only if it stays off the critical path.

**Net:** less token spend, lower latency, and — most importantly — **stronger credibility**, because every number on screen is deterministic and Claude is visibly a narration layer, not the engine. That's the correct answer to "max value + credibility, not max Claude." The app is ~90% there today; items #1–#2 close the gap.
