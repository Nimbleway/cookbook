# live-docs-grounding-agent — Live Docs Grounding Agent

Answers software library and API usage questions by grounding them in current official documentation, changelogs, and release notes — powered by [Nimble](https://nimbleway.com)'s Task Agents API.

## What it does

1. **Ask** — type a natural-language question about a library, framework, or API
2. **Search** — a Nimble Web Search Agent searches only official docs, GitHub release notes, and changelogs for the current answer instead of relying on stale training data
3. **Ground** — returns a structured answer that calls out breaking changes and migration notes when relevant
4. **Cite** — always includes a working code snippet and at least one citation URL
5. **Log** — every completed question is saved to a local history you can browse, view, or delete

## Stack

- [Nimble Task Agents API](https://nimbleway.com) — a Web Search Agent scoped to official docs, GitHub release notes, and changelogs
- Python — the CLI, HTTP client, terminal rendering, and history storage
- [httpx](https://www.python-httpx.org/) — REST calls to the Task Agents API
- [python-dotenv](https://pypi.org/project/python-dotenv/) — loads the Nimble API key from `.env`

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/live-docs-grounding-agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**2. Run it**

```bash
.venv/bin/python agent.py
```

First run asks for your Nimble API key, creates the agent in your workspace, and drops you into an interactive question loop. Get a key at [online.nimbleway.com](https://online.nimbleway.com).

## Usage

```bash
.venv/bin/python agent.py "What's the current way to stream responses in the OpenAI Python SDK v1.x?"
```

Type `quit` (or press Ctrl+C) at any point while a question is running to cancel it. In the interactive loop, type `history` to browse past questions, or `history delete <n>` to remove one — the same commands also work directly: `python agent.py history` / `python agent.py history <n>` / `python agent.py history delete <n>`.

## Editing the agent's domain

`agent_config.json` holds everything the agent knows: domain expertise, goals, the allowed doc/changelog sources, effort tier, and the output schema. Edit it and re-run with `--reset` to push the change to the live agent — that's all it takes to point this same code at a different domain entirely (e.g. answering questions about a different kind of documentation).

## Project structure

```
live-docs-grounding-agent/
├── agent.py            # Everything: Task Agents API client, CLI, history, terminal rendering
├── agent_config.json    # Editable agent definition (domain, sources, effort, output schema)
├── requirements.txt
└── .env.example
```
