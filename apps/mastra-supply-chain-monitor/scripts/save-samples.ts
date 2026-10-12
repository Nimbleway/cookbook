// Save the latest collected live results as demo data, so USE_LIVE=false replays real
// research with no Nimble runs and no model calls:
//   data/samples/sweep_<product>.json   the raw result, exactly as the package returned it
//   data/samples/triage.json            the triage agent's assessments, keyed by eventKey
import { mkdir, writeFile } from "node:fs/promises";
import { createClient } from "@libsql/client";
import { config } from "../src/mastra/config";
import { recentEvents } from "../src/mastra/lib/ledger";
import { WATCHLIST } from "../src/mastra/watchlist";

const db = createClient({ url: config.databaseUrl, authToken: config.databaseAuthToken });
await mkdir(`${config.dataDir}/samples`, { recursive: true });

for (const p of WATCHLIST) {
  const r = await db.execute({
    sql: `SELECT raw_json FROM runs WHERE product = ? AND state = 'collected' AND run_id NOT LIKE 'sample-%'
          ORDER BY collected_at DESC LIMIT 1`,
    args: [p.slug],
  });
  const raw = r.rows[0]?.raw_json as string | undefined;
  if (!raw) {
    console.log(`${p.slug}: no collected live result, skipped`);
    continue;
  }
  await writeFile(`${config.dataDir}/samples/sweep_${p.slug}.json`, JSON.stringify(JSON.parse(raw), null, 2));
  console.log(`${p.slug}: saved`);
}

const triage: Record<string, unknown> = {};
for (const e of await recentEvents(30)) {
  if (!e.triage) continue;
  triage[e.eventKey] = {
    eventKey: e.eventKey,
    duplicateOf: null,
    severity: e.triage.severity,
    affectedProducts: e.products,
    rationale: e.triage.rationale,
    recommendedAction: e.triage.recommendedAction,
  };
}
await writeFile(`${config.dataDir}/samples/triage.json`, JSON.stringify(triage, null, 2));
console.log(`triage: ${Object.keys(triage).length} assessments saved`);
