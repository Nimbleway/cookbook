import { defineTool } from "eve/tools";
import { z } from "zod";
import { upsertCompetitor } from "../lib/db";

export default defineTool({
  description:
    "Start tracking a competitor's pricing page, or update its URL if the competitor is already tracked. Pass the official pricing page URL you found with nimble__search. After adding, read the page and call record_snapshot to save the baseline.",
  inputSchema: z.object({
    name: z.string().min(1).describe("Competitor name, e.g. 'Postmark'."),
    pricing_url: z.url().describe("The competitor's official pricing page URL."),
  }),
  async execute({ name, pricing_url }) {
    const competitor = await upsertCompetitor(name.trim(), pricing_url);
    return { competitor, next: "Read the page with nimble__extract, then call record_snapshot to save the baseline." };
  },
});
