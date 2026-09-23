# Company and Industry Event Monitoring Agent

> **Cookbook Example**: one news-monitoring use case, built two ways on Nimble:
> a LangChain agent over the Search API, and a direct Web Search Agent run.

Researches the most important developments for a company over the past 30 days (product launches, partnerships, leadership changes, legal and regulatory news, and competitive moves) and ranks them by significance with cited evidence. Ships configured for OpenAI.

## Two patterns, one task

| | Pattern A: LangChain + Search API | Pattern B: Web Search Agent |
| --- | --- | --- |
| Who does the research | A `create_agent` Claude agent calling `nimble_search` / `nimble_extract` | Nimble's Web Search Agent |
| LLM in your loop | Yes (Anthropic) | No, just run → poll → fetch in Python |
| Recency | Enforced in the tool: `nimble_search` is wrapped so `start_date`/`end_date` are fixed to the last 30 days and the model can't override them | Stated in the task |
| Output | `artifacts/company_event_monitoring_agent__pattern_A.md` | `artifacts/company_event_monitoring_agent__pattern_B.json` (content + trust) and `.md` |

Both patterns share the same task, skill, goals, and source guidance, so you can
compare their outputs directly. Each item carries: `event, type, relevance, date, significance, source_url`.

### Why the date lock

Models fill in search date filters from their training prior, so "the past 30
days" in a prompt often turns into a date range from last year. Pattern A wraps
`nimble_search` so the date window is computed from `date.today()` and passed
on every call. The model only supplies the query, so every result it can
retrieve is from the window.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NIMBLE_API_KEY and ANTHROPIC_API_KEY
python agent.py        # runs Pattern A, then Pattern B
```

To run one pattern only:

```bash
python -c "import agent; agent.run_search_api_agent()"   # Pattern A
python -c "import agent; agent.run_agent_api()"          # Pattern B
```

## Configure

| Variable | Required | Description |
| --- | --- | --- |
| `NIMBLE_API_KEY` | yes | From online.nimbleway.com → Account Settings → API Keys |
| `ANTHROPIC_API_KEY` | Pattern A | From console.anthropic.com |

Constants at the top of `agent.py`:

- `MODEL`: Claude model for Pattern A (default `claude-sonnet-4-6`)
- `EFFORT`: Web Search Agent effort for Pattern B: `low` | `medium` | `high` | `x-high` | `max` (default `high`)
- `AGENT_TASK`, `SKILL`, `GOALS`, `SOURCE_HINTS`, `OUTPUT_FIELDS`: the use case

Swap the company by editing `AGENT_TASK` (and `AGENT_NAME` if you want a separate Web Search Agent per company).

## Example

Real runs from 2026-09-23, covering OpenAI developments for 24 Aug – 23 Sep 2026:

- `examples/company_event_monitoring_agent__pattern_A.md`: Pattern A (`claude-sonnet-4-6`)
- `examples/company_event_monitoring_agent__pattern_B.md` / `.json`: Pattern B (`effort=high`); the JSON includes the run metadata and `trust` block

These are illustrative model output, committed to show the shape of a result and kept
as they came back from the run. Treat every claim in them as an example of the
pipeline's output, not as verified research. Re-run the agent for current findings
before relying on any of it.

## Project structure

```
company-event-monitoring-agent/
├── agent.py          # Use case config, Pattern A (LangChain) and Pattern B (Web Search Agent)
├── examples/         # Committed sample outputs from a real run
├── README.md
├── ai-setup.md       # Setup steps for an AI coding agent
├── requirements.txt
└── .env.example
```
