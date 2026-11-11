import { MockLanguageModelV3 } from "ai/test";

type Step =
  | { text: string; input: number; output: number; cacheRead?: number; reasoning?: number }
  | { toolCall: { toolName: string; input: unknown }; input: number; output: number };

/** A mock model that plays back one scripted step per call. */
export function scriptedModel(steps: Step[]) {
  let call = 0;
  return new MockLanguageModelV3({
    doGenerate: async () => {
      const step = steps[Math.min(call++, steps.length - 1)]!;
      const usage = {
        inputTokens: {
          total: step.input,
          noCache: step.input - ("cacheRead" in step ? (step.cacheRead ?? 0) : 0),
          cacheRead: "cacheRead" in step ? step.cacheRead : undefined,
          cacheWrite: undefined,
        },
        outputTokens: {
          total: step.output,
          text: step.output,
          reasoning: "reasoning" in step ? step.reasoning : undefined,
        },
      };
      if ("toolCall" in step) {
        return {
          content: [
            {
              type: "tool-call" as const,
              toolCallId: `call-${call}`,
              toolName: step.toolCall.toolName,
              input: JSON.stringify(step.toolCall.input),
            },
          ],
          finishReason: { unified: "tool-calls" as const, raw: undefined },
          usage,
          warnings: [],
        };
      }
      return {
        content: [{ type: "text" as const, text: step.text }],
        finishReason: { unified: "stop" as const, raw: undefined },
        usage,
        warnings: [],
      };
    },
  });
}
