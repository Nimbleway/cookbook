// Every Nimble tool this app uses, configured in one place. Everything here is developer
// configuration: which agent runs, the output schema, the source allowlist, and the effort.
// The model-facing input of these tools is only `task`, `effort`, and `runId`.
import {
  createNimbleAgentTools,
  nimbleAgentRunResultTool,
  nimbleAgentStartRunTool,
} from "@nimble-way/mastra";
import { SWEEP_OUTPUT_SCHEMA } from "./sweep-schema";
import { SWEEP_SOURCES } from "./sweep-sources";
import { config } from "./config";

// Used by the workflows, called from code. No model decides whether to start a billed run.
export const sweepStartRun = nimbleAgentStartRunTool({
  agentId: config.sweepAgentId || undefined,
  outputSchema: SWEEP_OUTPUT_SCHEMA,
  sources: SWEEP_SOURCES,
  effort: "high",
});

// No `wait`: a collect tick takes whatever is ready and leaves the rest for the next tick.
export const sweepRunResult = nimbleAgentRunResultTool({
  agentId: config.sweepAgentId || undefined,
});

// Given to the investigator agent, which decides when to start a deep dive. The model may
// pick an effort, but never above the cap. No per-run sources: the deep-dive agent reads
// the open web, guided by the prioritize/avoid rules stored on the agent.
export const deepDiveTools = createNimbleAgentTools({
  agentId: config.deepDiveAgentId || undefined,
  effortCap: "high",
});
