# live-docs-grounding-agent — Live Docs Grounding Agent

Answers software library and API usage questions by grounding them in current official documentation, changelogs, and release notes — powered by [Nimble](https://nimbleway.com)'s Task Agents API. Ships as a local web app with animated onboarding, a live-updating answer feed, and mid-run cancellation.

> **Runs entirely on your own machine.** `python app.py` starts a web server bound to `127.0.0.1` (localhost/loopback) — it is reachable only from your own computer, is not exposed to your network or the internet, and needs no login. Each person who clones this repo runs their own private instance with their own Nimble API key; it is not a shared or hosted service. Your key is stored only in a local, gitignored `.env` and never leaves your machine.

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

### Prerequisites

- **Python 3.9 or newer** — check with `python3 --version`. If you don't have it, get it at [python.org/downloads](https://python.org/downloads).
- **A Nimble API key** — free to create. In the browser: go to [online.nimbleway.com](https://online.nimbleway.com), log in or sign up, then **profile icon → Account Settings → API Keys → Create New API Key**. Copy it (it's shown only once). You'll paste it into the app on first run — you do **not** put it in any file by hand.
- An open port **8420** on your machine (that's the fixed local port the app uses).

### Step by step

**1. Clone the repo and enter the app folder**

Everything runnable lives in the `agent/` subfolder — `cd` into it.

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/live-docs-grounding-agent/agent
```

**2. Create an isolated Python environment**

```bash
python3 -m venv .venv
```

**3. Install the dependencies into it**

```bash
.venv/bin/pip install -r requirements.txt
```

(On Windows the path is `.venv\Scripts\pip` instead of `.venv/bin/pip`, and `.venv\Scripts\python` below.)

**4. Start the app**

```bash
.venv/bin/python app.py
```

You'll see it print:

```
📚 Live Docs Grounding Agent
   http://127.0.0.1:8420
```

**5. Open that URL in your browser** — `http://127.0.0.1:8420`.

**6. Complete the on-screen setup (first run only).** The app plays a short animated setup sequence: it asks you to paste your Nimble API key, validates it live, and creates the agent in your Nimble workspace — each step completes on screen before the next begins. Your key is saved to a local, gitignored `.env` so you're not asked again.

**7. Ask a question.** Type into the box (or click one of the suggested-question chips) and press Enter. You're done.

On every later run, just repeat steps 4–5 — it detects your saved key and agent, shows a brief "Reconnecting…" beat, and drops you straight into the question screen. Stop the server any time with `Ctrl+C` in the terminal.

### Troubleshooting

- **`address already in use` / port 8420 busy** — something else is already using that port (often a previous copy of this app still running). Stop the other process, or change `PORT` near the top of `app.py`.
- **Key rejected (401)** — the key was mistyped or revoked. Re-run setup from the ⚙ menu and paste it again.
- **Nothing at the URL** — make sure the `python app.py` terminal is still running; the server only serves while that command is active.

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
├── README.md
├── AGENT_SETUP.md
└── agent/                  # everything runnable lives here — cd here to run
    ├── app.py              # Entry point: python app.py (starts the web server)
    ├── server.py           # FastAPI endpoints — orchestrates agent.py's client, no new Task Agents API calls
    ├── agent.py            # Task Agents API client, config loading, history, and the original CLI
    ├── agent_config.json   # Editable agent definition (domain, sources, effort, output schema)
    ├── question_pool.json  # Curated pool the app rotates a daily subset from for suggested questions
    ├── requirements.txt
    ├── .env.example
    └── static/
        ├── index.html
        ├── style.css
        └── app.js          # Onboarding sequence, ask/poll/render flow, history + saved panel
```
