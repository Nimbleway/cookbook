import type { Tool } from 'ai';
import {
  nimbleAgentRunResult,
  nimbleAgentRunStatus,
  nimbleAgentStartRun,
} from '@nimble-way/ai-sdk';

/**
 * Nimble's Vercel AI SDK connector exposes the three asynchronous research
 * operations as AI SDK tools. Credentials and agent selection stay server-side.
 */
export function nimbleResearchTools() {
  return {
    startResearch: nimbleAgentStartRun({ effort: 'high', effortCap: 'high' }),
    checkResearch: nimbleAgentRunStatus(),
    getResearchResult: nimbleAgentRunResult(),
  };
}

/**
 * Execute a connector tool directly, without a model in the loop.
 *
 * The start-run step goes through `generateText()` because deciding to begin
 * research is a model decision. Reading back a run is not: the run ID is
 * already known, so polling it through an LLM would add a model call every
 * five seconds for the whole 5-15 minute research job and let the model
 * restate a result Nimble already returned verbatim. These are the same AI SDK
 * `Tool` objects either way, so the connector stays the only path to Nimble.
 */
export async function runTool<INPUT, OUTPUT>(
  tool: Tool<INPUT, OUTPUT>,
  input: INPUT,
  options: { abortSignal?: AbortSignal } = {}
): Promise<OUTPUT> {
  if (typeof tool.execute !== 'function') {
    throw new Error('The Nimble connector tool is missing its execute implementation.');
  }

  const output = await tool.execute(input, {
    toolCallId: 'nimble-direct-invocation',
    messages: [],
    abortSignal: options.abortSignal,
  });

  return output as OUTPUT;
}
