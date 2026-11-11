import { defineTool } from "eve/tools";
import { z } from "zod";
import { findCompetitor, insertSnapshot, latestSnapshot } from "../lib/db";
import { diffPlans } from "../lib/diff";
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
    const normalized = normalizePlans(plans);
    const previous = await latestSnapshot(tracked.id);
    const read_at = await insertSnapshot(tracked.id, source_url, normalized);

    if (!previous) {
      return { baseline: true, changes: [], competitor: tracked.name, plans: normalized.length, read_at, source_url };
    }
    const { changes, unknown } = diffPlans(previous.plans, normalized);
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
