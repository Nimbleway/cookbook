import { defineTool } from "eve/tools";
import { z } from "zod";
import { listCompetitors } from "../lib/db";

export default defineTool({
  description: "List every tracked competitor with its pricing page URL.",
  inputSchema: z.object({}),
  async execute() {
    return { competitors: await listCompetitors() };
  },
});
