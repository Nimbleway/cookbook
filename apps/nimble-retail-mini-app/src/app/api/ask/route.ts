import type { NextRequest } from "next/server";
import { anthropic } from "@ai-sdk/anthropic";
import { streamObject } from "ai";
import type { InsightPayload } from "@/lib/types";
import {
  analystMessages,
  buildDataContext,
  askSchema,
  ASK_INSTRUCTION,
} from "@/lib/ai-context";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MODEL = "claude-sonnet-4-6";

// ─── Ask Nimble AI ──────────────────────────────────────────────────────────
// Streams a Claude Sonnet answer to the user's question, grounded strictly in
// the insight data. User-initiated and off the critical path — insights are
// already on screen before this runs.
export async function POST(req: NextRequest) {
  if (!process.env.ANTHROPIC_API_KEY) {
    return new Response("ANTHROPIC_API_KEY not configured", { status: 503 });
  }

  const body = (await req.json().catch(() => ({}))) as {
    question?: string;
    payload?: InsightPayload;
  };

  if (!body.payload) {
    return new Response("payload required", { status: 400 });
  }

  // Structured decision support — Answer / Why It Matters / Evidence / Action,
  // guaranteed by a typed schema (not free prose). The streamed JSON is parsed
  // progressively on the client.
  const task = `Question: ${body.question ?? ""}\n\n${ASK_INSTRUCTION}`;

  const result = streamObject({
    model: anthropic(MODEL),
    schema: askSchema,
    // Cached system + data-context prefix; only the question line varies per call.
    messages: analystMessages(buildDataContext(body.payload), task),
    temperature: 0.4,
    maxOutputTokens: 600,
  });

  return result.toTextStreamResponse();
}
