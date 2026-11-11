import type { UIMessage } from "ai";
import { streamSupportReply } from "@/lib/chat";

// Every request spends AI Gateway credits, so keep requests small. This demo
// has no auth: run it locally, or add auth before deploying it publicly.
const MAX_BODY_CHARS = 20_000;
const MAX_MESSAGES = 20;

export async function POST(req: Request) {
  const body = await req.text();
  if (body.length > MAX_BODY_CHARS) {
    return new Response("Request too large", { status: 413 });
  }
  let messages: unknown;
  try {
    ({ messages } = JSON.parse(body) as { messages?: unknown });
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  if (!Array.isArray(messages) || messages.length === 0) {
    return new Response("Send at least one message", { status: 400 });
  }
  // useChat sends the whole history on every turn: answer from the most recent part of it.
  const recent = (messages as UIMessage[]).slice(-MAX_MESSAGES);
  const result = await streamSupportReply(recent, {
    onUsage: (report) => console.log("usage", report),
  });
  return result.toUIMessageStreamResponse();
}
