import { generateText, stepCountIs } from 'ai';
import { openai } from '@ai-sdk/openai';
import { openrouter } from '@openrouter/ai-sdk-provider';
import type {
  NimbleAgentRunResultOutput,
  NimbleAgentRunStatusOutput,
  NimbleAgentStartRunOutput,
} from '@nimble-way/ai-sdk';
import { nimbleResearchTools, runTool } from './nimble-tools';

export type PatentCliffRunResult = NimbleAgentRunResultOutput;

/**
 * Nimble does the research. The model provider only invokes the connector
 * tool, so it can be the cheapest thing that reliably emits one tool call.
 *
 * Both halves are configuration, set in .env.local (or .env):
 *
 *   RESEARCH_PROVIDER   openrouter | openai | gateway
 *   RESEARCH_MODEL      a model id valid for that provider
 *
 * Leave `RESEARCH_PROVIDER` unset and the first provider with a usable API key
 * wins, in the order below. Leave `RESEARCH_MODEL` unset and the provider's
 * default applies. Whatever you pick must support tool calling: the start step
 * is a forced tool call, and a model without tool support cannot run it.
 */
const PROVIDERS = {
  openrouter: {
    keyName: 'OPENROUTER_API_KEY',
    // Free tier, and it advertises tools + tool_choice support on OpenRouter.
    defaultModel: 'google/gemma-4-31b-it:free',
    build: (id: string) => openrouter(id),
    // The model has one job: emit a single tool call. Reasoning tokens are
    // pure cost here, so they are turned down on whichever provider is used.
    options: { openrouter: { reasoning: { effort: 'minimal' } } },
  },
  gateway: {
    keyName: 'AI_GATEWAY_API_KEY',
    defaultModel: 'openai/gpt-5-nano',
    // A plain `provider/model` string routes through the Vercel AI Gateway.
    build: (id: string) => id,
    options: { openai: { reasoningEffort: 'minimal', textVerbosity: 'low' } },
  },
  openai: {
    keyName: 'OPENAI_API_KEY',
    defaultModel: 'gpt-5-nano',
    build: (id: string) => openai(id),
    options: { openai: { reasoningEffort: 'minimal', textVerbosity: 'low' } },
  },
} as const;

type ProviderName = keyof typeof PROVIDERS;

/**
 * A local misconfiguration, as opposed to an upstream failure. Carried as a
 * type rather than a message prefix so the API route can classify it without
 * pattern-matching on prose that anyone might later reword.
 */
export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigurationError';
  }
}

const PROVIDER_ORDER: ProviderName[] = ['openrouter', 'gateway', 'openai'];

const PLACEHOLDER_KEYS = new Set([
  'your_openai_api_key_here',
  'your_openrouter_api_key_here',
  'your_ai_gateway_api_key_here',
]);

function hasKey(name: ProviderName) {
  const value = process.env[PROVIDERS[name].keyName]?.trim();
  return Boolean(value) && !PLACEHOLDER_KEYS.has(value as string);
}

function configuredProvider(): ProviderName | undefined {
  const requested = process.env.RESEARCH_PROVIDER?.trim().toLowerCase();

  if (requested) {
    if (!(requested in PROVIDERS)) {
      throw new ConfigurationError(
        `Unknown RESEARCH_PROVIDER "${requested}". Use one of: ${Object.keys(PROVIDERS).join(', ')}.`
      );
    }
    // An explicit choice is never silently swapped for a different provider.
    return hasKey(requested as ProviderName) ? (requested as ProviderName) : undefined;
  }

  return PROVIDER_ORDER.find(hasKey);
}

function missingProviderMessage() {
  const requested = process.env.RESEARCH_PROVIDER?.trim().toLowerCase();
  if (requested && requested in PROVIDERS) {
    return `Missing ${PROVIDERS[requested as ProviderName].keyName}, required by RESEARCH_PROVIDER=${requested}. Add it to .env.local (or .env) before starting research.`;
  }
  return (
    'Missing a model provider key. Set OPENROUTER_API_KEY, AI_GATEWAY_API_KEY, or OPENAI_API_KEY ' +
    'in .env.local (or .env) before starting research.'
  );
}

/** The model and its cost-trimming options, for whichever provider is configured. */
function researchModel() {
  const name = configuredProvider();
  if (!name) throw new ConfigurationError(missingProviderMessage());

  const provider = PROVIDERS[name];
  return {
    model: provider.build(process.env.RESEARCH_MODEL?.trim() || provider.defaultModel),
    providerOptions: provider.options,
  };
}

type ConfigRequirement = 'nimble' | 'nimble+model';

function requireConfiguration(requirement: ConfigRequirement = 'nimble') {
  const required: Array<readonly [string, string | undefined, string]> = [
    ['NIMBLE_API_KEY', process.env.NIMBLE_API_KEY, 'your_nimble_api_key_here'],
    ['NIMBLE_AGENT_ID', process.env.NIMBLE_AGENT_ID, 'wsa_your_agent_id_here'],
  ];

  for (const [name, value, placeholder] of required) {
    if (!value || value === placeholder) {
      throw new ConfigurationError(
        `Missing ${name}. Add it to .env.local (or .env) before starting research.`
      );
    }
  }

  // Only starting a run goes through the model. Reading a run back does not,
  // so a missing model-provider key must not block someone resuming a report.
  if (requirement === 'nimble+model' && !configuredProvider()) {
    throw new ConfigurationError(missingProviderMessage());
  }
}

function toolOutput<T>(steps: Array<{ toolResults: Array<{ toolName: string; output: unknown }> }>, name: string) {
  const output = steps.flatMap(step => step.toolResults).find(result => result.toolName === name)?.output;
  if (!output) throw new Error(`The Vercel AI SDK agent did not call ${name}.`);
  return output as T;
}

/**
 * Surface a local misconfiguration verbatim, because the reader can act on it.
 * Anything else is an upstream failure and gets the caller's generic message.
 */
export function researchErrorMessage(error: unknown, fallback: string) {
  return error instanceof ConfigurationError ? error.message : fallback;
}

/**
 * Start a Nimble run through its Vercel AI SDK tool connector.
 *
 * This is the one step that runs a model: a Vercel AI SDK agent decides to
 * begin research and calls `nimbleAgentStartRun()`. `toolChoice` pins it to
 * that tool and `stepCountIs(1)` stops the loop as soon as the run handle
 * comes back, so a report costs exactly one model call.
 */
export async function startPatentCliffPhase(task: string) {
  requireConfiguration('nimble+model');
  const tools = nimbleResearchTools();
  const { steps } = await generateText({
    ...researchModel(),
    prompt:
      'Start deep research for this patent-cliff brief. Call the startResearch tool exactly once, ' +
      'set effort to high, and pass the brief below through as the task verbatim. Do not summarise ' +
      'it, reorder it, or drop any drug from the list.\n\n' +
      task,
    tools,
    toolChoice: { type: 'tool', toolName: 'startResearch' },
    stopWhen: stepCountIs(1),
  });
  const run = toolOutput<NimbleAgentStartRunOutput>(steps, 'startResearch');

  return {
    text: 'Research is underway. This report can take several minutes; this page will check for the cited result automatically.',
    runId: run.runId,
    agentId: run.agentId,
    effort: run.effort,
    status: run.status,
  };
}

/**
 * Retrieve a run through the Nimble Vercel AI SDK result tool.
 *
 * Called on every poll, so it invokes the connector tool directly rather than
 * through `generateText()`. See `runTool()` for why.
 */
export async function resumePatentCliffPhase(
  runId: string,
  options: { abortSignal?: AbortSignal } = {}
): Promise<{ text: string; result: PatentCliffRunResult }> {
  requireConfiguration();
  const { getResearchResult } = nimbleResearchTools();
  const result = await runTool(getResearchResult, { runId }, options);

  if (!result.ready) {
    return { text: `Research is ${result.status}. The cited report will appear here when Nimble completes the run.`, result };
  }

  const text = result.output.type === 'text'
    ? result.output.text
    : JSON.stringify(result.output.json, null, 2);
  return { text, result };
}

/** Lightweight status check through the connector's status tool. */
export async function checkRunStatus(
  runId: string,
  options: { abortSignal?: AbortSignal } = {}
): Promise<NimbleAgentRunStatusOutput> {
  requireConfiguration();
  const { checkResearch } = nimbleResearchTools();
  return runTool(checkResearch, { runId }, options);
}
