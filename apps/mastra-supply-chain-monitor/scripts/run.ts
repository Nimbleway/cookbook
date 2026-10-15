// Run a workflow from the command line, the same code path the cron routes use.
//   npm run sweep [-- --force]   start research runs (refused within 60 min of the last sweep)
//   npm run collect              collect finished runs, triage, alert, rebuild the digest
import { mastra } from "../src/mastra/index";

const [which, ...flags] = process.argv.slice(2);
const id = which === "sweep" ? "sweepWorkflow" : which === "collect" ? "collectWorkflow" : undefined;
if (!id) {
  console.error("usage: tsx scripts/run.ts <sweep|collect> [--force]");
  process.exit(1);
}

const run = await mastra.getWorkflow(id).createRun();
const res = await run.start({ inputData: (id === "sweepWorkflow" ? { force: flags.includes("--force") } : {}) as never });
console.log(JSON.stringify(res.status === "success" ? res.result : res, null, 2));
process.exit(res.status === "success" ? 0 : 1);
