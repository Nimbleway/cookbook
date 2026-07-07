import { z } from "zod";
import type { InsightPayload } from "./types";
import { RETAILER_META } from "./retailers";

// Builds a compact, factual context block from computed insights. This is the
// ONLY retail data Claude sees — it summarizes/explains/recommends over it and
// must never invent products, brands, or numbers beyond what's here.
export function buildDataContext(p: InsightPayload): string {
  const lines: string[] = [];
  lines.push(`CATEGORY / KEYWORD: ${p.keyword}`);
  lines.push(
    `RETAILERS WITH DATA: ${p.retailers.map((r) => RETAILER_META[r].label).join(", ") || "none"}`,
  );
  if (p.failedRetailers.length) {
    lines.push(
      `RETAILERS UNAVAILABLE: ${p.failedRetailers.map((r) => RETAILER_META[r].label).join(", ")}`,
    );
  }
  lines.push("");
  lines.push("CROSS-RETAILER BRAND SHARE (page-one placements):");
  p.brandShare.slice(0, 10).forEach((b) => {
    lines.push(
      `  - ${b.brand}: ${Math.round(b.share * 100)}% share (${b.count} placements, ${b.sponsoredCount} sponsored / ${b.organicCount} organic, avg rank ${b.avgRank})`,
    );
  });
  lines.push("");
  lines.push("PER-RETAILER BREAKDOWN:");
  p.perRetailer.forEach((s) => {
    const top3 = s.brands
      .slice(0, 3)
      .map((b) => `${b.brand} ${Math.round(b.share * 100)}%`)
      .join(", ");
    lines.push(
      `  ${RETAILER_META[s.retailer].label}: ${s.totalResults} results, ${s.sponsoredPct}% sponsored, leader ${s.topBrand}. Top brands: ${top3}`,
    );
  });
  lines.push("");
  lines.push("KEY METRICS:");
  p.kpis.forEach((k) => lines.push(`  - ${k.label}: ${k.value}${k.sub ? ` (${k.sub})` : ""}`));
  return lines.join("\n");
}

export const ANALYST_SYSTEM = `You are a senior retail/eCommerce category analyst presenting live digital-shelf intelligence to an executive. The data was collected in real time from retailer search results by Nimble.

RULES:
- Use ONLY the data provided. Never invent products, brands, prices, or numbers.
- Be punchy and conversational, like a sharp analyst talking to a brand manager — not a report.
- Lead with the most surprising/non-obvious insight. Create curiosity.
- Always connect a number to "so what" — why it matters for their brand.
- Keep it tight. No preamble, no "based on the data". Just the insight.
- When relevant, contrast retailers (Amazon vs Walmart vs Target) — differences are the most interesting story.
- If a retailer's data is unavailable, simply work with what's present; don't dwell on it.`;

// ─── Prompt caching ─────────────────────────────────────────────────────────
// Build the analyst message array with Anthropic prompt-cache breakpoints on
// the (stable) system prompt and the (per-search, stable) data context, so the
// insights/ask/report calls in one session reuse the cached prefix.
// NOTE: Sonnet 4.6's min cacheable prefix is ~2048 tokens; for small contexts
// this is a no-op, but it's the correct, future-proof shape and pays off as
// soon as the shared prefix grows.
const CACHE = { anthropic: { cacheControl: { type: "ephemeral" as const } } };

export function analystMessages(context: string, task: string) {
  return [
    { role: "system" as const, content: ANALYST_SYSTEM, providerOptions: CACHE },
    {
      role: "user" as const,
      content: [
        { type: "text" as const, text: context, providerOptions: CACHE },
        { type: "text" as const, text: task },
      ],
    },
  ];
}

// ─── Hero headline (the only Claude narrative on the results page) ──────────
// One cached call returns a single striking takeaway that streams into the hero
// line. The deterministic engine (verdicts, differences, etc.) carries every
// number — Claude only narrates. (Previously also emitted 3 cards; those were
// discarded once verdicts became deterministic, so the schema is headline-only.)
export const insightsSchema = z.object({
  headline: z
    .string()
    .describe(
      "ONE sentence of INTERPRETATION — the strategic read BEHIND the numbers. Not a restatement of who leads or what differs (the page already shows that). Explain WHY this shelf looks the way it does, or the single thing a brand should take from it.",
    ),
});

// The hero line is INTERPRETATION, not summarization — the deterministic engine
// already states who leads and what differs, so Claude must add the "why/so-what".
export const INSIGHTS_INSTRUCTION = `In ONE sentence, give the strategic INTERPRETATION behind this shelf — WHY it looks the way it does, or the one thing a brand should take from it (e.g. why a retailer's shelf skews to certain brands, or the non-obvious implication of the leader pattern). Do NOT restate who leads or what the shares are — the reader already sees that. Use only the data above. No preamble.`;

// ─── Ask Nimble — structured decision support (not chat) ─────────────────────
// A typed shape guarantees the four parts every time, so the answer reads like
// a tool, not ChatGPT. Grounded strictly in the provided data context.
export const askSchema = z.object({
  finding: z
    .string()
    .describe("The direct answer as ONE punchy finding. Max ~16 words. Cite a real number/brand/retailer. No preamble, no restating the question."),
  whyItMatters: z
    .string()
    .describe("ONE sentence on the strategic consequence — the so-what, not a number restate. Max ~18 words."),
  action: z
    .string()
    .describe("ONE concrete next step, imperative and specific. Max ~16 words."),
});

export const ASK_INSTRUCTION = `Answer using ONLY the data above, as three tight parts — Finding (the direct answer, leading with a real number/brand/retailer), Why it matters (the so-what), and Do this (one concrete step). Be specific. No preamble, no paragraphs, no hedging.`;

// ─── Paid vs Organic — the "earned vs bought" verdict ────────────────────────
// Claude INTERPRETS the deterministic sponsored/organic split into an executive
// verdict. The numbers (leaders, %, dependence) are computed and shown by the
// engine; Claude only narrates the story behind them. A deterministic fallback
// always exists client-side, so this call is enrichment, never load-bearing.
export const paidOrganicSchema = z.object({
  verdict: z
    .string()
    .describe(
      "ONE punchy sentence answering: are brands winning here by EARNING visibility or BUYING it? Name the organic leader and/or the brand whose lead is propped up by ads. Max ~22 words. No preamble.",
    ),
  soWhat: z
    .string()
    .describe(
      "ONE sentence on what this paid-vs-organic split means for a brand competing on this shelf — the strategic consequence, not a number. Max ~20 words.",
    ),
});

export const PAID_ORGANIC_INSTRUCTION = `Focus ONLY on the sponsored-vs-organic split in the data above (the sponsored/organic counts per brand and the % sponsored per retailer). In ONE sentence, say whether this shelf is won by EARNING visibility or BUYING it — name the organic leader and the paid leader, and call out any brand whose apparent dominance is propped up by ads. Then give a one-sentence "so what" for a brand competing here. Use only real brands and numbers from the data. Write in normal sentence case — never ALL-CAPS words for emphasis. No preamble.`;

// ─── Monitoring teaser — "what we'd watch for you" ───────────────────────────
// Forward-looking only: names the metric worth tracking over time. MUST NOT
// claim any past change/trend — there is no history. Deterministic fallback
// exists client-side, so this is enrichment, never load-bearing.
export const monitoringSchema = z.object({
  watch: z
    .string()
    .describe(
      "ONE forward-looking sentence: the single most important thing to monitor over time on THIS shelf and why. Use 'we'd watch…' framing. NEVER claim a past change or trend (there is no history). Name a real brand/retailer/number from the data. Max ~24 words.",
    ),
});

export const MONITORING_INSTRUCTION = `Nimble can track this shelf over time — share of shelf, share of voice (sponsored), price, availability, and search rank. In ONE forward-looking sentence, name the single most important metric to WATCH on this shelf and why, based on the data above. Use "we'd watch…" framing. NEVER claim a past change, movement, or trend — there is no history yet. Reference a real brand/retailer/number from the data. No preamble.`;

// ─── Brand signature — the brand-specific "I didn't know that" ───────────────
// Claude names the ONE pattern that makes a brand's footprint distinct (retailer
// skew, paid reliance, organic strength) — the cross-retailer read a dashboard
// can't phrase. Deterministic signature is computed in brand-analysis.ts and
// always shown first; this only sharpens the wording.
export const brandSignatureSchema = z.object({
  headline: z
    .string()
    .describe(
      "The single most distinctive thing about THIS brand's footprint, as a punchy claim. Max ~12 words. e.g. 'Bloom is invisible on Amazon' / 'Red Bull's lead is rented'.",
    ),
  detail: z
    .string()
    .describe(
      "ONE sentence backing the headline with a real number/retailer from the data, plus the so-what for this brand. Max ~26 words.",
    ),
});

export const BRAND_SIGNATURE_INSTRUCTION = `Looking ONLY at the named brand's footprint in the data above (its share per retailer, where it's absent, and its sponsored-vs-organic split): name the SINGLE most distinctive thing about how THIS brand shows up — e.g. it's missing on a retailer where it should compete, its visibility is concentrated on one retailer, its lead is propped up by ads, it wins organically, or it's barely on the shelf at all. Give a punchy headline + one detail sentence, always naming a specific retailer and a real number.
RULES: Never call a single-digit or low share "strong" — if a brand's biggest share is small, say it's barely present and lead with that. Never use vague words like "differs", "varies", or "balanced" — always say the concrete thing. Never generic ("close the gap", "improve visibility"). No preamble.`;
