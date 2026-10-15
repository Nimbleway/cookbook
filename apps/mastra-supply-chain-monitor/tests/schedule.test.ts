// The scheduled job must not retry: the server answers a failed tick with 500, and a retry
// would land on a refused sweep or an already-recorded failure and turn the job green.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workflow = readFileSync(".github/workflows/supply-chain-monitor.yml", "utf8");

test("a failed tick leaves the scheduled job red: curl fails on 500 and never retries", () => {
  assert.match(workflow, /--fail-with-body/);
  assert.doesNotMatch(workflow, /--retry/);
  const maxTime = Number(workflow.match(/--max-time (\d+)/)?.[1]);
  const timeoutMinutes = Number(workflow.match(/timeout-minutes: (\d+)/)?.[1]);
  assert.ok(timeoutMinutes * 60 > maxTime, "the job outlives the request");
});
