import { tool, type ToolCallOptions } from "ai";
import { z } from "zod";
import { findOrder } from "./orders";

export async function lookupOrderExecute(
  { orderId }: { orderId: string },
  options: ToolCallOptions,
) {
  const order = findOrder(orderId);
  return order
    ? { found: true as const, toolCallId: options.toolCallId, ...order }
    : { found: false as const, toolCallId: options.toolCallId, orderId };
}

export const tools = {
  lookupOrder: tool({
    description: "Look up an order by its id, for example A-1001.",
    inputSchema: z.object({ orderId: z.string().describe("The order id") }),
    execute: lookupOrderExecute,
  }),
};
