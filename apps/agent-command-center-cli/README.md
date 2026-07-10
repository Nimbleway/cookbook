# Agent Command Center (CLI)

> **Cookbook Example**: A conversational Claude agent for managing a fleet of
> [Nimble Web Search Agents](https://nimble-f5a8283f-docs-task-agents-api.mintlify.app/api-reference/web-search-agents)
> via the Task Agents API — talk to it in plain English instead of clicking
> through a dashboard.

List, inspect, create (from scratch or from a template), edit, and deactivate
Nimble Web Search Agents by chatting with Claude in your terminal. Claude
calls the Task Agents API on your behalf through a small set of tools.

This agent is mostly about agent **configuration and lifecycle**, not general
run management — there's no run browsing/cancellation, and no result
retrieval beyond one narrow exception: `test_agent` (see below), which
exists specifically to ground improvement suggestions in a real result.

## What it does

- **Ask about your fleet** — "list my agents", "which ones have no sources
  configured?", "show me the GTM lead discovery agent's goals".
- **Create agents** — from scratch, or from one of Nimble's templates, with
  Claude adapting the template's goals/sources/domain-expertise to your
  specific ask rather than just copying it verbatim.
- **Edit agents** — "add a goal to X", "change Y's effort to max", "add
  TechCrunch as a source for Z".
- **Test & improve an agent** — "test the deal-sourcing agent and suggest
  improvements". Claude fires a real Nimble run (using one of the agent's own
  `suggested_questions` by default), waits for the actual result, and
  critiques the config against what really came back — a source that
  produced no citations, an output field that came back empty, a degraded/
  failed run suggesting the goals don't match what's realistically
  findable — then proposes concrete diffs and offers to apply them via
  `update_agent`. This always tells you first that it's a real run (real
  quota, up to ~2 minutes).
- **Deactivate agents** — Claude always states which agent and asks for
  explicit confirmation before deactivating; nothing is deleted, only marked
  inactive, and the confirmation gate is enforced in code, not just in the
  prompt (the deactivate tool takes a `confirmed` flag and no-ops without it).
- **First-run key setup** — on startup, it shows you any `NIMBLE_API_KEY`/
  `ANTHROPIC_API_KEY` it found (masked) and lets you accept them or paste
  different ones, optionally saving the replacement back to `.env`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY and ANTHROPIC_API_KEY
python agent.py
```

```
you> list agents that have zero sources configured
you> create an agent from the lead-enrichment template for B2B SaaS companies with 50-500 employees
you> add a goal to that one: "always include a LinkedIn URL when available"
you> deactivate the one called debug-test
```

## Configure

`.env` (see `.env.example`):

| Variable             | Required | Description                                              |
| --------------------- | -------- | ---------------------------------------------------------- |
| `NIMBLE_API_KEY`      | yes      | From online.nimbleway.com → Account Settings → API Keys   |
| `NIMBLE_BASE_URL`     | no       | Defaults to `https://sdk.nimbleway.com`                   |
| `ANTHROPIC_API_KEY`   | yes      | From console.anthropic.com                                 |

## Project structure

```
agent-command-center-cli/
├── agent.py            # The whole agent: Nimble API client, tools, system prompt,
│                       #   Anthropic tool-use loop, key onboarding, terminal REPL
├── README.md           # This file
├── ai-setup.md         # Step-by-step setup instructions for an AI agent
├── requirements.txt
└── .env.example
```

Everything lives in one file, `agent.py`, organized top to bottom in the order
it runs: the Nimble Task Agents API client, the tool definitions and
dispatcher, the system prompt, the Anthropic tool-use loop, first-run key
onboarding, then the terminal REPL. Run it with `python agent.py`.

## Tech stack

Plain `anthropic` Python SDK (tool use), `httpx` for the Nimble API, `rich`
for terminal output. No agent framework — the tool-use loop itself is about
25 lines and easy to read end to end.

## Known API behavior worth knowing

- `DELETE /v1/task-agents/{id}` deactivates, it does not delete — the config
  is preserved and still fetchable via `GET /v1/task-agents/{id}`.
- `GET /v1/task-agents` (the list endpoint) only returns **active** agents —
  a deactivated agent won't show up in `list_agents` even though `get_agent`
  can still fetch it directly by id. The system prompt tells Claude to
  mention this when relevant.
- `PATCH /v1/task-agents/{id}` expects a JSON Patch array, one op per field
  — `TaskAgentsClient.update_agent` builds this from a plain dict so the
  tools never have to think about JSON Patch.
