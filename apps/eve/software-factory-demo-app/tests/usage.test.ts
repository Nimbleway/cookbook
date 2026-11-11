import { generateText } from "ai";
import { describe, expect, it } from "vitest";
import { toUsageReport } from "../lib/usage";
import { scriptedModel } from "./mock";

describe("toUsageReport", () => {
  it("reports cached and reasoning tokens", async () => {
    const model = scriptedModel([{ text: "ok", input: 1000, output: 50, cacheRead: 800, reasoning: 20 }]);
    const result = await generateText({ model, prompt: "hi" });
    expect(toUsageReport(result.usage)).toEqual({
      inputTokens: 1000,
      outputTokens: 50,
      cachedInputTokens: 800,
      reasoningTokens: 20,
    });
  });
});
