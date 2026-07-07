import type { NextRequest } from "next/server";
import { anthropic } from "@ai-sdk/anthropic";
import { generateObject } from "ai";
import type { InsightPayload } from "@/lib/types";
import {
  analystMessages,
  buildDataContext,
  brandSignatureSchema,
  BRAND_SIGNATURE_INSTRUCTION,
} from "@/lib/ai-context";
import { aiEnrichmentDisabled, getAiCache, setAiCache } from "@/lib/ai-cache";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-haiku-4-5";

// ─── Brand signature (Claude as interpreter) ─────────────────────────────────
// Sharpens the deterministic brand signature into the brand-specific "I didn't
// know that". The component shows the deterministic signature instantly and
// swaps this in; a 503/failure is a no-op.
export async function POST(req: NextRequest) {
  if (!process.env.ANTHROPIC_API_KEY || aiEnrichmentDisabled()) {
    return new Response("AI enrichment off", { status: 503 });
  }
  const body = (await req.json().catch(() => ({}))) as {
    payload?: InsightPayload;
    brand?: string;
  };
  if (!body.payload || !body.brand) {
    return new Response("payload and brand required", { status: 400 });
  }

  const cacheKey = `brand-sig:${body.payload.keyword.trim().toLowerCase()}:${body.brand.trim().toLowerCase()}`;
  const cached = getAiCache(cacheKey);
  if (cached) return Response.json(cached);

  try {
    const task = `Brand: ${body.brand}\n\n${BRAND_SIGNATURE_INSTRUCTION}`;
    const { object } = await generateObject({
      model: anthropic(MODEL),
      schema: brandSignatureSchema,
      messages: analystMessages(buildDataContext(body.payload), task),
      temperature: 0.4,
      maxOutputTokens: 220,
    });
    setAiCache(cacheKey, object);
    return Response.json(object);
  } catch {
    return new Response("brand-signature interpretation failed", { status: 502 });
  }
}
