import type { NextRequest } from "next/server";
import { anthropic } from "@ai-sdk/anthropic";
import { generateObject } from "ai";
import type { InsightPayload } from "@/lib/types";
import {
  analystMessages,
  buildDataContext,
  paidOrganicSchema,
  PAID_ORGANIC_INSTRUCTION,
} from "@/lib/ai-context";
import { aiEnrichmentDisabled, getAiCache, setAiCache } from "@/lib/ai-cache";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Haiku 4.5 — interpreting the sponsored/organic split into a one-line verdict
// is a tight summarization task; speed matters more than depth here.
const MODEL = "claude-haiku-4-5";

// ─── Paid vs Organic verdict (Claude as interpreter) ─────────────────────────
// Returns a small { verdict, soWhat } object. The engine already computed every
// NUMBER and shipped a deterministic verdict/soWhat — this only enriches the
// narrative. The client renders the deterministic strings instantly and swaps
// in Claude's when it returns, so a 503 (no key) or failure is a no-op.
export async function POST(req: NextRequest) {
  if (!process.env.ANTHROPIC_API_KEY || aiEnrichmentDisabled()) {
    return new Response("AI enrichment off", { status: 503 });
  }
  const body = (await req.json().catch(() => ({}))) as { payload?: InsightPayload };
  if (!body.payload) {
    return new Response("payload required", { status: 400 });
  }

  // Cache by category so repeated demos don't re-spend Claude tokens.
  const cacheKey = `paid-organic:${body.payload.keyword.trim().toLowerCase()}`;
  const cached = getAiCache(cacheKey);
  if (cached) return Response.json(cached);

  try {
    const { object } = await generateObject({
      model: anthropic(MODEL),
      schema: paidOrganicSchema,
      messages: analystMessages(buildDataContext(body.payload), PAID_ORGANIC_INSTRUCTION),
      temperature: 0.4,
      maxOutputTokens: 300,
    });
    setAiCache(cacheKey, object);
    return Response.json(object);
  } catch {
    // Enrichment only — the client already has the deterministic verdict.
    return new Response("paid-organic interpretation failed", { status: 502 });
  }
}
