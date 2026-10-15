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

5. **Pick the account** (optional): edit `COMPANY_NAME`, `DOMAIN`, the query strings
   in `PASSES` and the domain in `AGENT_INPUT` in `config.py`. The default is
   `eve.legal`.

6. **Run it**:
   ```bash
   python agent.py                # both patterns
   python agent.py --pattern A    # Search API only
   python agent.py --pattern B    # Web Search Agent only
   ```
   Outputs land in `artifacts/`. Pattern B polls every 15s and times out after
   30 minutes; a `high` effort run took about 3 minutes in testing.

## Common issues

- **`NimbleError` about a missing API key**: `.env` is missing or wasn't copied from `.env.example`.
- **Anthropic `not_found_error` for the model**: the key can't access `MODEL`; change it at the top of `agent.py`.
- **A Pattern A pass prints `search failed`**: the other passes still run and the failure is recorded in the artifact's `searches` list. Re-run, or change that pass's parameters in `PASSES`.
- **Pattern B `TimeoutError`**: the run is still going on Nimble's side. Raise `timeout` in `run_agent_api()` or lower the effort with `--effort medium`.
- **Pattern B `RuntimeError: ... ended as cancelled`**: the run stopped server-side. Run it again at `high`.
