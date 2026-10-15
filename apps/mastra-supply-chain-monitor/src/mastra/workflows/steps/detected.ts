// What detect-events hands to the triage and act steps.
import { z } from "zod";
import type { MonitoredEvent } from "../../lib/events";

// The shapes are validated in lib/events.ts; the workflow only passes them along.
export const eventList = z.array(z.custom<MonitoredEvent>());

export const detected = z.object({
  candidates: eventList, // new, or a status change: these get triaged
  repeats: eventList, // seen before with nothing new
  known: eventList, // the ledger's recent events, for near-duplicate matching
  runIds: z.array(z.string()),
  stillRunning: z.number(),
  failed: z.number(),
  collected: z.number(),
});
