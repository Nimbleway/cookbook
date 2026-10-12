// Status changes on an alerted event: self-contained, with its own ledger.
// announced (alert) → escalating (alert) → escalating again (no alert) → announced (alert).
import assert from "node:assert/strict";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const dir = mkdtempSync(join(tmpdir(), "scm-alerts-"));
mkdirSync(join(dir, "samples"));
const samplePath = join(dir, "samples/sweep_laptop.json");
cpSync("tests/fixtures/sweep_laptop_smoke.json", samplePath);
process.env.USE_LIVE = "false";
process.env.DATA_DIR = dir;
process.env.TURSO_DATABASE_URL = `file:${join(dir, "test.db")}`;
delete process.env.SLACK_WEBHOOK_URL;

const { mastra } = await import("../src/mastra/index");
const { eventsFromResult } = await import("../src/mastra/lib/events");

const [event] = eventsFromResult(JSON.parse(readFileSync(samplePath, "utf8")), "laptop").events;
writeFileSync(
  join(dir, "samples/triage.json"),
  JSON.stringify({
    [event.eventKey]: { eventKey: event.eventKey, duplicateOf: null, severity: "high", affectedProducts: ["laptop"], rationale: "t", recommendedAction: "t" },
  }),
);

function setStatus(status: string) {
  const sample = JSON.parse(readFileSync(samplePath, "utf8"));
  sample.output.json.events[0].status = status;
  writeFileSync(samplePath, JSON.stringify(sample));
}

async function tick() {
  for (const [id, inputData] of [["sweepWorkflow", { force: true }], ["collectWorkflow", {}]] as const) {
    const r = await (await mastra.getWorkflow(id).createRun()).start({ inputData: inputData as never });
    assert.equal(r.status, "success");
    if (id === "collectWorkflow") return (r as { result: any }).result;
  }
}

test("an alerted event alerts again on each status change, not on repeats", async () => {
  setStatus("announced");
  const first = await tick();
  assert.equal(first.newEvents, 1);
  assert.equal(first.alerted.length, 1);

  setStatus("escalating");
  const escalated = await tick();
  assert.equal(escalated.updates, 1);
  assert.equal(escalated.alerted.length, 1);

  const repeat = await tick();
  assert.equal(repeat.alerted.length, 0);

  setStatus("announced");
  const returned = await tick();
  assert.equal(returned.updates, 1);
  assert.equal(returned.alerted.length, 1);
});
