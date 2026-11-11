import { generateText, Output, type LanguageModel } from "ai";
import { z } from "zod";
import { MODEL } from "./model";

export const triageSchema = z.object({
  category: z.enum(["order-status", "refund", "product-question", "other"]),
  urgency: z.enum(["low", "normal", "high"]),
  summary: z.string(),
});

export type Triage = z.infer<typeof triageSchema>;

/** Classifies an incoming support ticket for the queue. */
export async function triageTicket(
  ticket: string,
  options: { model?: LanguageModel } = {},
): Promise<Triage> {
  const result = await generateText({
    model: options.model ?? MODEL,
    system: "Classify the support ticket. Summarize it in one sentence.",
    prompt: ticket,
    experimental_output: Output.object({ schema: triageSchema }),
  });
  return result.experimental_output;
}
