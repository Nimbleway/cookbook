import type { NextRequest } from "next/server";
import { anthropic } from "@ai-sdk/anthropic";
import { streamObject } from "ai";
import type { InsightPayload } from "@/lib/types";
import {
  INSIGHTS_INSTRUCTION,
  analystMessages,
  buildDataContext,
  insightsSchema,
} from "@/lib/ai-context";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Haiku 4.5 — fastest model; turning the provided data into a headline + 3
// cards is a summarization task well within it, and speed is the priority here.
const MODEL = "claude-haiku-4-5";

// Deeper structured narrative, STREAMED — the partial object streams as it's
// generated so the hero headline lands in ~1-2s. Consolidates the old summary
// call. Fired async; rule-based insights are already on screen, so it never
// blocks first paint.
export async function POST(req: NextRequest) {
  if (!process.env.ANTHROPIC_API_KEY) {
    return new Response("ANTHROPIC_API_KEY not configured", { status: 503 });
  }
  const body = (await req.json().catch(() => ({}))) as { payload?: InsightPayload };
  if (!body.payload) {
    return new Response("payload required", { status: 400 });
  }

  const result = streamObject({
    model: anthropic(MODEL),
    schema: insightsSchema,
    messages: analystMessages(buildDataContext(body.payload), INSIGHTS_INSTRUCTION),
    temperature: 0.4,
    maxOutputTokens: 700,
  });

  // Streams the accumulating JSON as text; the client parses it progressively.
  return result.toTextStreamResponse();
}
