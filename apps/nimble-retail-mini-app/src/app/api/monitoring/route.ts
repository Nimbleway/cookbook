import type { NextRequest } from "next/server";
import { anthropic } from "@ai-sdk/anthropic";
import { generateObject } from "ai";
import type { InsightPayload } from "@/lib/types";
import {
  analystMessages,
  buildDataContext,
  monitoringSchema,
  MONITORING_INSTRUCTION,
} from "@/lib/ai-context";
import { aiEnrichmentDisabled, getAiCache, setAiCache } from "@/lib/ai-cache";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-haiku-4-5";

// ─── Monitoring teaser line (Claude as interpreter) ──────────────────────────
// Returns { watch } — a forward-looking "what we'd track for you" line. The
// component shows a deterministic fallback instantly and swaps this in; a 503
// (no key) or failure is a no-op. Strictly future-tense — no fabricated history.
export async function POST(req: NextRequest) {
  if (!process.env.ANTHROPIC_API_KEY || aiEnrichmentDisabled()) {
    return new Response("AI enrichment off", { status: 503 });
  }
  const body = (await req.json().catch(() => ({}))) as { payload?: InsightPayload };
  if (!body.payload) {
    return new Response("payload required", { status: 400 });
  }

  const cacheKey = `monitoring:${body.payload.keyword.trim().toLowerCase()}`;
  const cached = getAiCache(cacheKey);
  if (cached) return Response.json(cached);

  try {
    const { object } = await generateObject({
      model: anthropic(MODEL),
      schema: monitoringSchema,
      messages: analystMessages(buildDataContext(body.payload), MONITORING_INSTRUCTION),
      temperature: 0.4,
      maxOutputTokens: 200,
    });
    setAiCache(cacheKey, object);
    return Response.json(object);
  } catch {
    return new Response("monitoring interpretation failed", { status: 502 });
  }
}
