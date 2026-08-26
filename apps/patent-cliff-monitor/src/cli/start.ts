import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { startPatentCliffPhase } from '../lib/agent';
import { DEFAULT_BRIEF, buildResearchBrief } from '../lib/brief';

const drugListPath = process.env.DRUG_LIST_PATH;
let brief: string;

if (drugListPath) {
  const absolutePath = resolve(process.cwd(), drugListPath);
  if (!existsSync(absolutePath)) {
    console.error(`DRUG_LIST_PATH points at a file that does not exist: ${absolutePath}`);
    process.exit(1);
  }
  // A JSON or CSV list is only the drugs. Wrap it in the standing brief so a
  // custom list asks for the same research as the bundled example.
  brief = buildResearchBrief(readFileSync(absolutePath, 'utf-8'));
} else {
  brief = DEFAULT_BRIEF;
}

startPatentCliffPhase(brief)
  .then(({ text, runId, effort, status }) => {
    console.log(`\n[request 1] run ${runId} (effort: ${effort}, status: ${status})`);
    console.log('[nimble]', text);
    console.log(`\nResume later — in a separate process:\n  npm run cli:resume -- ${runId}`);
  })
  .catch(err => {
    console.error('Failed to start research:', err.message);
    process.exit(1);
  });
