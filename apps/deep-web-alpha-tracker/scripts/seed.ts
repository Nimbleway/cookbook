import { changeRows, db, must, saveAgentResult } from '../lib/db';
import { AGENTS } from '../lib/agents';
import { sampleSnapshot } from '../lib/sample';
import type { CompanyRecord } from '../lib/types';

/** Loads the watchlist and the sample snapshot into Supabase. Re-running replaces sample rows only. */
async function main() {
  const snap = sampleSnapshot();
  must(await db().from('dwa_companies').upsert(snap.records.map((r) => r.company)));
  const live = must(await db().from('dwa_agent_data').select('ticker,agent').eq('source', 'live')) as { ticker: string; agent: string }[];
  const keep = new Set(live.map((r) => `${r.ticker}:${r.agent}`));
  let written = 0;
  for (const rec of snap.records) {
    for (const agent of AGENTS) {
      if (keep.has(`${rec.company.ticker}:${agent.key}`)) continue;
      const field = (agent.key === 'deepDive' ? 'deepDive' : agent.key) as keyof CompanyRecord;
      await saveAgentResult(rec.company.ticker, agent.key, { [field]: rec[field] } as Partial<CompanyRecord>, null, 'sample');
      written += 1;
    }
  }
  must(await db().from('dwa_changes').delete().eq('source', 'sample'));
  const rows = changeRows(snap.changes, null, 'sample');
  for (let i = 0; i < rows.length; i += 500) must(await db().from('dwa_changes').insert(rows.slice(i, i + 500)));
  console.log(`Seeded ${snap.records.length} companies, ${written} agent results, ${rows.length} changes.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
