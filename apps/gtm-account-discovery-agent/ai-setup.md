# AI setup guide

Instructions for an AI agent (e.g. Claude Code) setting this up for a user.

1. **Check prerequisites**: Python 3.10+ (`python3 --version`), a Nimble API
   key, and an Anthropic API key (used by both patterns).

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

5. **Adjust the ICP** (optional): edit `ICP_CRITERIA` and the numeric constants in
   `config.py`, and the `DISCOVERY` queries to match the new market. If you change
   `GOALS`, `SOURCES` or `OUTPUT_SCHEMA`, also change `AGENT_NAME`, because an existing
   agent with that name is reused as-is.

6. **Run it**:
   ```bash
   python agent.py                # both patterns
   python agent.py --pattern A    # Search API pipeline only
   python agent.py --pattern B    # Web Search Agent + trust gate only
   ```
   Outputs land in `artifacts/`. Pattern A makes roughly 6 + 2 per candidate
   searches and one Claude call per search step. Pattern B polls every 30s and times
   out after 45 minutes; a `high` effort run took about 8 minutes in testing.

## Common issues

- **`NimbleError` about a missing API key**: `.env` is missing or wasn't copied from `.env.example`.
- **Anthropic `not_found_error` for the model**: the key can't access `MODEL`; change it at the top of `agent.py`.
- **Pattern B returns rows that ignore an edited goal**: the agent was reused with its old configuration. Change `AGENT_NAME` and run again.
- **Pattern B `RuntimeError: ... ended as cancelled`**: the run stopped server-side. Keep `EFFORT = "high"`; `x-high` runs of this task were cancelled in testing.
- **Pattern B `TimeoutError`**: the run is still going on Nimble's side. Raise `timeout` in `run_agent_api()`.
