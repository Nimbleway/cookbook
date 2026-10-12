// The agent a person talks to in Mastra Studio. It answers from what the monitor has
// already found, and starts a Nimble deep dive when a question needs fresh research.
import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { Memory } from "@mastra/memory";
import { z } from "zod";
import { config } from "../config";
import { recentEvents, recentRuns } from "../lib/ledger";
import { deepDiveTools } from "../nimble";
import { WATCHLIST } from "../watchlist";

const listMonitoredEvents = createTool({
  id: "list-monitored-events",
  description:
    "Events the scheduled monitor has already found, newest first, with severity, products, " +
    "status, and source URLs. Costs nothing: use this before starting any research.",
  inputSchema: z.object({
    days: z.number().int().min(1).max(60).default(14),
    product: z.string().optional().describe("A product slug to filter on: laptop, earbuds, or smartwatch."),
  }),
  execute: async ({ days, product }) => {
    const events = await recentEvents(days);
    return events
      .filter((e) => !product || e.products.includes(product))
      .map((e) => ({
        eventKey: e.eventKey,
        headline: e.headline,
        severity: e.triage?.severity ?? "untriaged",
        products: e.products,
        location: e.location,
        eventDate: e.eventDate,
        status: e.status,
        confidence: e.confidence,
        sources: e.citations.map((c) => c.url),
      }));
  },
});

const getWatchlist = createTool({
  id: "get-watchlist",
  description: "The monitored products and the exposures (suppliers, materials, sites, lanes) behind each.",
  inputSchema: z.object({}),
  execute: async () => WATCHLIST,
});

const listMonitorRuns = createTool({
  id: "list-monitor-runs",
  description: "The scheduled sweep runs: when they started, for which product, and whether they were collected.",
  inputSchema: z.object({ limit: z.number().int().min(1).max(50).default(10) }),
  execute: async ({ limit }) => recentRuns(limit),
});

export const investigatorAgent = new Agent({
  id: "investigator",
  name: "Supply chain investigator",
  description: "Answers questions about detected supply chain events and runs Nimble deep dives on them.",
  model: config.model,
  memory: new Memory(),
  tools: {
    listMonitoredEvents,
    getWatchlist,
    listMonitorRuns,
    ...deepDiveTools,
  },
  instructions: `You help a sourcing team understand supply chain events that may affect their products.

Answer from list-monitored-events and get-watchlist first. They cost nothing and cover what the
scheduled monitor has already found.

Start a Nimble run (nimble-agent-start-run) only when the user asks for a deep dive, or when the
question needs research the monitor has not done. Write the task as: the event, its source URL if
known, and the exposures it may touch. Tell the user the runId and that the research takes
several minutes. When they ask for the answer, fetch the result by runId.

If the result is not ready, say so and keep the runId. Never start a second run for a task that
already has a runId. If starting a run fails without returning a runId, report the failure and
stop. Do not try again.

When you present a finished deep dive, cite sources only from the run's trust data. Never present
a URL you wrote yourself as a citation.`,
});
