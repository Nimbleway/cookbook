# AI Setup Guide: Patent Cliff Monitor

## Goal

Turn a list of medicines nearing patent expiry into a cited competitive-intelligence report, using a Nimble Web Search Agent through the [Nimble Vercel AI SDK connector](https://docs.nimbleway.com/integrations/connectors/vercel-ai-sdk). The report covers FDA biosimilar and generic approvals, court dockets, pricing signals, manufacturer response, and near-term patent events, each finding source-linked and confidence-graded.

## Product framing

The demo value is the **asynchronous** agent-run lifecycle. A patent-cliff report takes 5 to 15 minutes, which no browser request should ever block on. This app starts the run in milliseconds, keeps only the `task_run_…` handle in the browser session, and retrieves the cited report from a later request. Nimble is the live-web research layer; the UI, the store, and the model provider are all swappable.

---

## Setup steps

```bash
cd apps/patent-cliff-monitor
npm install
cp .env.example .env.local
# add NIMBLE_API_KEY, NIMBLE_AGENT_ID, and one model-provider key
npm run dev
```

`NIMBLE_AGENT_ID` is a pre-created Web Search Agent (`wsa_…`) from the Nimble console. Agent runs will not start without one.

---

## Verification commands

```bash
# types and tests
npx tsc --noEmit
npm test

# production build
npm run build

# start a run from the terminal, then retrieve it later
npm run cli:start
npm run cli:resume -- task_run_<id>

# API contract, without a browser
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:3000/api/research \
  -H 'Content-Type: application/json' -d '{}'                    # 400, missing task
curl -s -X POST localhost:3000/api/research \
  -H 'Content-Type: application/json' -d '{"runId":"task_run_0"}' # 502 unknown run, 500 if unconfigured
```

---

## Where the model sits

Starting a run is a model decision, so it goes through Vercel AI SDK `generateText()` with the connector's `nimbleAgentStartRun()` tool, pinned with `toolChoice` and stopped after one step. That is **one model call per report**.

Reading a run back is not a model decision. The `runId` is already known and Nimble returns the cited report verbatim, so `nimbleAgentRunStatus()` and `nimbleAgentRunResult()` are invoked directly as AI SDK tools. Polling a 15-minute run through a model every five seconds would cost roughly 180 model calls per report and let the model paraphrase citations Nimble had already graded.

Note that the Vercel **AI SDK** and the Vercel **AI Gateway** are different things. The AI SDK is the framework and is always used. The AI Gateway is one optional route to a model.

---

## Safe customisations

- **Change the medicines:** Edit the brief in the browser, or point `DRUG_LIST_PATH` at a JSON or CSV file. The file only needs the medicines; `buildResearchBrief()` in `src/lib/brief.ts` wraps it in the standing brief.
- **Change the research brief:** Edit `RESEARCH_DIRECTIVES` in `src/lib/brief.ts`. This is the fastest way to retarget the app at another therapeutic area or another domain entirely.
- **Change the model or provider:** Set `RESEARCH_PROVIDER` (`openrouter`, `openai`, or `gateway`) and `RESEARCH_MODEL` in `.env.local`. No code change needed.
- **Change research depth:** `effort` and `effortCap` in `src/lib/nimble-tools.ts`. `effortCap` bounds what the model may request; it does not bound the developer-set `effort`.
- **Change the polling window:** `POLL_INTERVAL_MS` and `POLL_TIMEOUT_MS` in `app/page.tsx`.

---

## Guardrails

- **The model must support tool calling.** The start step is a forced tool call, so a model without tool support cannot run this at all. On OpenRouter, check `tools` and `tool_choice` in the model's `supported_parameters`.
- **The model writes the `task` argument.** It is instructed to pass the brief through verbatim, but a weaker model can paraphrase or drop an item. Check the first report against your input list when changing models.
- **Never expose credentials to the client.** `NIMBLE_API_KEY` and `NIMBLE_AGENT_ID` are resolved server-side in the API route. Do not move them into `NEXT_PUBLIC_*`.
- **The route must not block.** `nimbleAgentRunResult()` is configured without `wait`, so an active run returns `{ ready: false }` immediately. Enabling `wait` would hold the request open past the 60-second function ceiling.
- **Research support only.** The report is not clinical, regulatory, legal, investment, or pricing advice. Nimble's confidence metadata is a research control, not a substitute for reviewing patent and regulatory claims.
- **Session scope.** The run handle lives in `sessionStorage`, so a report survives a refresh but not a new browser session. Use a database or job store if you need cross-device recovery. Any run remains retrievable from its `task_run_…` ID via the CLI.
