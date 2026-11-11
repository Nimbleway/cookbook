import { describe, expect, it } from "vitest";
import { lookupOrderExecute } from "../lib/tools";

const options = { toolCallId: "call-1", messages: [] };

describe("lookupOrder", () => {
  it("finds a known order", async () => {
    const result = await lookupOrderExecute({ orderId: "a-1002" }, options);
    expect(result).toMatchObject({ found: true, status: "processing", item: "USB-C dock" });
  });

  it("reports an unknown order", async () => {
    const result = await lookupOrderExecute({ orderId: "Z-9" }, options);
    expect(result).toMatchObject({ found: false, orderId: "Z-9" });
  });
});
