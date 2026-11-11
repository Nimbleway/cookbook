import { describe, expect, it } from "vitest";
import { triageTicket } from "../lib/triage";
import { scriptedModel } from "./mock";

describe("triageTicket", () => {
  it("returns the structured triage", async () => {
    const model = scriptedModel([
      {
        text: JSON.stringify({ category: "refund", urgency: "high", summary: "Customer wants a refund for a broken dock." }),
        input: 80,
        output: 30,
      },
    ]);
    const triage = await triageTicket("My USB-C dock arrived broken, I want my money back now.", { model });
    expect(triage).toEqual({
      category: "refund",
      urgency: "high",
      summary: "Customer wants a refund for a broken dock.",
    });
  });
});
