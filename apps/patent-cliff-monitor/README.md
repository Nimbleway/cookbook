# Patent Cliff Monitor

> **Nimble Vercel AI SDK connector cookbook:** This app registers Nimble's Web Search Agent tools with [Vercel AI SDK v6](https://ai-sdk.dev/). For the run lifecycle, deployment steps, verification checklist, and constraints, read [ai-setup.md](./ai-setup.md).

A research report generator for the pharmaceutical industry. Input a list of drugs nearing patent expiry, and the app runs a deep-research Nimble Web Search Agent to produce a sourced, confidence-graded report covering biosimilars, generics, court dockets, pricing, and manufacturer responses.

> **Runs locally.** `npm run dev` starts a server on `localhost:3000` — not exposed to your network or the internet. Your API keys are stored only in a local `.env.local` and never leave your machine.

## What it does

**Input:** A list of drugs with patent-expiry context (typed in the browser or read by the CLI from JSON/CSV).

**Output:** A per-drug research report containing:

1. **FDA approvals** — biosimilars, generics, ANDAs currently active
2. **Court dockets** — injunctions, settlements, IPR decisions
3. **Pricing** — WAC, median acquisition cost, any price cuts
4. **Manufacturer responses** — line extensions, formulations, marketing pivots
5. **Upcoming catalysts** — any patent events within the next 24 months

Every finding includes a source link and a confidence grade (high/medium/low). The report is structured per-drug, then a summary section ranking overall competitive threat.

## Stack

- [@nimble-way/ai-sdk](https://www.npmjs.com/package/@nimble-way/ai-sdk) — Nimble's Vercel AI SDK connector, registering start, status, and result tools for Web Search Agent runs
- [Vercel AI SDK v6](https://ai-sdk.dev/) — runs the app-side agent that invokes the connector tools, with the model provider (OpenRouter, OpenAI, or Vercel AI Gateway) chosen in `.env`
- [react-markdown](https://github.com/remarkjs/react-markdown) + [remark-gfm](https://github.com/remarkjs/remark-gfm) — renders the GitHub Flavored Markdown report Nimble returns, tables included
- [Next.js](https://nextjs.org) — app router and API routes

## Setup

### Prerequisites

- **Node.js 20 LTS or later** (recommended by Nimble's Node SDK documentation)
- **A Nimble API key** — from [online.nimbleway.com](https://online.nimbleway.com) → Account Settings → API Keys
- **A pre-created Web Search Agent** — create one in the [Nimble console](https://app.nimbleway.com). Its ID (looks like `wsa_…`) goes in `NIMBLE_AGENT_ID`

### Step by step

**1. Clone and enter the app**

```bash
git clone https://github.com/Nimbleway/cookbook.git
cd cookbook/apps/patent-cliff-monitor
```

**2. Install**

```bash
npm install
```

**3. Configure**

```bash
cp .env.example .env.local
```

Edit `.env.local`:

| Variable | Required | Description |
|---|---|---|
| `NIMBLE_API_KEY` | yes | From online.nimbleway.com |
| `NIMBLE_AGENT_ID` | yes | Your pre-created Web Search Agent ID (e.g. `wsa_abc123`) |
| `RESEARCH_PROVIDER` | no | `openrouter`, `openai`, or `gateway`. Unset means the first provider with a key set wins |
| `RESEARCH_MODEL` | no | Model id for that provider. Unset takes the provider's default |
| `OPENROUTER_API_KEY` | one of | Needed when `RESEARCH_PROVIDER=openrouter` |
| `AI_GATEWAY_API_KEY` | one of | Needed when `RESEARCH_PROVIDER=gateway` |
| `OPENAI_API_KEY` | one of | Needed when `RESEARCH_PROVIDER=openai` |
| `DRUG_LIST_PATH` | CLI only | Path to a drugs.json or drugs.csv file for `npm run cli:start` |

**4. Run**

```bash
npm run dev
```

Open http://localhost:3000. Click "Generate Report" — it kicks off a research run in milliseconds, then polls for the full report (5-15 minutes depending on how many drugs).

### Choosing a model

The model is spent once per report, to invoke the connector's `startResearch` tool. Nimble does the research, so the cheapest model that reliably emits one tool call is the right one.

| Provider | Default model | Cost |
|---|---|---|
| `openrouter` | `google/gemma-4-31b-it:free` | free |
| `gateway` | `openai/gpt-5-nano` | $0.05 / $0.40 per million tokens |
| `openai` | `gpt-5-nano` | $0.05 / $0.40 per million tokens |

Whatever you pick **must support tool calling**. The start step is a forced tool call, so a model without tool support cannot run it. On OpenRouter, check `tools` and `tool_choice` in the model's `supported_parameters`.

## Custom drug lists

Place a JSON file and point `DRUG_LIST_PATH` at it:

```json
[
  { "name": "Drug Name (generic)", "expiry": "2025", "notes": "Any specific things to watch" },
  { "name": "Another Drug", "expiry": "2026-2027", "notes": "" }
]
```

Or a CSV — one drug name per line, or with an optional expiry date after a semicolon.

The file only needs to contain the drugs. `buildResearchBrief()` in `src/lib/brief.ts` wraps it in the same standing brief the browser uses, so a custom list asks for the same FDA, docket, pricing, and manufacturer-response research as the bundled example. If `DRUG_LIST_PATH` points at a file that does not exist, the CLI stops rather than quietly falling back to the example list.

## CLI usage

Run the report from the terminal instead of the browser:

```bash
# Start a research run (uses bundled example drugs)
npm run cli:start

# Or point at your own drug list
DRUG_LIST_PATH=./my-drugs.json npm run cli:start

# Resume a previous run
npm run cli:resume -- task_run_abc123
```

The resume command prints:
- The full patent cliff report
- Confidence scores per claim
- Source links (top 5 shown, all listed if fewer)

## Architecture

```
app/page.tsx               - UI: input, generate button, progress, cited report
app/report.tsx             - Markdown rendering and citation callout linking
app/globals.css            - Design tokens and all component styling
app/api/research/route.ts  - API endpoint: starts or resumes a patent cliff run
src/lib/agent.ts           - Core: startPatentCliffPhase, resumePatentCliffPhase, checkRunStatus
src/lib/nimble-tools.ts    - Connector tool registration and direct tool invocation
src/lib/brief.ts           - The shared research brief used by the UI and the CLI
src/cli/start.ts           - CLI: start from terminal (loads drug list from file or defaults)
src/cli/resume.ts          - CLI: resume a previous run
data/drugs.json            - Example drug list (5 blockbuster drugs on the patent cliff)
```

The flow:

1. User provides drug list (via UI or file)
2. The page POSTs to `/api/research` with the list
3. `startPatentCliffPhase()` runs a Vercel AI SDK agent with Nimble's `nimbleAgentStartRun()` connector tool and returns the new research run ID immediately
4. The page persists the `runId` in browser session storage, then polls `/api/research` every 5 seconds, waiting for each check to return before scheduling the next; a refresh in the same browser session resumes the run
5. When Nimble reports the run complete, the page renders the markdown report with each `[n]` callout linked to the source Nimble cited for that claim

The run ID stays in `sessionStorage` after the report arrives, so refreshing the tab fetches the finished report straight back from Nimble. That costs nothing: no model call, and a completed run returns immediately. Starting a new report clears it, and the UI shows the full run ID with a `cli:resume` command so a report is recoverable from any machine.

## Async research pattern

This cookbook demonstrates the asynchronous Web Search Agent lifecycle through Nimble's Vercel AI SDK connector:

- **`nimbleAgentStartRun()`** — starts research and returns a `task_run_...` ID immediately.
- **`nimbleAgentRunStatus()`** — retrieves the current state without waiting.
- **`nimbleAgentRunResult()`** — retrieves the cited result once the run completes.

A patent cliff report for 3-5 drugs requires 5-10 sources per drug — 15-50 total research calls. That's 5-15 minutes, which is why the async pattern is required: no chat request should ever block that long.

### Where the model sits

Starting a run is a model decision, so `startPatentCliffPhase()` runs a Vercel AI SDK agent: `generateText()` with the connector's tools, pinned to `startResearch` via `toolChoice` and stopped at one step. That is one model call per report, through whichever provider `RESEARCH_PROVIDER` selects.

Note that the Vercel **AI SDK** and the Vercel **AI Gateway** are different things. The AI SDK is the framework and is always used. The AI Gateway is one optional way to reach a model, selected with `RESEARCH_PROVIDER=gateway`. With `openrouter` or `openai` the request goes straight to that provider and the gateway is not involved.

Reading a run back is not a model decision. The run ID is already known and Nimble returns the cited report verbatim, so `resumePatentCliffPhase()` and `checkRunStatus()` invoke the same connector `Tool` objects directly through `runTool()`. Routing a five-second poll through an LLM for a fifteen-minute job would mean roughly 180 model calls per report and would let the model paraphrase citations Nimble already graded.

Both paths go through `@nimble-way/ai-sdk`. Only the first one needs a model provider.

## Known API behavior

- Search, Extract, and Web Search Agent runs ship today. Map and Crawl are planned follow-ups.
- **Agent runs need a pre-created agent instance.** Set `NIMBLE_AGENT_ID`.
- **Nimble owns the research and cited report.** A model provider is required only because this is a Vercel AI SDK connector example: the app uses it to invoke the configured Nimble tools. The model does not receive the Nimble API key or choose the Nimble agent. It runs once per report and the provider is set in `.env`, so it can run entirely on a free model.
- **Node.js runtime (20 LTS or later is recommended by Nimble's Node SDK documentation).** The API route explicitly selects Node.js.
- **The UI polls the run state.** Nimble also supports event streaming for applications that need live progress events.

## Deployment

The source is Vercel-ready via `vercel.json`, but not deployed by this repository. Set `NIMBLE_API_KEY`, `NIMBLE_AGENT_ID`, and your chosen model-provider key as server-only environment variables in Vercel, then deploy:

```bash
npm i -g vercel
vercel --prod
```

Do not describe the app as deployed until the live URL has completed the post-deployment verification in [ai-setup.md](./ai-setup.md).
