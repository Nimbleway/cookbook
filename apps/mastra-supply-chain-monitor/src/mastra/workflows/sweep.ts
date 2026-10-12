// Sweep: start one Nimble research run per product and record its runId. Nothing here
// waits for research. A high-effort run takes minutes, so the sweep returns in seconds and
// the collect workflow picks the results up on a later tick, from whatever process is
// running then.
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { NimbleAgentRunError } from "@nimble-way/mastra";
import { z } from "zod";
import { config } from "../config";
import {
  lastSweepStartedAt,
  lastWindowEnd,
  recentEvents,
  recordRunStarted,
  recordStartFailure,
  recordSweep,
} from "../lib/ledger";
import { sweepStartRun } from "../nimble";
import { WATCHLIST, type Product } from "../watchlist";

const isoDate = (d: Date) => d.toISOString().slice(0, 10);
const DAY = 86_400_000;

const taskSchema = z.object({
  product: z.string(),
  windowStart: z.string(),
  windowEnd: z.string(),
  task: z.string(),
});

// The task text the sweep agent receives. Exposures go in verbatim, so the agent can copy
// them back into `affected_exposures`, and known events go in so it reports a status
// change instead of the same event again.
function buildTask(product: Product, windowStart: string, windowEnd: string, known: string[]): string {
  const lines = [
    `Product: ${product.name}.`,
    `Window: ${windowStart} to ${windowEnd}.`,
    `Exposures: ${product.exposures.map((e) => e.name).join("; ")}.`,
  ];
  if (known.length) {
    lines.push(
      "Known events (already reported; include one only if its status has changed, and say so in the summary):",
      ...known.map((k) => `- ${k}`),
    );
  }
  return lines.join("\n");
}

const planSweep = createStep({
  id: "plan-sweep",
  description: "Refuse if a sweep ran recently; otherwise build one research task per product.",
  inputSchema: z.object({ force: z.boolean().default(false) }),
  outputSchema: z.object({ refused: z.string().nullable(), tasks: z.array(taskSchema) }),
  execute: async ({ inputData }) => {
    const last = await lastSweepStartedAt();
    const minutesSince = last ? (Date.now() - Date.parse(last)) / 60_000 : Infinity;
    if (!inputData.force && minutesSince < config.minMinutesBetweenSweeps) {
      return {
        refused: `Last sweep started ${Math.round(minutesSince)} min ago; minimum gap is ${config.minMinutesBetweenSweeps} min.`,
        tasks: [],
      };
    }
    await recordSweep(config.useLive);

    const today = isoDate(new Date());
    const known = await recentEvents(14);
    const tasks = await Promise.all(
      WATCHLIST.map(async (product) => {
        // Pick up where the last research window ended, with a day of overlap: articles
        // carry dates, not times. The first sweep builds a baseline.
        const prevEnd = await lastWindowEnd(product.slug);
        const windowStart = prevEnd
          ? isoDate(new Date(Date.parse(prevEnd) - DAY))
          : isoDate(new Date(Date.now() - config.firstLookbackDays * DAY));
        const knownForProduct = known
          .filter((e) => e.products.includes(product.slug))
          .slice(0, 15)
          .map((e) => `${e.headline} (${e.eventDate}, ${e.status})`);
        return {
          product: product.slug,
          windowStart,
          windowEnd: today,
          task: buildTask(product, windowStart, today, knownForProduct),
        };
      }),
    );
    return { refused: null, tasks };
  },
});

const startRuns = createStep({
  id: "start-runs",
  description: "Start one Nimble Web Search Agent run per task and record each runId.",
  inputSchema: planSweep.outputSchema,
  outputSchema: z.object({
    refused: z.string().nullable(),
    started: z.array(z.object({ product: z.string(), runId: z.string() })),
    failed: z.array(z.object({ product: z.string(), createOutcome: z.string(), message: z.string() })),
  }),
  execute: async ({ inputData }) => {
    const started: Array<{ product: string; runId: string }> = [];
    const failed: Array<{ product: string; createOutcome: string; message: string }> = [];

    for (const t of inputData.tasks) {
      const startedAt = new Date().toISOString();

      if (!config.useLive) {
        // Demo mode: no billed run. The collector replays a saved real result instead.
        const runId = `sample-${t.product}-${startedAt}`;
        await recordRunStarted({ runId, product: t.product, windowStart: t.windowStart, windowEnd: t.windowEnd, startedAt });
        started.push({ product: t.product, runId });
        continue;
      }

      try {
        const run = await sweepStartRun.execute!({ task: t.task }, {} as never);
        const runId = (run as { runId: string }).runId;
        await recordRunStarted({ runId, product: t.product, windowStart: t.windowStart, windowEnd: t.windowEnd, startedAt });
        started.push({ product: t.product, runId });
      } catch (err) {
        // Run creation is billed and is sent exactly once. "not-created" means no run
        // exists. "unknown" means one might: it is recorded for a human to reconcile in the
        // Nimble dashboard and is never retried here.
        const outcome = err instanceof NimbleAgentRunError ? (err.createOutcome ?? err.reason) : "error";
        const message = err instanceof Error ? err.message : String(err);
        await recordStartFailure(t.product, outcome, message);
        failed.push({ product: t.product, createOutcome: outcome, message });
      }
    }
    return { refused: inputData.refused, started, failed };
  },
});

export const sweepWorkflow = createWorkflow({
  id: "sweep",
  description: "Start one supply chain research run per watched product.",
  inputSchema: z.object({ force: z.boolean().default(false) }),
  outputSchema: startRuns.outputSchema,
})
  .then(planSweep)
  .then(startRuns)
  .commit();
