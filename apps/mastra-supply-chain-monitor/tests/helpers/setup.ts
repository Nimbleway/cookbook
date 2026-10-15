// Shared setup for the end-to-end tests: a temp data dir with the laptop fixture as the
// demo sample, and a demo-mode env pointing at a fresh ledger. Call setupTestEnv() before
// importing src/mastra/index, since config reads the env on import.
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { eventsFromResult } from "../../src/mastra/lib/events";

export const FIXTURE = "tests/fixtures/sweep_laptop_smoke.json";

export function setupTestEnv(prefix: string): { dir: string; samplePath: string } {
  const dir = mkdtempSync(join(tmpdir(), `scm-${prefix}-`));
  mkdirSync(join(dir, "samples"));
  const samplePath = join(dir, "samples/sweep_laptop.json");
  cpSync(FIXTURE, samplePath);
  process.env.USE_LIVE = "false";
  process.env.DATA_DIR = dir;
  process.env.TURSO_DATABASE_URL = `file:${join(dir, "test.db")}`;
  delete process.env.SLACK_WEBHOOK_URL;
  return { dir, samplePath };
}

// Caches a `high` triage for the fixture's one event, so a collect needs no model call.
export function cacheHighTriage(dir: string): void {
  const [event] = eventsFromResult(JSON.parse(readFileSync(FIXTURE, "utf8")), "laptop").events;
  writeFileSync(
    join(dir, "samples/triage.json"),
    JSON.stringify({
      [event.eventKey]: { eventKey: event.eventKey, duplicateOf: null, severity: "high", affectedProducts: ["laptop"], rationale: "test", recommendedAction: "test" },
    }),
  );
}
