# Deal Monitor

A small LangChain/LangGraph agent that watches a live web search query and posts a Slack alert when new results appear.

Built with [Nimble Web Search Agents](https://nimbleway.com) via `langchain-nimble`. This cookbook lives in `langchain/deal_monitor/` in the Nimble Cookbook repo. Change the query and it becomes a funding monitor, competitor tracker, acquisition watcher, pricing monitor, or industry-alert bot.

---

## What it does

1. Runs a configurable live web search with Nimble's LangChain integration: `NimbleSearchTool`
2. Saves the raw Nimble response before transformation
3. Normalizes the returned search results
4. Compares result URLs against a local `.state.json` seen-list
5. Summarizes only the new results with an OpenRouter-compatible chat model
6. Sends the digest to Slack with an Incoming Webhook
7. Persists the seen-list so the next run only alerts on genuinely new matches

Designed to run on a cron every few hours. No database or hosted infrastructure required.

---

## Quickstart

```bash
cd langchain/deal_monitor
pip install -r requirements.txt
cp .env.example .env
# Add your Nimble, OpenRouter, and Slack webhook credentials
python3 agent.py --dry-run
python3 agent.py
```

---

## Configure

Edit `.env`:

```bash
NIMBLE_API_KEY=your_nimble_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
MONITOR_QUERY=developer tools funding news this week
```

Optional:

```bash
NIMBLE_SEARCH_FOCUS=news
NIMBLE_SEARCH_TIME_RANGE=week
NIMBLE_SEARCH_DEPTH=lite
NIMBLE_NUM_RESULTS=10
NIMBLE_INCLUDE_ANSWER=false
NIMBLE_SEARCH_LOCALE=en
NIMBLE_SEARCH_COUNTRY=US
NIMBLE_OUTPUT_FORMAT=markdown
OPENROUTER_MODEL=google/gemma-3-27b-it:free
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=nimble-deal-monitor
```

---

## Example queries

```bash
MONITOR_QUERY=fintech Series A this week
MONITOR_QUERY=climate tech seed round announced
MONITOR_QUERY=enterprise SaaS acquisition 2026
MONITOR_QUERY=developer tools funding news
MONITOR_QUERY=competitor product launch announcement
```

You can also pass the query directly:

```bash
python3 agent.py --query "AI infrastructure startup funding this week"
```

---

## Graph structure

```text
fetch_news -> filter_seen -> summarize_results -> notify_slack -> persist_state
```

Each node is a plain Python function. LangGraph wires the nodes together and passes typed state between them.

---

## Project structure

```text
langchain/deal_monitor/
├── agent.py          # LangGraph monitor agent
├── CLAUDE.md         # Claude Code setup/context prompt
├── WEBFLOW.md        # Cookbook page fields for Webflow
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Stack

| Layer | Tool |
|---|---|
| Live web data | Nimble `NimbleSearchTool` via `langchain-nimble` |
| Orchestration | LangGraph `StateGraph` |
| LLM summary | OpenRouter-compatible chat model via `langchain-openai` |
| State | Local `.state.json` file |
| Notifications | Slack Incoming Webhook |
| Optional tracing | LangSmith |

---

## Run on a cron

Example: run every 6 hours.

```cron
0 */6 * * * cd /path/to/cookbook/langchain/deal_monitor && /path/to/venv/bin/python agent.py >> monitor.log 2>&1
```

The app only sends a Slack message when it finds new results.
