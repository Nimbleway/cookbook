// A collect tick that fails part-way (here: Slack is down) loses nothing. Once its claim
// goes stale, a later tick processes the runs again, sends the alert exactly once, and
// doesn't duplicate the leads.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createClient } from "@libsql/client";
import { cacheHighTriage, setupTestEnv } from "./helpers/setup";

const { dir } = setupTestEnv("recovery");
cacheHighTriage(dir);

const { mastra } = await import("../src/mastra/index");
const { config } = await import("../src/mastra/config");
const { leadsOn } = await import("../src/mastra/lib/ledger-events");

async function run(id: "sweepWorkflow" | "collectWorkflow", inputData: object) {
  const r = await (await mastra.getWorkflow(id).createRun()).start({ inputData: inputData as never });
  return r as { status: string; result?: any };
}

test("Slack down mid-tick, then recovery: one alert, no duplicate leads", async () => {
  await run("sweepWorkflow", { force: true });

  config.slackWebhookUrl = "http://127.0.0.1:9/unreachable";
  const failed = await run("collectWorkflow", {});
  assert.notEqual(failed.status, "success");

  // The claim is still fresh: another tick leaves the runs alone.
  config.slackWebhookUrl = undefined;
  const early = await run("collectWorkflow", {});
  assert.equal(early.result.collected, 0);

  // Age the claims past the stale window, as 15 minutes would.
  const db = createClient({ url: process.env.TURSO_DATABASE_URL! });
  await db.execute("UPDATE runs SET claimed_at = '2000-01-01T00:00:00Z' WHERE state = 'collecting'");

  const recovered = await run("collectWorkflow", {});
  assert.equal(recovered.status, "success");
  assert.equal(recovered.result.collected, 3);
  assert.equal(recovered.result.alerted.length, 1);

  const today = new Date().toISOString().slice(0, 10);
  const leads = await leadsOn(today);
  assert.equal(leads.length, new Set(leads.map((l) => l.text)).size);

  // And it doesn't alert a third time.
  await run("sweepWorkflow", { force: true });
  const again = await run("collectWorkflow", {});
  assert.equal(again.result.alerted.length, 0);
});
