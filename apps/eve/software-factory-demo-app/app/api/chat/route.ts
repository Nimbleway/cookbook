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
  const { messages }: { messages: UIMessage[] } = JSON.parse(body);
  if (!Array.isArray(messages) || messages.length === 0 || messages.length > MAX_MESSAGES) {
    return new Response(`Send between 1 and ${MAX_MESSAGES} messages`, { status: 400 });
  }
  const result = await streamSupportReply(messages, {
    onUsage: (report) => console.log("usage", report),
  });
  return result.toUIMessageStreamResponse();
}
