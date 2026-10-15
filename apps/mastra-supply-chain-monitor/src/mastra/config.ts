// Runtime settings, read once from the environment. Secrets are read here and passed to
// clients and the server, never into prompts.
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

// `mastra dev` and `mastra build` run from inside the project (src/mastra/public,
// .mastra/output), so local files resolve from the project root: the nearest folder
// above that contains src/mastra.
function projectRoot(): string {
  for (let dir = process.cwd(); ; dir = dirname(dir)) {
    if (existsSync(join(dir, "src", "mastra"))) return dir;
    if (dirname(dir) === dir) return process.cwd();
  }
}
const root = projectRoot();
const dataDir = process.env.DATA_DIR ?? join(root, "data");

export const config = {
  // false = demo mode: no Nimble runs are created; the collector replays saved results
  // from data/samples/. true = the real thing.
  useLive: process.env.USE_LIVE === "true",
  sweepAgentId: process.env.NIMBLE_SWEEP_AGENT_ID ?? "",
  deepDiveAgentId: process.env.NIMBLE_DEEP_DIVE_AGENT_ID ?? "",
  model: process.env.MODEL ?? "anthropic/claude-sonnet-4-6",
  // Saved demo results live in <dataDir>/samples; local digests are written to <dataDir>/digests.
  dataDir,
  // Demo and live keep separate local ledgers, so replayed sample events never count as
  // "already reported" for the live monitor.
  databaseUrl:
    process.env.TURSO_DATABASE_URL ??
    `file:${join(dataDir, process.env.USE_LIVE === "true" ? "monitor.db" : "demo.db")}`,
  databaseAuthToken: process.env.TURSO_AUTH_TOKEN,
  slackWebhookUrl: process.env.SLACK_WEBHOOK_URL,
  cronSecret: process.env.CRON_SECRET,
  apiKey: process.env.MONITOR_API_KEY,
  // A sweep that starts within this many minutes of the last one is refused, so a late
  // GitHub Actions start or a leaked cron secret can't bill extra runs.
  minMinutesBetweenSweeps: Number(process.env.MIN_MINUTES_BETWEEN_SWEEPS ?? 60),
  // The first sweep for a product looks back this far to build a baseline; later sweeps
  // pick up where the previous window ended.
  firstLookbackDays: Number(process.env.FIRST_LOOKBACK_DAYS ?? 7),
};
