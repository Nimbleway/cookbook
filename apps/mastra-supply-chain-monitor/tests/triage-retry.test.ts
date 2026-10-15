// A triage call that fails leaves the event untriaged. When the event comes back as a
// repeat, it's scored again and alerts; a repeat that already has a triage isn't re-sent.
import assert from "node:assert/strict";
import { cpSync, mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const dir = mkdtempSync(join(tmpdir(), "scm-triage-"));
mkdirSync(join(dir, "samples"));
cpSync("tests/fixtures/sweep_laptop_smoke.json", join(dir, "samples/sweep_laptop.json"));
process.env.USE_LIVE = "false";
process.env.DATA_DIR = dir;
process.env.TURSO_DATABASE_URL = `file:${join(dir, "test.db")}`;
delete process.env.SLACK_WEBHOOK_URL;

const { mastra } = await import("../src/mastra/index");

// No triage.json here, so every scoring goes to the agent; stub its model call.
const agent = mastra.getAgent("triageAgent");
let calls = 0;
let reply: (prompt: string) => unknown = () => {
  throw new Error("model unavailable");
};
agent.generate = (async (prompt: string) => {
  calls++;
  return reply(prompt);
}) as never;

async function tick() {
  for (const [id, inputData] of [["sweepWorkflow", { force: true }], ["collectWorkflow", {}]] as const) {
    const r = await (await mastra.getWorkflow(id).createRun()).start({ inputData: inputData as never });
    assert.equal(r.status, "success");
    if (id === "collectWorkflow") return (r as { result: any }).result;
  }
}

test("an event recorded untriaged is scored again when it repeats, then alerts", async () => {
  const first = await tick();
  assert.equal(first.newEvents, 1);
  assert.equal(first.alerted.length, 0);

  reply = (prompt) => {
    const [e] = JSON.parse(prompt).CANDIDATES;
    return { object: { assessments: [{ eventKey: e.eventKey, duplicateOf: null, severity: "high", affectedProducts: ["laptop"], rationale: "t", recommendedAction: "t" }] } };
  };
  const second = await tick();
  assert.equal(second.newEvents, 0);
  assert.equal(second.alerted.length, 1);

  const before = calls;
  const third = await tick();
  assert.equal(calls, before, "a triaged repeat is not sent to the agent again");
  assert.equal(third.alerted.length, 0);
});
