import { generateText, stepCountIs, type LanguageModel } from "ai";
import { MODEL } from "./model";
import { tools } from "./tools";
import { toUsageReport, type UsageReport } from "./usage";

/**
 * Answers one question, possibly after looking an order up, and reports the
 * tokens spent on the final answer step (what the support dashboard bills).
 */
export async function answerQuestion(
  question: string,
  options: { model?: LanguageModel } = {},
): Promise<{ text: string; finalStepUsage: UsageReport }> {
  const result = await generateText({
    model: options.model ?? MODEL,
    system: "Answer the customer's question. Look orders up when they mention one.",
    prompt: question,
    tools,
    stopWhen: stepCountIs(5),
  });
  return { text: result.text, finalStepUsage: toUsageReport(result.usage) };
}
