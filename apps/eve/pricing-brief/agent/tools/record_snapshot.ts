import { defineTool } from "eve/tools";
import { z } from "zod";
import { findCompetitor, insertSnapshotIfLatest, latestSnapshot } from "../lib/db";
import { carryForward, diffPlans } from "../lib/diff";
import { normalizePlans } from "../lib/normalize";
import { planSchema } from "../lib/plans";

/**
 * The model passes what it read; application code does the rest. Prices are
 * normalized, stored and compared here, never by the model.
 */
export default defineTool({
  description:
    "Save today's read of a competitor's pricing page and compare it with the previous saved read. Pass every plan you can see on the page, as typed fields. Use null or empty lists for anything the page doesn't show; never guess. Returns the meaningful changes (empty when nothing changed) and the time of this read.",
  inputSchema: z.object({
    competitor: z.string().min(1).describe("Tracked competitor name, as returned by list_competitors."),
    source_url: z.url().describe("The URL you actually read."),
    plans: z.array(planSchema).min(1),
  }),
  async execute({ competitor, source_url, plans }) {
    const tracked = await findCompetitor(competitor);
    if (!tracked) {
      return { error: `${competitor} isn't tracked. Call add_competitor first.` };
    }
    const read = normalizePlans(plans);
    // Compare against the latest snapshot and save in one step. If an
    // overlapping check saved first, compare against its snapshot instead, so
    // a change is reported once.
    let previous = await latestSnapshot(tracked.id);
    let read_at: string | null = null;
    for (let attempt = 0; attempt < 3 && !read_at; attempt++) {
      if (attempt > 0) {
        previous = await latestSnapshot(tracked.id);
      }
      // Diff today's raw read, but store it with the last known values filled
      // in wherever today's read couldn't see a field.
      const stored = previous ? carryForward(previous.plans, read) : read;
      read_at = await insertSnapshotIfLatest(tracked.id, source_url, stored, previous?.id ?? null);
    }
    if (!read_at) {
      return { error: `Another check of ${tracked.name} is saving at the same time. Try again shortly.` };
    }

    if (!previous) {
      return { baseline: true, changes: [], competitor: tracked.name, plans: read.length, read_at, source_url };
    }
    const { changes, unknown } = diffPlans(previous.plans, read);
    if (unknown.length) {
      console.log(`[record_snapshot] ${tracked.name}: not visible on this read: ${unknown.join(", ")}`);
    }
    return {
      baseline: false,
      changes,
      competitor: tracked.name,
      previous_read_at: new Date(previous.read_at).toISOString(),
      read_at,
      source_url,
    };
  },
});
