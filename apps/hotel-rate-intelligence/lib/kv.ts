// Vercel KV operations for monitor configs and cron run results.
// Only used in the alerting/cron mode - not needed for on-demand checks.
// KV_REST_API_URL and KV_REST_API_TOKEN must be set in environment variables.

import { kv } from "@vercel/kv";
import { MonitorConfig, AgentResult } from "./types";

const CONFIG_KEY = "monitor_configs";
const RUN_PREFIX = "run:";

export async function getMonitorConfigs(): Promise<MonitorConfig[]> {
  try {
    const configs = await kv.get<MonitorConfig[]>(CONFIG_KEY);
    return configs ?? [];
  } catch {
    return [];
  }
}

export async function saveMonitorConfig(config: MonitorConfig): Promise<void> {
  const configs = await getMonitorConfigs();
  const existing = configs.findIndex((c) => c.id === config.id);
  if (existing >= 0) {
    configs[existing] = config;
  } else {
    configs.push(config);
  }
  await kv.set(CONFIG_KEY, configs);
}

export async function deleteMonitorConfig(id: string): Promise<void> {
  const configs = await getMonitorConfigs();
  await kv.set(
    CONFIG_KEY,
    configs.filter((c) => c.id !== id)
  );
}

export interface RunRecord {
  configId: string;
  runAt: string;
  result: AgentResult;
  alertSent: boolean;
}

export async function saveRunResult(record: RunRecord): Promise<void> {
  const key = `${RUN_PREFIX}${record.configId}:${record.runAt}`;
  await kv.set(key, record, { ex: 60 * 60 * 24 * 30 }); // 30 day TTL
}

export async function getRecentRuns(configId: string, limit = 10): Promise<RunRecord[]> {
  // KV doesn't have a built-in prefix scan on all plans, so we store a run index per config
  const indexKey = `${RUN_PREFIX}${configId}:index`;
  const index = (await kv.get<string[]>(indexKey)) ?? [];
  const recent = index.slice(-limit);

  const records = await Promise.all(
    recent.map((k) => kv.get<RunRecord>(k))
  );
  return records.filter((r): r is RunRecord => r !== null);
}

export async function appendRunIndex(configId: string, runKey: string): Promise<void> {
  const indexKey = `${RUN_PREFIX}${configId}:index`;
  const index = (await kv.get<string[]>(indexKey)) ?? [];
  index.push(runKey);
  // Keep last 100 entries
  await kv.set(indexKey, index.slice(-100));
}
