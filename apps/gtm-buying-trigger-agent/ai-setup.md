# AI setup guide

Instructions for an AI agent (e.g. Claude Code) setting this up for a user.

1. **Check prerequisites**: Python 3.10+ (`python3 --version`), a Nimble API
   key, and an Anthropic API key (Pattern A only).

2. **Create a virtualenv and install dependencies**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Get API keys** if the user doesn't have them:
   - Nimble: online.nimbleway.com → Account Settings → API Keys
   - Anthropic: console.anthropic.com → API Keys

   Do not try to generate either key for the user.

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Set `NIMBLE_API_KEY` and `ANTHROPIC_API_KEY` in `.env`.

5. **Set the watchlist** (optional): edit `WATCHLIST` in `config.py`. Give each account
   its `domain` and a short `descriptor` (e.g. "cybersecurity") that is added to every
   search. Edit `SELLER_CONTEXT` to describe what the user sells.

6. **Run it**:
   ```bash
   python agent.py                # both patterns
   python agent.py --pattern A    # Search API only
   python agent.py --pattern B    # Web Search Agent only
   ```
   Outputs land in `artifacts/`. Pattern A makes 3 searches and one Claude call per
   account. Pattern B polls every 30s and times out after 45 minutes; a `high` effort
   run on five accounts took about 5 minutes on 2026-10-12.

## Common issues

- **`NimbleError` about a missing API key**: `.env` is missing or wasn't copied from `.env.example`.
- **Anthropic `not_found_error` for the model**: the key can't access `MODEL`; change it at the top of `agent.py`.
- **Search results about another company with the same name**: make the account's `descriptor` more specific (a product or market name).
- **Pattern B prints `create with goals rejected`**: the agent is created with the goals in its skill text instead; nothing to fix.
- **Pattern B returns rows that ignore an edited goal**: the agent was reused with its old configuration. Change `AGENT_NAME` and run again.
- **Pattern B `TimeoutError`**: the run is still going on Nimble's side. Raise `timeout` in `run_agent_api()`.
