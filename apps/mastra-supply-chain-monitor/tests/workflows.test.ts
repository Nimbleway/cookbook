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
const { recentEvents, claimRun, recordRunStarted } = await import("../src/mastra/lib/ledger");

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

test("two overlapping sweeps: exactly one starts runs", async () => {
  const [a, b] = await Promise.all([start("sweepWorkflow", { force: false }), start("sweepWorkflow", { force: false })]);
  const winner = a.refused === null ? a : b;
  const loser = a.refused === null ? b : a;
  assert.deepEqual(winner.started.map((s: any) => s.product), ["laptop", "earbuds", "smartwatch"]);
  assert.match(loser.refused, /minimum gap/);
  assert.equal(loser.started.length, 0);
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

test("two overlapping collects take each run exactly once", async () => {
  await start("sweepWorkflow", { force: true });
  const [a, b] = await Promise.all([start("collectWorkflow", {}), start("collectWorkflow", {})]);
  assert.equal(a.collected + b.collected, 3);
  assert.equal(a.alerted.length + b.alerted.length, 0);
});

test("a claimed run can't be claimed again until its claim goes stale", async () => {
  const runId = "sample-laptop-claim-test";
  await recordRunStarted({ runId, product: "laptop", windowStart: "2026-10-05", windowEnd: "2026-10-12", startedAt: new Date().toISOString() });
  assert.equal(await claimRun(runId), true);
  assert.equal(await claimRun(runId), false);
});

test("an already-alerted event alerts again when it escalates", async () => {
  const sample = JSON.parse(readFileSync(join(dir, "samples/sweep_laptop.json"), "utf8"));
  sample.output.json.events[0].status = "escalating";
  writeFileSync(join(dir, "samples/sweep_laptop.json"), JSON.stringify(sample));
  await start("sweepWorkflow", { force: true });
  const out = await start("collectWorkflow", {});
  assert.equal(out.updates, 1);
  assert.equal(out.alerted.length, 1);

  // Same status again: no further alert.
  await start("sweepWorkflow", { force: true });
  const again = await start("collectWorkflow", {});
  assert.equal(again.alerted.length, 0);
});

test("a status that returns after an alerted escalation alerts again", async () => {
  // Alerted so far: announced (first collect), then escalating (previous test).
  const sample = JSON.parse(readFileSync(join(dir, "samples/sweep_laptop.json"), "utf8"));
  sample.output.json.events[0].status = "announced";
  writeFileSync(join(dir, "samples/sweep_laptop.json"), JSON.stringify(sample));
  await start("sweepWorkflow", { force: true });
  const out = await start("collectWorkflow", {});
  assert.equal(out.updates, 1);
  assert.equal(out.alerted.length, 1);
});
