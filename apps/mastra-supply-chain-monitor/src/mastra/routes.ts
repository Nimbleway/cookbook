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
import { eventsChangedOn, leadsOn, startFailuresOn } from "./lib/ledger-events";

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

type Outcome = { ok: boolean; body: unknown };

async function runWorkflow(mastra: Mastra, id: "sweepWorkflow" | "collectWorkflow", inputData: object): Promise<Outcome> {
  const run = await mastra.getWorkflow(id).createRun();
  const res = await run.start({ inputData: inputData as never });
  if (res.status === "success") {
    // A workflow can succeed while a run failed to start or failed on Nimble. Report those
    // as a failed tick too, so the scheduler's job shows them.
    const r = res.result as { failed?: unknown };
    const partial = Array.isArray(r.failed) ? r.failed.length > 0 : typeof r.failed === "number" && r.failed > 0;
    return { ok: !partial, body: res.result };
  }
  return { ok: false, body: { workflow: id, status: res.status, error: String((res as { error?: unknown }).error ?? "") } };
}

// A failed tick answers 500, so the scheduler's job fails visibly instead of staying green.
const respond = (c: Context, body: unknown, ok: boolean) => c.json(body as object, ok ? 200 : 500);

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
      return respond(c, { collected: collected.body, swept: swept.body }, collected.ok && swept.ok);
    },
  }),
  registerApiRoute("/cron/collect", {
    method: "POST",
    requiresAuth: false,
    handler: async (c) => {
      const rejected = rejectUnlessCron(c);
      if (rejected) return rejected;
      const collected = await runWorkflow(c.get("mastra"), "collectWorkflow", {});
      return respond(c, collected.body, collected.ok);
    },
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
