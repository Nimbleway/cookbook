// Create the two Web Search Agents this app runs, once. Prints the IDs to put in .env.
// Creating an agent is free; research runs are what's billed.
import { createNimbleClient } from "@nimble-way/mastra";
import { DEEP_DIVE_AGENT, SWEEP_AGENT } from "../src/mastra/agents-spec";

const apiKey = process.env.NIMBLE_API_KEY;
if (!apiKey) throw new Error("Set NIMBLE_API_KEY in .env first.");
const nimble = createNimbleClient(apiKey);

for (const [envName, spec] of [
  ["NIMBLE_SWEEP_AGENT_ID", SWEEP_AGENT],
  ["NIMBLE_DEEP_DIVE_AGENT_ID", DEEP_DIVE_AGENT],
] as const) {
  const { output_schema, ...rest } = spec;
  const agent = await nimble.agents.create({ ...rest, ...(output_schema ? { output_schema } : {}) });
  console.log(`${envName}=${agent.id}`);
}
