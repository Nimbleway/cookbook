import type { UIMessage } from "ai";
import { beforeEach, describe, expect, it, vi } from "vitest";

const received: UIMessage[][] = [];
vi.mock("@/lib/chat", () => ({
  streamSupportReply: async (messages: UIMessage[]) => {
    received.push(messages);
    return { toUIMessageStreamResponse: () => new Response("ok") };
  },
}));

const { POST } = await import("../app/api/chat/route");

const message = (i: number): UIMessage => ({ id: `m${i}`, parts: [{ text: `q${i}`, type: "text" }], role: "user" });
const post = (body: string) => POST(new Request("http://localhost/api/chat", { body, method: "POST" }));

describe("POST /api/chat", () => {
  beforeEach(() => {
    received.length = 0;
  });

  it("answers a long history from its last 20 messages", async () => {
    const messages = Array.from({ length: 25 }, (_, i) => message(i));
    const res = await post(JSON.stringify({ messages }));
    expect(res.status).toBe(200);
    expect(received[0]?.map((m) => m.id)).toEqual(messages.slice(-20).map((m) => m.id));
  });

  it("rejects an empty history", async () => {
    expect((await post(JSON.stringify({ messages: [] }))).status).toBe(400);
  });

  it("rejects a malformed body", async () => {
    expect((await post("{not json")).status).toBe(400);
  });
});
