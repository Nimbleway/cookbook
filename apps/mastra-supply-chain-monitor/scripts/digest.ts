// Print a day's digest from the ledger: npm run digest [-- YYYY-MM-DD]
import { eventsChangedOn, leadsOn, startFailuresOn } from "../src/mastra/lib/ledger-events";
import { digestMarkdown } from "../src/mastra/lib/notify";

const date = process.argv[2] ?? new Date().toISOString().slice(0, 10);
console.log(
  digestMarkdown({
    date,
    events: await eventsChangedOn(date),
    leads: await leadsOn(date),
    startFailures: await startFailuresOn(date),
  }),
);
