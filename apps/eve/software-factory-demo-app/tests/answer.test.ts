import { describe, expect, it } from "vitest";
import { answerQuestion } from "../lib/answer";
import { scriptedModel } from "./mock";

describe("answerQuestion", () => {
  it("looks the order up, then answers", async () => {
    const model = scriptedModel([
      { toolCall: { toolName: "lookupOrder", input: { orderId: "A-1001" } }, input: 100, output: 10 },
      { text: "Order A-1001 has shipped.", input: 150, output: 40 },
    ]);
    const { text } = await answerQuestion("Where is order A-1001?", { model });
    expect(text).toBe("Order A-1001 has shipped.");
  });

  it("bills only the final answer step", async () => {
    const model = scriptedModel([
      { toolCall: { toolName: "lookupOrder", input: { orderId: "A-1001" } }, input: 100, output: 10 },
      { text: "Order A-1001 has shipped.", input: 150, output: 40 },
    ]);
    const { finalStepUsage } = await answerQuestion("Where is order A-1001?", { model });
    expect(finalStepUsage.inputTokens).toBe(150);
    expect(finalStepUsage.outputTokens).toBe(40);
  });
});
