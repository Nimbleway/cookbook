import type { LanguageModelUsage } from "ai";

export type UsageReport = {
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens: number;
  reasoningTokens: number;
};

/** Flattens the SDK's usage record for the cost log. */
export function toUsageReport(usage: LanguageModelUsage): UsageReport {
  return {
    inputTokens: usage.inputTokens ?? 0,
    outputTokens: usage.outputTokens ?? 0,
    cachedInputTokens: usage.cachedInputTokens ?? 0,
    reasoningTokens: usage.reasoningTokens ?? 0,
  };
}
