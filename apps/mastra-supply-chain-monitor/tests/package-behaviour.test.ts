// The @nimble-way/mastra behaviours this app relies on, checked against a mock client.
import assert from "node:assert/strict";
import { test } from "node:test";
import { NimbleAgentRunError, nimbleAgentRunResultTool, nimbleAgentStartRunTool } from "@nimble-way/mastra";

const AGENT = "wsa_0a1b2c3d4e5f60718293a4b5c6d7e8f9";
const RUN_ID = "task_run_9f8e7d6c5b4a39281706f5e4d3c2b1a0";
const KEY = "sk-test-not-a-real-key-000";
const run = (status: string, isActive: boolean) => ({
  id: RUN_ID,
  web_search_agent_id: AGENT,
  interaction_id: RUN_ID,
  status,
  is_active: isActive,
  effort: "high",
  created_at: "2026-10-12T06:00:00Z",
});
const httpError = (status: number) => Object.assign(new Error(`HTTP ${status}`), { status });
const client = (runs: Record<string, unknown>) =>
  ({ agents: { runs: { create: async () => run("queued", true), get: async () => run("running", true), ...runs } } }) as never;

test("a run still working is not an error: ready is false", async () => {
  const tool = nimbleAgentRunResultTool({ agentId: AGENT, apiKey: KEY, client: client({ result: async () => { throw httpError(409); } }) });
  const out = (await tool.execute!({ runId: RUN_ID }, {} as never)) as { ready: boolean };
  assert.equal(out.ready, false);
});

test("a failed run throws with reason 'failed' and keeps the runId", async () => {
  const tool = nimbleAgentRunResultTool({
    agentId: AGENT,
    apiKey: KEY,
    client: client({
      get: async () => run("failed", false),
      result: async () => ({ run: run("failed", false), error: { message: "boom", ref_id: "r" } }),
    }),
  });
  await assert.rejects(tool.execute!({ runId: RUN_ID }, {} as never), (e: unknown) => {
    assert.ok(e instanceof NimbleAgentRunError);
    assert.equal(e.reason, "failed");
    assert.equal(e.runId, RUN_ID);
    return true;
  });
});

test("run creation: 429 means not created, 500 means it might exist", async () => {
  for (const [status, outcome] of [[429, "not-created"], [500, "unknown"]] as const) {
    const tool = nimbleAgentStartRunTool({ agentId: AGENT, apiKey: KEY, client: client({ create: async () => { throw httpError(status); } }) });
    await assert.rejects(tool.execute!({ task: "x" }, {} as never), (e: unknown) => {
      assert.ok(e instanceof NimbleAgentRunError);
      assert.equal(e.createOutcome, outcome);
      return true;
    });
  }
});

test("run creation is sent once, never retried", async () => {
  let calls = 0;
  const tool = nimbleAgentStartRunTool({
    agentId: AGENT,
    apiKey: KEY,
    client: client({ create: async () => { calls++; throw httpError(503); } }),
  });
  await assert.rejects(tool.execute!({ task: "x" }, {} as never));
  assert.equal(calls, 1);
});
