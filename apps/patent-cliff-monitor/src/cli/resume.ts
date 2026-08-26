import { resumePatentCliffPhase } from '../lib/agent';

const runId = process.argv.slice(2)[0];
if (!runId) {
  console.error('Usage: npm run cli:resume -- <runId>');
  process.exit(1);
}

resumePatentCliffPhase(runId)
  .then(({ text, result }) => {
    if (result?.ready && result.output.trust) {
      const trust = result.output.trust;
      console.log(`[trust] confidence: ${trust.confidence} — ${trust.sources.length} sources, ${trust.claims.length} cited claims`);
      for (const s of trust.sources.slice(0, 5)) {
        console.log(`  [${s.type}] ${s.title ?? s.url}\n         ${s.url}`);
      }
    }
    console.log('\n[nimble]', text);
  })
  .catch(err => {
    console.error('Failed to resume research:', err.message);
    process.exit(1);
  });
