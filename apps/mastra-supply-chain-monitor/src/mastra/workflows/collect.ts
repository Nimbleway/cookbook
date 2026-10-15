// Collect: pick up every finished sweep run, find what's new, triage it, and act.
// It needs nothing from the process that started the runs: the runIds are in the ledger.
// Runs still working are left for the next tick.
import { readFile } from "node:fs/promises";
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { NimbleAgentRunError } from "@nimble-way/mastra";
import { z } from "zod";
import { config } from "../config";
import { diffAgainst, mergeAcrossProducts } from "../lib/dedupe";
import { eventsFromResult, type CompletedResult, type MonitoredEvent } from "../lib/events";
import { claimRun, collectableRuns, markFailed, releaseRun, saveRaw } from "../lib/ledger";
import { recentEvents, recordLeads } from "../lib/ledger-events";
import { sweepRunResult } from "../nimble";
import { act } from "./steps/act";
import { detected } from "./steps/detected";
import { triageEvents } from "./steps/triage";

// The shapes are validated in lib/events.ts; the workflow only passes them along.
const completedList = z.array(z.object({ product: z.string(), result: z.custom<CompletedResult>() }));

// Demo mode replays real results saved from earlier live runs.
async function sampleResult(product: string, runId: string): Promise<CompletedResult> {
  try {
    const saved = JSON.parse(await readFile(`${config.dataDir}/samples/sweep_${product}.json`, "utf8"));
    return { ...saved, runId };
  } catch {
    console.warn(`demo: no saved result for ${product} (${config.dataDir}/samples/sweep_${product}.json); treating as no events`);
    return { ready: true, runId, output: { type: "json", json: { events: [], unverified: [] } } };
  }
}

const fetchResults = createStep({
  id: "fetch-results",
  description: "Claim each collectable run, fetch it if finished, and save the raw result before touching it.",
  inputSchema: z.object({}),
  outputSchema: z.object({ completed: completedList, stillRunning: z.number(), failed: z.number() }),
  execute: async () => {
    const completed: Array<{ product: string; result: CompletedResult }> = [];
    let stillRunning = 0;
    let failed = 0;

    for (const run of await collectableRuns()) {
      // Another collect tick may be running at the same time. Whoever claims a run owns it.
      if (!(await claimRun(run.runId))) continue;

      if (run.runId.startsWith("sample-")) {
        const result = await sampleResult(run.product, run.runId);
        await saveRaw(run.runId, result);
        completed.push({ product: run.product, result });
        continue;
      }
      try {
        const result = (await sweepRunResult.execute!({ runId: run.runId }, {} as never)) as
          | CompletedResult
          | { ready: false };
        // Branch on `ready`, never on `status`: a not-ready payload can carry any status.
        if (!result.ready) {
          await releaseRun(run.runId);
          stillRunning++;
          continue;
        }
        await saveRaw(run.runId, result);
        completed.push({ product: run.product, result });
      } catch (err) {
        // A run that failed or was cancelled server-side. It is recorded, not restarted:
        // a restart would be a new billed run, and the next sweep covers the window anyway.
        if (err instanceof NimbleAgentRunError && (err.reason === "failed" || err.reason === "cancelled")) {
          await markFailed(run.runId, err.message);
          failed++;
        } else {
          // Network trouble or similar: hand it back and try again next tick.
          console.warn(`collect: could not read ${run.runId}:`, err instanceof Error ? err.message : err);
          await releaseRun(run.runId);
          stillRunning++;
        }
      }
    }
    return { completed, stillRunning, failed };
  },
});

const detectEvents = createStep({
  id: "detect-events",
  description: "Turn results into events, merge the same event across products, and diff against the ledger.",
  inputSchema: fetchResults.outputSchema,
  outputSchema: detected,
  execute: async ({ inputData }) => {
    const found: MonitoredEvent[] = [];
    for (const { product, result } of inputData.completed) {
      const { events, leads } = eventsFromResult(result, product);
      await recordLeads(result.runId, product, leads);
      found.push(...events);
    }
    const known = await recentEvents(14);
    const diff = diffAgainst(known, mergeAcrossProducts(found));
    return {
      candidates: [...diff.fresh, ...diff.updates],
      repeats: diff.repeats,
      known,
      runIds: inputData.completed.map((c) => c.result.runId),
      stillRunning: inputData.stillRunning,
      failed: inputData.failed,
      collected: inputData.completed.length,
    };
  },
});

export const collectWorkflow = createWorkflow({
  id: "collect",
  description: "Collect finished research runs, detect new supply chain events, triage, and alert.",
  inputSchema: z.object({}),
  outputSchema: act.outputSchema,
})
  .then(fetchResults)
  .then(detectEvents)
  .then(triageEvents)
  .then(act)
  .commit();
