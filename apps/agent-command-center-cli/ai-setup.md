# AI setup guide

Instructions for an AI agent (e.g. Claude Code) setting this up for a user.

1. **Check prerequisites** — Python 3.9+ (`python3 --version`), a Nimble API
   key, and an Anthropic API key. No other services are required.

2. **Create a virtualenv and install dependencies**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Get API keys** — if the user doesn't already have them:
   - Nimble: online.nimbleway.com → Account Settings → API Keys → "+ Add Key"
   - Anthropic: console.anthropic.com → API Keys
   Do not attempt to generate either on the user's behalf.

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Set `NIMBLE_API_KEY` and `ANTHROPIC_API_KEY` in `.env`.

5. **Verify connectivity before running the full REPL** — this catches key
   issues with a clear error instead of a confusing chat failure:
   ```bash
   source .venv/bin/activate
   python3 -c "from dotenv import load_dotenv; load_dotenv(); from agent import TaskAgentsClient; print(len(TaskAgentsClient().list_agents()), 'agents found')"
   ```

6. **Run it**:
   ```bash
   source .venv/bin/activate
   python agent.py
   ```

## Common issues

- **"NIMBLE_API_KEY is not set" / "ANTHROPIC_API_KEY is not set"** — `.env`
  is missing or wasn't copied from `.env.example`.
- **A just-created agent doesn't show up when asked to list agents** —
  transient; the account may be large, or (much less likely) there's real
  API lag. Ask the agent to `get_agent` by the id it returned when it was
  created.
- **A just-deactivated agent doesn't show up in a fleet listing** — expected.
  Nimble's list endpoint only returns active agents; the deactivated agent's
  config still exists and is fetchable by id.
- **Agent creation fails with a name conflict** — `agent_name` must be
  unique across the account; ask the agent to pick a different one (it
  should already default to something reasonably unique, but shared/pooled
  accounts can still collide).
