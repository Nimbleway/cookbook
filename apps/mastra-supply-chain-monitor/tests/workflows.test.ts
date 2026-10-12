// End to end, offline: sweep → collect → act, in demo mode against a temp database.
// No Nimble run is created and no model is called (triage comes from a cache).
import assert from "node:assert/strict";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const dir = mkdtempSync(join(tmpdir(), "scm-"));
mkdirSync(join(dir, "samples"));
cpSync("tests/fixtures/sweep_laptop_smoke.json", join(dir, "samples/sweep_laptop.json"));

process.env.USE_LIVE = "false";
process.env.DATA_DIR = dir;
process.env.TURSO_DATABASE_URL = `file:${join(dir, "test.db")}`;
delete process.env.SLACK_WEBHOOK_URL;

const { mastra } = await import("../src/mastra/index");
const { eventsFromResult } = await import("../src/mastra/lib/events");
const { recentEvents } = await import("../src/mastra/lib/ledger");

// Cache a triage for the one real event so the collect pass needs no model.
const [event] = eventsFromResult(JSON.parse(readFileSync("tests/fixtures/sweep_laptop_smoke.json", "utf8")), "laptop").events;
writeFileSync(
  join(dir, "samples/triage.json"),
  JSON.stringify({
    [event.eventKey]: {
      eventKey: event.eventKey,
      duplicateOf: null,
      severity: "high",
      affectedProducts: ["laptop"],
      rationale: "test",
      recommendedAction: "test",
    },
  }),
);

async function start(id: "sweepWorkflow" | "collectWorkflow", inputData: object) {
  const run = await mastra.getWorkflow(id).createRun();
  const res = await run.start({ inputData: inputData as never });
  assert.equal(res.status, "success", JSON.stringify(res));
  return (res as { result: any }).result;
}

test("sweep starts one run per product and records the runIds", async () => {
  const out = await start("sweepWorkflow", { force: false });
  assert.equal(out.refused, null);
  assert.deepEqual(out.started.map((s: any) => s.product), ["laptop", "earbuds", "smartwatch"]);
});

test("a second sweep inside the minimum gap is refused", async () => {
  const out = await start("sweepWorkflow", { force: false });
  assert.match(out.refused, /minimum gap/);
  assert.equal(out.started.length, 0);
});

test("collect picks up the runs, records the event, alerts, and writes the digest", async () => {
  const out = await start("collectWorkflow", {});
  assert.equal(out.collected, 3);
  assert.equal(out.newEvents, 1);
  assert.equal(out.alerted.length, 1);
  assert.ok(out.digestPath && existsSync(out.digestPath));
  assert.match(readFileSync(out.digestPath, "utf8"), /blank sailings/i);
  const stored = await recentEvents(14);
  assert.equal(stored.length, 1);
  assert.equal(stored[0].triage?.severity, "high");
});

test("the same result again is a repeat: nothing new, no second alert", async () => {
  await start("sweepWorkflow", { force: true });
  const out = await start("collectWorkflow", {});
  assert.equal(out.collected, 3);
  assert.equal(out.newEvents, 0);
  assert.equal(out.alerted.length, 0);
  assert.equal((await recentEvents(14)).length, 1);
});

test("nothing pending: collect is a no-op", async () => {
  const out = await start("collectWorkflow", {});
  assert.equal(out.collected, 0);
});
