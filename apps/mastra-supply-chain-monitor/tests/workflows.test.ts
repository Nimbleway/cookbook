// End to end, offline: sweep → collect → act, in demo mode against a temp database.
// No Nimble run is created and no model is called (triage comes from a cache).
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { nimbleAgentStartRunTool } from "@nimble-way/mastra";
import { cacheHighTriage, setupTestEnv } from "./helpers/setup";

const { dir } = setupTestEnv("workflows");
cacheHighTriage(dir);

const { mastra } = await import("../src/mastra/index");
const { config } = await import("../src/mastra/config");
const { sweepStartRun } = await import("../src/mastra/nimble");
const { recentEvents, startFailuresOn } = await import("../src/mastra/lib/ledger-events");

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

test("two overlapping collects take each run exactly once", async () => {
  await start("sweepWorkflow", { force: true });
  const [a, b] = await Promise.all([start("collectWorkflow", {}), start("collectWorkflow", {})]);
  assert.equal(a.collected + b.collected, 3);
  assert.equal(a.alerted.length + b.alerted.length, 0);
});

test("a sweep where run creation fails reports it and starts the rest", async () => {
  // A real start-run tool over a mock client: the second create (earbuds) answers 500, so
  // a run might exist. The package classifies it; the sweep records it and moves on.
  const MOCK_AGENT = "wsa_00000000000000000000000000000000";
  let creates = 0;
  const mock = nimbleAgentStartRunTool({
    agentId: MOCK_AGENT,
    apiKey: "sk-test-not-a-real-key-000",
    client: {
      agents: {
        runs: {
          create: async () => {
            creates++;
            if (creates === 2) throw Object.assign(new Error("HTTP 500"), { status: 500 });
            const id = `task_run_${String(creates).padStart(32, "0")}`;
            return { id, web_search_agent_id: MOCK_AGENT, interaction_id: id, status: "queued", is_active: true, effort: "high", created_at: new Date().toISOString() };
          },
        },
      },
    } as never,
  });
  const realExecute = sweepStartRun.execute;
  sweepStartRun.execute = mock.execute;
  config.useLive = true;
  try {
    const out = await start("sweepWorkflow", { force: true });
    assert.deepEqual(out.started.map((s: any) => s.product), ["laptop", "smartwatch"]);
    assert.deepEqual(out.failed.map((f: any) => [f.product, f.createOutcome]), [["earbuds", "unknown"]]);
    const today = new Date().toISOString().slice(0, 10);
    const recorded = await startFailuresOn(today);
    assert.deepEqual(recorded.map((r: any) => [r.product, r.create_outcome]), [["earbuds", "unknown"]]);
  } finally {
    config.useLive = false;
    sweepStartRun.execute = realExecute;
  }
});
