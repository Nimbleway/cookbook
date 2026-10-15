// Triage: a Mastra agent scores new and changed events against the watchlist. A model
// failure never loses events: they're recorded untriaged and scored again next time.
import { readFile } from "node:fs/promises";
import { createStep } from "@mastra/core/workflows";
import type { z } from "zod";
import { triageSchema } from "../../agents/triage";
import { config } from "../../config";
import { mergeInto } from "../../lib/dedupe";
import type { MonitoredEvent } from "../../lib/events";
import { WATCHLIST } from "../../watchlist";
import { detected } from "./detected";

type Assessment = z.infer<typeof triageSchema>["assessments"][number];

async function cachedTriage(): Promise<Record<string, Assessment>> {
  try {
    return JSON.parse(await readFile(`${config.dataDir}/samples/triage.json`, "utf8"));
  } catch {
    return {};
  }
}

export const triageEvents = createStep({
  id: "triage-events",
  description: "Score each new or changed event against the watchlist.",
  inputSchema: detected,
  outputSchema: detected,
  execute: async ({ inputData, mastra }) => {
    // A repeat with no triage was recorded while the model call failed. Score it now, or it
    // could never alert.
    const toScore = [...inputData.candidates, ...inputData.repeats.filter((e) => !e.triage)];
    if (!toScore.length) return inputData;

    // Demo mode reuses saved assessments when they exist, so a recording never depends on
    // a live model call. Anything not in the cache is triaged live.
    const cache = config.useLive ? {} : await cachedTriage();
    const uncached = toScore.filter((c) => !cache[c.eventKey]);
    const assessments: Record<string, Assessment> = { ...cache };

    if (uncached.length) {
      const prompt = JSON.stringify(
        {
          WATCHLIST: WATCHLIST,
          CANDIDATES: uncached.map(({ citations, runIds, triage, ...e }) => e),
          // A repeat being scored again is a candidate here, not a known event to match.
          KNOWN: inputData.known.filter((k) => !uncached.some((c) => c.eventKey === k.eventKey)).map((e) => ({
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
    const withAssessment = (e: MonitoredEvent, a: Assessment): MonitoredEvent => ({
      ...e,
      products: [...new Set([...e.products, ...a.affectedProducts.filter((s) => slugs.has(s))])],
      triage: { severity: a.severity, rationale: a.rationale, recommendedAction: a.recommendedAction },
    });

    const candidates: MonitoredEvent[] = [];
    const repeats = inputData.repeats.map((e) => (!e.triage && assessments[e.eventKey] ? withAssessment(e, assessments[e.eventKey]) : e));
    for (const e of inputData.candidates) {
      const a = assessments[e.eventKey];
      if (!a) {
        candidates.push(e); // untriaged: still recorded, never alerted; scored again next time it's seen
        continue;
      }
      const prior = a.duplicateOf ? inputData.known.find((k) => k.eventKey === a.duplicateOf) : undefined;
      if (prior && !e.previousStatus) {
        repeats.push(mergeInto(prior, e)); // a near-duplicate the deterministic match missed
        continue;
      }
      candidates.push(withAssessment(e, a));
    }
    return { ...inputData, candidates, repeats };
  },
});
