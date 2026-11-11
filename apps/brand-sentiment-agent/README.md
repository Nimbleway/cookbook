# brand-sentiment-agent

A **LangChain agent** that turns scattered reviews, community discussion, and news
coverage into a ranked list of sentiment themes that are getting worse, using **Nimble**
for web data. Give it a brand name; it finds and classifies items across source classes,
then a deterministic step (not the LLM) dedupes them, splits them into a current and a
prior time window, drops any theme below a minimum sample size, and flags themes whose
negative volume rose beyond a threshold since the prior window.

| File | Pattern | Who runs the research loop |
| --- | --- | --- |
| `agent.py` / `run.py` | **A** - LangChain + Nimble Search API | the LangChain agent |
| `agent_api_v2.py` | **B** - Nimble Web Search Agent (Agent API) | Nimble |

Both patterns produce the same `SentimentExtractionBatch` shape (items + the canonical
theme labels the run defined), so `sentiment_model.build_result` is identical downstream.
Only the retrieval step changes.

## Why the counting is not the LLM's job

Asked to just "summarize sentiment," an LLM will confidently report a theme built on
three reviews as if it were a trend, and will average review-platform text into a single
sentiment percentage as if it represented all customers. `sentiment_model.py` does the
counting in plain Python instead:

- **Dedupe** on normalized text + date, so a syndicated review appearing on two
  aggregator sites is not counted twice.
- **Minimum sample size** (`MIN_SAMPLE_SIZE`, default 4): a theme with fewer current-window
  items than that goes to `insufficient_volume` and is never reported as a finding.
- **Current vs prior window comparison**: items are bucketed by their extracted date into
  two windows (`--window-days`, default 90 each), and negative-volume change is computed
  per theme, not felt.
- **Escalation threshold** (`ESCALATION_THRESHOLD_PCT`, default 25%): only themes whose
  negative volume rose past that make the triage list; everything else lands in the full
  theme table.

The agent's job is narrower than it looks: find items, date them accurately (including
converting relative dates like "2 weeks ago" to absolute ones), and classify each into a
small set of theme labels it defines once per run and reuses consistently.

## Run

```bash
uv sync
cp .env.example .env       # NIMBLE_API_KEY + an LLM_MODEL and its key

uv run python run.py "Chipotle" --window-days 90
uv run python agent_api_v2.py "Chipotle" --window-days 90
```

`LLM_MODEL` is provider-agnostic via `init_chat_model`: `openai:gpt-5.1` (default),
`anthropic:claude-sonnet-5`, ... Install the matching provider package.

Both entrypoints also write `dashboard.html` to `./output` (or `--out-dir`) and open it
in the default browser (skip with `--no-dashboard`): current-vs-prior negative volume
per theme with escalation flagged, and the full theme table.

## Files

- `schema.py` - `ReviewItem`, `SentimentExtractionBatch` (the agent's raw output),
  `ThemeRow`, `SentimentResult` (the final triage output).
- `sentiment_model.py` - dedupe, windowing, minimum sample, and escalation logic. No LLM
  calls.
- `config.py` - the extraction agent's role and system-prompt builder. Instructs the
  agent to search with explicit recency signals, since a query with no recency term
  skews toward old, highly-upvoted threads and starves the current window of volume.
- `agent.py` - the Pattern A LangChain agent and its `nimble_search` tool.
- `agent_api_v2.py` - the Pattern B driver.
- `run.py` - Pattern A CLI and the shared result printer.
- `dashboard.py` - writes the self-contained `dashboard.html` artifact both entrypoints
  open after a run.

## Example

`examples/chipotle_result.json` - a real run: 43 items considered across Reddit,
Trustpilot, and news coverage, 2 escalated themes ("Portions, Value & Pricing" up 400%
negative volume vs the prior window, "Menu Changes & Limited-Time Items" newly
appearing) each with real sourced quotes, and 4 themes correctly held back for
insufficient volume rather than reported as thin findings.
