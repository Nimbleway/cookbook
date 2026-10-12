# mastra-supply-chain-monitor — Nimble × Mastra

![Built with Nimble + Mastra](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20Mastra-edc602)

How to use [Nimble](https://nimbleway.com) Web Search Agents in a Mastra app through the
official [`@nimble-way/mastra`](https://www.npmjs.com/package/@nimble-way/mastra) integration:
start research from a scheduled workflow, collect it on a later tick, read per-claim evidence
out of the result, and give the same tools to a chat agent. The example app that carries
these patterns is a supply chain event monitor for three products.

## The integration

`@nimble-way/mastra` adds three typed tools: start a research run, check its status, fetch
its result. None of them blocks. A run returns a `runId` in about a second and keeps working
on Nimble for minutes. The `runId` is the only handle needed to collect it later, from any
process.

```bash
npm install @nimble-way/mastra @mastra/core zod
```

| Tool (factory) | Model-facing input | Returns |
|---|---|---|
| `nimbleAgentStartRunTool` | `task`, optional `effort` | `runId` right away, plus status and timestamps |
| `nimbleAgentRunStatusTool` | `runId` | An instant status snapshot. Never waits. |
| `nimbleAgentRunResultTool` | `runId` | The answer with its `trust` data, or `{ ready: false }` while still working |

`createNimbleAgentTools()` returns all three with shared settings. Everything else is
developer configuration the model never sees: the API key, the agent ID, `outputSchema`,
`sources`, `effort`, and `effortCap`.

This app uses the tools two ways.

**From code, inside a scheduled workflow.** No model decides whether to start a billed run.

```ts
import { nimbleAgentStartRunTool, nimbleAgentRunResultTool } from "@nimble-way/mastra";

// Developer config: the agent, output schema, source allowlist, and effort.
const startSweep = nimbleAgentStartRunTool({
  agentId: process.env.NIMBLE_SWEEP_AGENT_ID,
  outputSchema: SWEEP_OUTPUT_SCHEMA,
  sources: SWEEP_SOURCES,
  effort: "high",
});
const sweepResult = nimbleAgentRunResultTool({ agentId: process.env.NIMBLE_SWEEP_AGENT_ID });

// Tick 1: start the research and store the runId.
const { runId } = await startSweep.execute({ task }, {});

// Tick 2, minutes later, possibly on a server that slept in between:
const result = await sweepResult.execute({ runId }, {});
if (result.ready) {
  result.output.json;   // events, in the shape of SWEEP_OUTPUT_SCHEMA
  result.output.trust;  // sources and per-claim citations, keyed by JSON path
}
```

**As tools for a chat agent.** The model can start a deep dive and collect it in a later turn.

```ts
import { Agent } from "@mastra/core/agent";
import { createNimbleAgentTools } from "@nimble-way/mastra";

export const investigatorAgent = new Agent({
  id: "investigator",
  model: "anthropic/claude-sonnet-4-6",
  tools: createNimbleAgentTools({ agentId: process.env.NIMBLE_DEEP_DIVE_AGENT_ID, effortCap: "high" }),
  instructions:
    "… Never start a second run for a task that already has a runId. If starting a run fails " +
    "without returning a runId, report the failure and stop. Do not try again.",
});
```

### Things worth knowing before you build on it

**Design scheduled work around start and collect.** Research takes minutes, but the tools return
in seconds. This app starts runs on one cron tick and collects them on later ones, so nothing
waits on research and the server can sleep between ticks.

**Branch on `ready`, never on `status`.** A not-ready result can carry any status, and it never
carries `output`. `if (result.ready)` is the only safe test.

**Run creation is sent exactly once.** A failed start reports `createOutcome`. `"not-created"`
means no run exists. `"unknown"` means one might, so reconcile in the Nimble dashboard before
starting again. The scheduled path here records both and never retries. The chat agent's
instructions keep the docs' "never start a second run" clause, and it held in testing: asked
"is it ready?" too early, the agent checked once, said not yet, and kept the `runId`.

**`outputSchema` buys per-field provenance.** With a schema, every claim in `trust.claims` is
keyed by JSON path (`$.events[2].location`), so each event carries its own citations and
confidence. Without one, claims are keyed by prose callout and can't be attached to a field.
Echoed input fields (`product`, the window dates) come back graded `low` with no citations.
This app leaves them out when grading an event.

**`sources.allow` is a hard whitelist.** A domain left out is a domain the run can't read, and
the gap shows up in the run's `unverified` list, not as an error. The scheduled sweep uses a
curated list of trade press, wires, and official notices. The deep dive passes no per-run
sources (the package requires a non-empty `allow` when you do), so it reads the open web,
guided by the prioritize and avoid rules stored on its agent.

**A free or serverless host won't run Mastra's built-in scheduler.** `createWorkflow({ schedule })`
needs a process that stays up. Serverless hosts stop the process after each request, and a
free Mastra platform server sleeps after about 10 idle minutes. This app's workflows are
triggered over HTTP instead, by a GitHub Actions cron. On an always-on host, the built-in
`schedule` works too (see [Going further](#going-further)).

## Patterns in this cookbook

| Pattern | Where to look |
|---|---|
| Start research runs from code in a Mastra workflow, with schema, sources, and effort fixed by the developer | `src/mastra/nimble.ts`, `src/mastra/workflows/sweep.ts` |
| Collect on a later tick from stored `runId`s, branching on `ready` | `src/mastra/workflows/collect.ts` (`fetch-results`) |
| Handle a failed start: `not-created` vs `unknown`, never retried | `src/mastra/workflows/sweep.ts` (`start-runs`) |
| Turn `trust.claims` into per-record citations and confidence with `outputSchema` paths | `src/mastra/lib/events.ts` |
| A server-enforced source allowlist for one agent, open web for another | `src/mastra/agents-spec.ts`, `src/mastra/nimble.ts` |
| Give the tools to a chat agent with an effort cap, memory, and the no-second-run instruction | `src/mastra/agents/investigator.ts` |
| Pass a run's result to another Mastra agent with structured output | `src/mastra/workflows/collect.ts` (`triage-events`), `src/mastra/agents/triage.ts` |
| Trigger the workflows over HTTP so a host that sleeps between ticks still works | `src/mastra/routes.ts`, `.github/workflows/supply-chain-monitor.yml` |
| Create the Web Search Agents once, from code | `scripts/setup-agents.ts` |
| Test against the package with a mock client, no network | `tests/package-behaviour.test.ts` |

This cookbook uses the package. The integration can also run over the Nimble MCP Server with
Mastra's `MCPClient`, which gives the full Nimble tool surface without the package's
developer-side controls. See the [integration docs](https://docs.nimbleway.com/integrations/connectors/mastra).

## The example app

A supply chain event monitor for three consumer electronics products that share suppliers: a
laptop, earbuds, and a smartwatch. Each product is a list of exposures (suppliers, materials,
assembly sites, freight lanes), so an event on one shared supplier reaches every product that
depends on it.

1. **Sweep** (three times a day): start one research run per product and store each `runId`.
2. **Collect** (shortly after): fetch the finished runs, save each raw result, and turn it
   into events with their own citations and confidence.
3. **Detect:** merge the same event found by several runs, and diff against what's already
   been reported.
4. **Triage:** a second Mastra agent scores each new or changed event against the watchlist.
5. **Act:** post serious, well-sourced events to Slack and rebuild a daily digest.
6. **Investigate:** in Mastra Studio, the investigator answers from what the monitor found, or
   starts a deep-dive run and collects the cited briefing in a later turn.

## Stack

- [Nimble Web Search Agents](https://docs.nimbleway.com/nimble-sdk/web-search-agents/overview): all research, with per-claim citations and confidence
- [`@nimble-way/mastra`](https://docs.nimbleway.com/integrations/connectors/mastra): the Mastra integration (start, status, and result tools)
- [Mastra](https://mastra.ai) `@mastra/core` 1.76: workflows, agents, memory, server, Studio
- [Anthropic Claude](https://www.anthropic.com) `claude-sonnet-4-6` through Mastra's model router: triage and the investigator chat
- [LibSQL](https://github.com/tursodatabase/libsql) via `@mastra/libsql` and `@libsql/client`: a local file in development, hosted Turso when deployed
- GitHub Actions: the scheduler
- TypeScript, Node.js 22.13+

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/mastra-supply-chain-monitor
npm install
cp .env.example .env
```

**Demo mode needs no keys.** With `USE_LIVE=false` (the default), the sweep starts no runs and
the collector replays real results saved in `data/samples/`, including their saved triage.
To run the real monitor, fill in `.env`:

| Variable | What it's for |
|---|---|
| `NIMBLE_API_KEY` | Every research run. Get a key at [nimbleway.com](https://online.nimbleway.com/settings/api-keys). |
| `NIMBLE_SWEEP_AGENT_ID`, `NIMBLE_DEEP_DIVE_AGENT_ID` | The two Web Search Agents. Create them once with `npm run setup-agents`, which prints both lines. |
| `ANTHROPIC_API_KEY` | The triage agent and the investigator. Set `MODEL` to use another provider Mastra supports. |
| `SLACK_WEBHOOK_URL` | Optional. A Slack incoming webhook for alerts. Unset, alerts print to the console. |
| `CRON_SECRET` | The token the scheduler sends to `/cron/*`. Generate one with `openssl rand -base64 32`. |
| `MONITOR_API_KEY` | Protects the agent API, Studio, and `/digest` on a deployed server. Leave empty locally. |

Then set `USE_LIVE=true`.

## Usage

```bash
npm run sweep      # start one research run per product (seconds)
npm run collect    # collect finished runs, triage, alert, write the digest
npm run digest     # print today's digest
npm run dev        # Mastra Studio at http://localhost:4111
```

In live mode, run `collect` a few minutes after `sweep`. A high-effort run typically takes
5–15 minutes, and `collect` reports how many runs are still working. A second `sweep` within
60 minutes of the last one is refused, so a retried or duplicated trigger can't start extra
billed runs. Pass `-- --force` to override it locally.

In Studio, the `sweep` and `collect` workflows run from the Workflows tab. The investigator
(it needs `ANTHROPIC_API_KEY`, even in demo mode) answers questions like:

- "What did the monitor find for the laptop this week, and which of it matters most?"
- "Start a deep dive on the CPU price hike: how big is the increase and what are other laptop brands doing?"
- "Is the deep dive ready?"
- "Which events touch the earbuds and the smartwatch at the same time?"

`USE_LIVE` covers the scheduled path only. A deep dive the investigator starts is a real,
billed Nimble run in either mode.

## Run it on a schedule

The workflows are triggered over HTTP, so any host plus any scheduler works. The setup this
cookbook was built for is the Mastra platform free tier, with a GitHub Actions cron:

1. **Deploy.** Run `npm run deploy` (`mastra deploy`). The first run creates the project and
   offers to attach a hosted Turso database. Accept it: the platform injects
   `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`, and the ledger lives there. Commit the
   `.mastra-project.json` it writes.
2. **Set the variables** on the environment in the Mastra dashboard: `USE_LIVE=true`,
   `NIMBLE_API_KEY`, both agent IDs, `ANTHROPIC_API_KEY`, `CRON_SECRET`, `MONITOR_API_KEY`, and
   optionally `SLACK_WEBHOOK_URL`. **Always set `MONITOR_API_KEY` on a deployed server.**
   Without it, anyone with the URL can chat with the investigator on your Nimble and model credits.
3. **Schedule.** Copy `.github/workflows/supply-chain-monitor.yml` into the root
   `.github/workflows/` of the repository that will run it. Create an environment named
   `supply-chain-monitor`, limit it to `main`, and add `MONITOR_URL` and `CRON_SECRET` as
   environment secrets.

The workflow calls `/cron/sweep` at 06:00, 14:00, and 22:00 UTC and `/cron/collect` 20, 35,
and 50 minutes after each. The server wakes about 12 times a day and sleeps the rest. Each
sweep tick collects leftovers before starting new runs, so a missed collect tick loses nothing.
GitHub may start scheduled jobs a few minutes late, and it disables schedules in a public
repository after 60 days without activity.

## Project structure

```
mastra-supply-chain-monitor/
├── src/mastra/
│   ├── index.ts              Mastra instance: agents, workflows, storage, server auth, routes
│   ├── config.ts             environment settings
│   ├── watchlist.ts          the three products and their exposures
│   ├── agents-spec.ts        both Web Search Agents: briefing, sources, output schema
│   ├── nimble.ts             every Nimble tool, configured in one place
│   ├── routes.ts             /cron/sweep, /cron/collect, /digest
│   ├── workflows/
│   │   ├── sweep.ts          plan-sweep → start-runs
│   │   └── collect.ts        fetch-results → detect-events → triage-events → act
│   ├── agents/
│   │   ├── triage.ts         severity rubric, structured output, no tools
│   │   └── investigator.ts   ledger tools + Nimble deep-dive tools, with memory
│   └── lib/
│       ├── events.ts         result → events, per-event trust, merge, diff
│       ├── ledger.ts         runs, events, leads (LibSQL)
│       └── notify.ts         Slack message and daily digest
├── scripts/                  run.ts (sweep/collect) · setup-agents.ts · digest.ts · save-samples.ts
├── tests/                    unit, package behaviour (mock client), end to end in demo mode
├── data/samples/             real results from a live sweep on 2026-10-12, plus their triage
└── .github/workflows/        the scheduler
```

## Output

Each event the example app records (`MonitoredEvent` in `src/mastra/lib/events.ts`):

| Field | Type | Description |
|---|---|---|
| `eventKey` | string | Stable ID: event type, location, and date |
| `headline` | string | One-line factual headline |
| `eventType` | string | `port_disruption`, `labor_action`, `export_control`, `tariff_or_customs`, `sanctions`, `factory_incident`, `natural_hazard`, `supplier_distress`, `route_disruption`, `material_shortage`, `other` |
| `summary` | string | What happened and what's known so far |
| `location` | string | Facility, port, city, or country |
| `eventDate` | string | ISO date it happened or takes effect |
| `status` | string | `announced`, `ongoing`, `escalating`, `easing`, `resolved` |
| `previousStatus` | string | Set when a reported event comes back with a new status |
| `expectedDuration` | string \| null | As reported, for example "2-3 weeks" |
| `impactMechanism` | string | How the event reaches the product |
| `exposures` | string[] | Watchlist exposures it touches, verbatim |
| `products` | string[] | Product slugs it reaches |
| `confidence` | `high` \| `medium` \| `low` | Lowest grade among the claims that establish the event happened |
| `citations` | object[] | `url`, `title`, `sourceType`, `sourceCategory`, `excerpts`, from `trust.claims` |
| `sourceUrl`, `publishedAt` | string | The page the event is reported on, and its date |
| `runIds` | string[] | The Nimble runs that found it |
| `triage` | object | `severity` (`critical`/`high`/`medium`/`low`), `rationale`, `recommendedAction` |

**Alerts** go to Slack for `critical` or `high` severity events whose confidence isn't `low`.
**The digest** (`data/digests/<date>.md` locally, `GET /digest` when deployed) groups the
day's new and changed events by severity, lists unconfirmed events and the runs' unverified
leads separately, and names any run that failed to start.

## Going further

- **Block for a bounded time instead:** `nimbleAgentRunResultTool({ wait: { timeoutMs, pollIntervalMs } })`
  makes the result tool wait inside one call. When the deadline passes it returns
  `{ ready: false }` and the run keeps going, so the stored-`runId` pattern still applies.
- **Mastra background tasks:** Mastra can run a tool call in the background and re-invoke the
  agent when it lands. Persist the Nimble `runId` regardless: Mastra's `taskId` can't collect a
  Nimble run after a restart.
- **Cadence:** the times live in the GitHub Actions workflow. Keep each collect tick within
  about an hour of its sweep, and keep sweeps at least `MIN_MINUTES_BETWEEN_SWEEPS` apart.
- **An always-on host:** add `schedule: { cron: "0 6,14,22 * * *" }` to `createWorkflow` in
  `sweep.ts` (and a collect schedule) and drop the GitHub Action. Never run both: every sweep
  would start, and bill, twice.
- **Effort:** the sweep runs at `high`. `medium` is faster and cheaper, at some cost to recall.
- **Sources:** `SWEEP_SOURCES` in `agents-spec.ts` is the allowlist. Remember that a domain
  left out is a domain the sweep can't read.
- **Delivery:** `notify.ts` is the only place alerts leave the app. Email, a ticket, or a
  webhook fits in the same spot.

## Requirements

- Node.js 22.13 or later (`@nimble-way/mastra` declares it)
- A Nimble account with Web Search Agents
- An Anthropic API key, or another provider Mastra supports
- For scheduled runs: a Mastra platform account (free tier works) and a GitHub repository
