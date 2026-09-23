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

5. **Run it**:
   ```bash
   python agent.py
   ```
   Outputs land in `artifacts/`. Pattern B polls every 15s and times out after
   30 minutes.

## Common issues

- **`KeyError: 'NIMBLE_API_KEY'`**: `.env` is missing or wasn't copied from `.env.example`.
- **Anthropic `not_found_error` for the model**: the key can't access `MODEL`; change it at the top of `agent.py`.
- **Pattern B `TimeoutError`**: the run is still going on Nimble's side. Raise `timeout` in `run_agent_api()` or lower `EFFORT`.
