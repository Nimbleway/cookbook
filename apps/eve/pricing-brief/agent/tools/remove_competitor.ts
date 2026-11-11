import { defineTool } from "eve/tools";
import { z } from "zod";
import { removeCompetitor } from "../lib/db";

export default defineTool({
  description: "Stop tracking a competitor and delete its saved snapshots.",
  inputSchema: z.object({ name: z.string().min(1) }),
  async execute({ name }) {
    return { removed: await removeCompetitor(name) };
  },
});
