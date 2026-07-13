# live-docs-grounding-agent — Live Docs Grounding Agent

Answers software library and API usage questions by grounding them in current official documentation, changelogs, and release notes — powered by [Nimble](https://nimbleway.com)'s Task Agents API. Ships as a local web app with animated onboarding, a live-updating answer feed, and mid-run cancellation.

## What it does

1. **Ask** — type a natural-language question about a library, framework, or API
2. **Search** — a Nimble Web Search Agent searches only official docs, GitHub release notes, and changelogs for the current answer instead of relying on stale training data
3. **Ground** — returns a structured answer that calls out breaking changes and migration notes when relevant
4. **Cite** — always includes a working code snippet and at least one citation URL
5. **Log** — every completed question is saved to a local history you can browse, view, or delete

## Stack

- [Nimble Task Agents API](https://nimbleway.com) — a Web Search Agent scoped to official docs, GitHub release notes, and changelogs
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) — local web server exposing the agent as JSON endpoints
- Vanilla HTML/CSS/JS — the frontend, no build step
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
.venv/bin/python app.py
```

This prints the local URL (`http://127.0.0.1:8420`) and starts the server. Open it in your browser — first run walks you through pasting your Nimble API key and creating the agent, with the setup steps shown live on screen. Get a key at [online.nimbleway.com](https://online.nimbleway.com).

On return visits with an existing key and agent, it reconnects automatically and drops you straight into the question screen.

## Usage

Type a question in the box (or click one of the suggested-question chips) and press Enter or **Ask**. The answer streams in as a card below the question, with a live progress indicator while the run is in progress and a **Cancel** button to stop it early. Answers render as formatted text with a code block and clickable citation links — never raw JSON.

The suggested-question chips under the ask box are **today's picks** — a date-seeded rotating subset of a curated pool in `question_pool.json`. They change every day (and are the same for everyone on a given day); edit `question_pool.json` to keep the pool current.

Click **★ Save** on any answer to bookmark it. The 📜 icon opens a side panel with two tabs: **History** (every question, auto-logged) and **Saved** (your bookmarks). A saved answer is a full independent snapshot — it stays reopenable any day, even after you clear it from history. Click ⚙ → **Re-run setup** to replay the onboarding sequence (e.g. for a demo) — it re-checks the agent for real rather than faking the animation.

### CLI (still available)

The original terminal interface still works, unchanged, if you'd rather script it or use it headless:

```bash
.venv/bin/python agent.py                    # interactive terminal loop
.venv/bin/python agent.py "your question"    # ask one question directly
.venv/bin/python agent.py history            # browse history
.venv/bin/python agent.py --reset            # force re-setup
```

## Editing the agent's domain

`agent_config.json` holds everything the agent knows: domain expertise, goals, the allowed doc/changelog sources, effort tier, and the output schema. Edit it, then either click **Re-run setup** in the web app or run `python agent.py --reset` to push the change to the live agent — that's all it takes to point this same code at a different domain entirely (e.g. answering questions about a different kind of documentation).

## Project structure

```
live-docs-grounding-agent/
├── app.py               # Entry point: python app.py (starts the web server)
├── server.py            # FastAPI endpoints — orchestrates agent.py's client, no new Task Agents API calls
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js           # Onboarding sequence, ask/poll/render flow, history panel
├── agent.py              # Task Agents API client, config loading, history, and the original CLI
├── agent_config.json     # Editable agent definition (domain, sources, effort, output schema)
├── question_pool.json    # Curated pool the app rotates a daily subset from for suggested questions
├── requirements.txt
└── .env.example
```
