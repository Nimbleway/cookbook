# AI Architecture Review (Claude)

**App:** Nimble Retail Intelligence Experience
**Scope:** Every Claude call site, prompts/schemas, what's structured vs freeform, and recommendations.
**Date:** 2026-06-01

---

## 0. TL;DR

- Claude is **well-guardrailed**: it only ever sees **aggregated facts** from `buildDataContext`, never raw product rows, and is told "use ONLY the data provided."
- Models: **Haiku 4.5** for fast structured insights, **Sonnet 4.6** for Ask + summary + report.
- **Insights are structured** (Zod → headline + 3 cards) and render as cards. ✅
- **Ask-the-Data, the summary line, and the email exec-summary are freeform paragraphs.** ⚠️ The product direction is to make these **structured cards** with an explicit `limitations` field.
- Prompt caching is configured (ephemeral on system + context); a no-op for today's small prompts but correctly future-proofed.

---

## 1. Call sites

| Route | Model | SDK fn | Output | Streaming | Caching |
|---|---|---|---|---|---|
| `/api/insights` | `claude-haiku-4-5` | `streamObject` | **Structured** (`insightsSchema`: headline + 3 cards) | ✅ `toTextStreamResponse()` | ✅ |
| `/api/ask` | `claude-sonnet-4-6` | `streamText` | **Freeform text** (modes `summary` ≤180 tok, `ask` ≤500 tok) | ✅ | ✅ |
| `/api/report` | `claude-sonnet-4-6` | `generateText` | **Freeform text** (3–4 sentence exec summary, best-effort) | ❌ | ✅ |

- `temperature: 0.4` across all calls.
- `/api/report` Claude call is wrapped in try/catch — the branded HTML report still generates if Claude fails (graceful degradation).
- Client consumption: `useAiInsights` + `extractHeadline` in `results-experience.tsx` stream the headline token-by-token (renders ~1–2s) and parse the full object for cards; `ask-the-data.tsx` appends streamed text into a chat bubble.

---

## 2. Prompts & schema (`src/lib/ai-context.ts`)

**`ANALYST_SYSTEM`** (system, cached): "senior retail/eCommerce category analyst… data collected in real time from retailer search results via Nimble. RULES: Use ONLY the data provided. Never invent products, brands, prices, or numbers. Be punchy… Lead with the most surprising insight… connect a number to 'so what'… contrast retailers… don't dwell on missing retailers."

**`buildDataContext(payload)`** (user message, cached): serializes **only aggregated facts** — keyword, retailers with data, cross-retailer brand share (top 10: %, placements, organic/sponsored split, avg rank), per-retailer breakdown (total, sponsored %, leader, top 3), and KPI label/value pairs. **No raw rows.**

**`analystMessages(context, task)`**: `[system(cached), user([context(cached), task])]`. `CACHE = { anthropic: { cacheControl: { type: "ephemeral" } } }`.

**Tasks:**
- `SUMMARY_INSTRUCTION` — "2–3 short sentences… single most striking takeaway… make a brand manager think 'I didn't realize that.'"
- `INSIGHTS_INSTRUCTION` — "punchy, exec-ready brief: one-line headline and EXACTLY 3 cards (title/what/why/action). Lead with the most surprising cross-retailer dynamic."
- Ask mode — injects `Question: {q}\n\nAnswer using only the data above.`
- Report — "3–4 sentence executive summary… who owns this category, the most surprising cross-retailer dynamic, single highest-priority action."

**`insightsSchema`** (Zod): `{ headline: string, cards: [{ title, what, why, action, tone: enum(positive|warning|neutral|opportunity) }] × exactly 3 }`.

---

## 3. Structured vs freeform

| Output | Today | Target |
|---|---|---|
| Insights (headline + 3 cards) | ✅ Structured (Zod) → cards | Keep |
| Ask-the-Data answer | ⚠️ Freeform paragraph bubble | **Structured card** |
| Summary line | ⚠️ Freeform text | **Structured** (fold into insights/exec summary) |
| Email exec summary | ⚠️ Freeform text | **Structured** |

---

## 4. Recommendations (carried to roadmap §5)

Move the freeform calls to **structured outputs**, rendered as cards, matching the requested shapes:

```ts
type ExecutiveSummary = {
  headline: string;
  takeaways: { label: string; detail: string; tone: Tone }[];
  watchouts: { label: string; detail: string }[];   // pricing / availability
  questionsToAsk: string[];                          // discovery prompts
};

type AskNimbleAnswer = {
  directAnswer: string;
  supportingEvidence: { stat: string; source: string }[]; // e.g. "Quest 19% of page one", "Amazon"
  whatItMeans: string;
  recommendedNextStep: string;
  limitations: string[];   // e.g. "Single point-in-time snapshot; no historical trend."
};
```

- Use `streamObject` (Haiku for Ask too — fast/cheap) or `messages.parse()` with the schema; render as cards (`directAnswer` headline, evidence chips, "what it means", "next step", muted `limitations`).
- The **`limitations` field is a credibility feature**: it pre-empts skeptics by stating the data is a current snapshot — turning the honesty constraint into a trust signal.
- Keep the "use ONLY provided data" guardrail and `buildDataContext` (aggregates only) — it's the reason Claude never hallucinates numbers.
- Once prompts grow past ~2048 tokens, the ephemeral cache becomes a real latency/cost win across summary→insights→ask→report in a session.
