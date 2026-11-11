# AI setup guide

Instructions for an AI agent (e.g. Claude Code) setting this up for a user.

1. **Check prerequisites**: Python 3.12+ (`python3 --version`), a Nimble API
   key, and an API key for the LLM provider named in `LLM_MODEL` (Pattern A only;
   defaults to OpenAI).

2. **Install dependencies**, either with uv (preferred, uses the lockfile):
   ```bash
   uv sync
   ```
   or with pip:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   For a non-OpenAI model, also install its LangChain package
   (e.g. `langchain-anthropic` for `anthropic:...`).

3. **Get API keys** if the user doesn't have them:
   - Nimble: online.nimbleway.com → Account Settings → API Keys
   - LLM provider: the provider's console (e.g. platform.openai.com → API keys)

   Do not try to generate either key for the user.

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Set `NIMBLE_API_KEY`, `LLM_MODEL`, and the matching provider key in `.env`.

5. **Run it**:
   ```bash
   # Pattern A: LangChain agent + Nimble Search
   uv run python run.py "Chipotle" --window-days 90
   # Pattern B: Nimble Web Search Agent (no LLM in the loop)
   uv run python agent_api_v2.py "Chipotle" --window-days 90
   ```
   Outputs (the theme triage output and `dashboard.html`) land in `./output` (override with `--out-dir`).
   The dashboard opens in the default browser; pass `--no-dashboard` to skip it.

## Common issues

- **Missing `NIMBLE_API_KEY`**: `.env` is missing or wasn't copied from `.env.example`.
- **`ImportError` for a provider package**: install the LangChain package matching `LLM_MODEL`.
- **Pattern A stops with a recursion error**: raise `AGENT_RECURSION_LIMIT` in `.env`.
