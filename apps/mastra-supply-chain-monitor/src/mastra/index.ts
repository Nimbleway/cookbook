import { Mastra } from "@mastra/core";
import { SimpleAuth } from "@mastra/core/server";
import { LibSQLStore } from "@mastra/libsql";
import { investigatorAgent } from "./agents/investigator";
import { triageAgent } from "./agents/triage";
import { config } from "./config";
import { apiRoutes } from "./routes";
import { collectWorkflow } from "./workflows/collect";
import { sweepWorkflow } from "./workflows/sweep";

export const mastra = new Mastra({
  agents: { triageAgent, investigatorAgent },
  workflows: { sweepWorkflow, collectWorkflow },
  // One database for Mastra's own state (workflow runs, agent memory) and the monitor's
  // ledger: a local file in development, a hosted database when deployed.
  storage: new LibSQLStore({ id: "storage", url: config.databaseUrl, authToken: config.databaseAuthToken }),
  server: {
    apiRoutes,
    // A deployed server is public. Without auth, anyone could chat with the investigator
    // and spend your Nimble and model credits. Set MONITOR_API_KEY on every deployment.
    auth: config.apiKey ? new SimpleAuth({ tokens: { [config.apiKey]: { id: "operator" } } }) : undefined,
  },
});
