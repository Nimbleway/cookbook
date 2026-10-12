// HTTP triggers for the two workflows. A scheduler outside the server (GitHub Actions in
// this cookbook) calls these, so the server can sleep between ticks.
//
// The cron routes are excluded from server auth (`requiresAuth: false`) and check their
// own CRON_SECRET instead, so the scheduler holds a key that can only trigger the
// monitor, not chat with the agents. The check runs inside the handler: Mastra skips
// middleware on routes that opt out of auth.
import { timingSafeEqual } from "node:crypto";
import type { Mastra } from "@mastra/core";
import { registerApiRoute } from "@mastra/core/server";
import type { Context } from "hono";
import { config } from "./config";
import { digestMarkdown } from "./lib/notify";
import { eventsChangedOn, leadsOn, startFailuresOn } from "./lib/ledger";

function matches(given: string | undefined, expected: string): boolean {
  const a = Buffer.from(given ?? "");
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

// Fails closed: with no secret configured the route refuses everything.
function rejectUnlessCron(c: Context): Response | undefined {
  if (!config.cronSecret) return c.json({ error: "Route disabled: CRON_SECRET not configured" }, 503);
  const token = c.req.header("Authorization")?.replace(/^Bearer\s+/i, "");
  if (!matches(token, config.cronSecret)) return c.json({ error: "Unauthorized" }, 401);
  return undefined;
}

async function runWorkflow(mastra: Mastra, id: "sweepWorkflow" | "collectWorkflow", inputData: object) {
  const run = await mastra.getWorkflow(id).createRun();
  const res = await run.start({ inputData: inputData as never });
  return res.status === "success" ? res.result : { status: res.status, error: String((res as { error?: unknown }).error ?? "") };
}

export const apiRoutes = [
  // Collect first, so runs left over from the previous sweep are picked up even if every
  // collect tick in between was skipped. Then start the new runs.
  registerApiRoute("/cron/sweep", {
    method: "POST",
    requiresAuth: false,
    handler: async (c) => {
      const rejected = rejectUnlessCron(c);
      if (rejected) return rejected;
      const mastra = c.get("mastra");
      const collected = await runWorkflow(mastra, "collectWorkflow", {});
      const swept = await runWorkflow(mastra, "sweepWorkflow", { force: false });
      return c.json({ collected, swept });
    },
  }),
  registerApiRoute("/cron/collect", {
    method: "POST",
    requiresAuth: false,
    handler: async (c) => rejectUnlessCron(c) ?? c.json(await runWorkflow(c.get("mastra"), "collectWorkflow", {})),
  }),
  // Today's digest (or ?date=YYYY-MM-DD), built from the ledger. Protected by server auth
  // (MONITOR_API_KEY), like the agent endpoints.
  registerApiRoute("/digest", {
    method: "GET",
    handler: async (c) => {
      const date = c.req.query("date") ?? new Date().toISOString().slice(0, 10);
      const markdown = digestMarkdown({
        date,
        events: await eventsChangedOn(date),
        leads: await leadsOn(date),
        startFailures: await startFailuresOn(date),
      });
      return c.text(markdown, 200, { "Content-Type": "text/markdown; charset=utf-8" });
    },
  }),
];
