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

This installs httpx, python-dotenv, fastapi, and uvicorn.

---

## Step 4: Get a Nimble API key

Ask the user if they already have a Nimble API key.

**If they have one already** — ask them to have it ready to paste into the web app in the next step.

**If they don't** — direct them to:
1. Go to https://online.nimbleway.com and log in (or sign up free)
2. Click their profile icon -> Account Settings -> API Keys
3. Click "Create New API Key" and copy it (shown only once)

---

## Step 5: Run it

```bash
.venv/bin/python app.py
```

This starts a local web server and prints its URL (`http://127.0.0.1:8420`). Tell the user to open that URL in their browser.

First run shows an animated setup sequence: it prompts for the API key in the browser, validates it, and creates the Web Search Agent in the user's workspace — each step completes visibly before the next starts. On return visits it reconnects automatically and skips straight to the question screen.

---

## Step 6: Ask a question

In the browser, type any question about a software library, framework, or API into the input box — for example:

```
What's the current way to stream responses in the OpenAI Python SDK v1.x?
```

Click **Ask** (or press Enter). The agent searches official docs and changelogs and the answer animates in below the question, with a citation URL and a working code snippet. A 📜 icon in the top bar opens past questions; a **Cancel** button appears while a question is running.

A terminal-only CLI is also still available (`.venv/bin/python agent.py`) if the user prefers scripting it instead of the browser.
