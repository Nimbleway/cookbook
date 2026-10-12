// Collect: pick up every finished sweep run, find what's new, triage it, and act.
// It needs nothing from the process that started the runs: the runIds are in the ledger.
// Runs still working are left for the next tick.
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { NimbleAgentRunError } from "@nimble-way/mastra";
import { z } from "zod";
import { triageSchema } from "../agents/triage";
import { config } from "../config";
import {
  diffAgainst,
  eventsFromResult,
  mergeAcrossProducts,
  mergeInto,
  type CompletedResult,
  type MonitoredEvent,
} from "../lib/events";
import {
  eventsChangedOn,
  leadsOn,
  claimRun,
  collectableRuns,
  markAlerted,
  markCollected,
  markFailed,
  releaseRun,
  saveRaw,
  recentEvents,
  recordLeads,
  startFailuresOn,
  upsertEvent,
} from "../lib/ledger";
import { digestMarkdown, postToSlack, shouldAlert, slackMessage } from "../lib/notify";
import { sweepRunResult } from "../nimble";
import { WATCHLIST } from "../watchlist";

// Workflow steps pass these between them; the shapes are validated in lib/events.ts.
const eventList = z.array(z.custom<MonitoredEvent>());
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
  outputSchema: z.object({
    candidates: eventList,
    repeats: eventList,
    known: eventList,
    runIds: z.array(z.string()),
    stillRunning: z.number(),
    failed: z.number(),
    collected: z.number(),
  }),
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

type Assessment = z.infer<typeof triageSchema>["assessments"][number];

async function cachedTriage(): Promise<Record<string, Assessment>> {
  try {
    return JSON.parse(await readFile(`${config.dataDir}/samples/triage.json`, "utf8"));
  } catch {
    return {};
  }
}

const triageEvents = createStep({
  id: "triage-events",
  description: "Score each new or changed event against the watchlist.",
  inputSchema: detectEvents.outputSchema,
  outputSchema: detectEvents.outputSchema,
  execute: async ({ inputData, mastra }) => {
    if (!inputData.candidates.length) return inputData;

    // Demo mode reuses saved assessments when they exist, so a recording never depends on
    // a live model call. Anything not in the cache is triaged live.
    const cache = config.useLive ? {} : await cachedTriage();
    const uncached = inputData.candidates.filter((c) => !cache[c.eventKey]);
    const assessments: Record<string, Assessment> = { ...cache };

    if (uncached.length) {
      const prompt = JSON.stringify(
        {
          WATCHLIST: WATCHLIST,
          CANDIDATES: uncached.map(({ citations, runIds, triage, ...e }) => e),
          KNOWN: inputData.known.map((e) => ({
            eventKey: e.eventKey,
            headline: e.headline,
            location: e.location,
            eventDate: e.eventDate,
            status: e.status,
          })),
        },
        null,
        2,
      );
      try {
        const res = await mastra!.getAgent("triageAgent").generate(prompt, {
          structuredOutput: { schema: triageSchema },
        });
        for (const a of res.object?.assessments ?? []) assessments[a.eventKey] = a;
      } catch (err) {
        // The runs are already collected, so failing here would lose their events. Record
        // them untriaged instead: they reach the digest, never Slack.
        console.warn("triage failed; recording events untriaged:", err instanceof Error ? err.message : err);
      }
    }

    const slugs = new Set(WATCHLIST.map((p) => p.slug));
    const candidates: MonitoredEvent[] = [];
    const repeats = [...inputData.repeats];
    for (const e of inputData.candidates) {
      const a = assessments[e.eventKey];
      if (!a) {
        candidates.push(e); // untriaged: still recorded, never alerted
        continue;
      }
      const prior = a.duplicateOf ? inputData.known.find((k) => k.eventKey === a.duplicateOf) : undefined;
      if (prior && !e.previousStatus) {
        repeats.push(mergeInto(prior, e)); // a near-duplicate the deterministic match missed
        continue;
      }
      candidates.push({
        ...e,
        products: [...new Set([...e.products, ...a.affectedProducts.filter((s) => slugs.has(s))])],
        triage: { severity: a.severity, rationale: a.rationale, recommendedAction: a.recommendedAction },
      });
    }
    return { ...inputData, candidates, repeats };
  },
});

const act = createStep({
  id: "act",
  description: "Record events, alert Slack on the serious well-sourced ones, and rebuild today's digest.",
  inputSchema: detectEvents.outputSchema,
  outputSchema: z.object({
    collected: z.number(),
    stillRunning: z.number(),
    failed: z.number(),
    newEvents: z.number(),
    updates: z.number(),
    alerted: z.array(z.string()),
    digestPath: z.string().nullable(),
  }),
  execute: async ({ inputData }) => {
    for (const e of inputData.repeats) await upsertEvent(e, false);
    for (const e of inputData.candidates) await upsertEvent(e, true);

    // Alert every serious event not yet alerted at its current status, repeats included: an
    // escalation alerts again, and if a Slack post failed on an earlier pass, the event comes
    // back as a repeat and gets the alert now.
    //
    // Delivery is at least once by design. If the process dies after Slack accepts a post but
    // before markAlerted records it, the alert repeats on a later pass. Recording first would
    // turn that same crash into a lost alert, which is the worse failure for a risk monitor.
    const alerted: string[] = [];
    for (const e of [...inputData.candidates, ...inputData.repeats]) {
      if (shouldAlert(e) && e.alertedStatus !== e.status) {
        await postToSlack(slackMessage(e));
        await markAlerted(e.eventKey, e.status);
        alerted.push(e.headline);
      }
    }

    // Only now are the runs done: their events are recorded and alerts sent. If anything
    // above failed, the runs stay claimed and a later tick processes them again.
    await markCollected(inputData.runIds);

    // The digest is rebuilt from the ledger on every pass, so it always covers the whole day.
    const date = new Date().toISOString().slice(0, 10);
    const markdown = digestMarkdown({
      date,
      events: await eventsChangedOn(date),
      leads: await leadsOn(date),
      startFailures: await startFailuresOn(date),
    });
    let digestPath: string | null = null;
    try {
      await mkdir(`${config.dataDir}/digests`, { recursive: true });
      digestPath = `${config.dataDir}/digests/${date}.md`;
      await writeFile(digestPath, markdown);
    } catch {
      // Read-only or ephemeral filesystem when deployed: GET /digest serves it from the ledger.
    }

    return {
      collected: inputData.collected,
      stillRunning: inputData.stillRunning,
      failed: inputData.failed,
      newEvents: inputData.candidates.filter((e) => !e.previousStatus).length,
      updates: inputData.candidates.filter((e) => e.previousStatus).length,
      alerted,
      digestPath,
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
