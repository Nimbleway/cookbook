# AI Setup Instructions — Live Docs Grounding Agent

You are helping the user set up and run the Live Docs Grounding Agent. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/live-docs-grounding-agent
```

---

## Step 3: Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

This installs httpx (the HTTP client for the Task Agents API) and python-dotenv (loads the API key from `.env`).

---

## Step 4: Get a Nimble API key

Ask the user if they already have a Nimble API key.

**If they have one already** — ask them to paste it when prompted in the next step.

**If they don't** — direct them to:
1. Go to https://online.nimbleway.com and log in (or sign up free)
2. Click their profile icon -> Account Settings -> API Keys
3. Click "Create New API Key" and copy it (shown only once)

---

## Step 5: Run it

```bash
.venv/bin/python agent.py
```

This validates the API key, saves it to a local `.env` (gitignored), creates the Web Search Agent in the user's Nimble workspace, and drops into an interactive question loop.

---

## Step 6: Ask a question

At the `Question (...)` prompt, type any question about a software library, framework, or API — for example:

```
What's the current way to stream responses in the OpenAI Python SDK v1.x?
```

The agent searches official docs and changelogs and returns a structured answer with a citation URL and a working code snippet. Typing `history` shows past questions. Typing `quit` (or pressing Ctrl+C) while a question is running cancels it.
