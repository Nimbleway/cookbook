// Act: record events, alert Slack on the serious well-sourced ones, rebuild the digest,
// and only then mark the runs collected.
import { mkdir, writeFile } from "node:fs/promises";
import { createStep } from "@mastra/core/workflows";
import { z } from "zod";
import { config } from "../../config";
import { markCollected } from "../../lib/ledger";
import { eventsChangedOn, leadsOn, markAlerted, startFailuresOn, upsertEvent } from "../../lib/ledger-events";
import { digestMarkdown, postToSlack, shouldAlert, slackMessage } from "../../lib/notify";
import { detected } from "./detected";

export const act = createStep({
  id: "act",
  description: "Record events, alert Slack on the serious well-sourced ones, and rebuild today's digest.",
  inputSchema: detected,
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
