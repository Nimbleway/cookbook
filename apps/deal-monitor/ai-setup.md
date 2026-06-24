# AI Setup Instructions — Deal Monitor

You are helping the user set up and run the Deal Monitor — a LangChain/LangGraph agent that watches a live web search query and posts a Slack alert when new results appear. It uses Nimble's `NimbleSearchTool` for live web data, OpenRouter for summarization, and persists a local seen-list so each run only alerts on genuinely new matches. Follow these steps in order. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**git**
```bash
git --version
```
If missing: direct the user to https://git-scm.com

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls nimble-data-apps
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd nimble-data-apps
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/nimble-data-apps
cd nimble-data-apps
```

---

## Step 3: Install dependencies

```bash
cd deal-monitor
pip install -r requirements.txt
```

This installs: `langchain-core`, `langchain-openai`, `langgraph`, `langchain-nimble`, `python-dotenv`, `requests`.

---

## Step 4: Get API keys

Ask the user which keys they already have.

**Nimble API key** — used for live web searches via `NimbleSearchTool`
Get one at: https://nimbleway.com

**OpenRouter API key** — used to summarize new results before posting to Slack
Get one at: https://openrouter.ai/keys
Tell the user: the default model is `google/gemma-3-27b-it:free` — free tier, no cost. Swap via `OPENROUTER_MODEL` in `.env`.

**Slack Incoming Webhook URL** — used to post the digest when new results are found
Get one at: https://api.slack.com/messaging/webhooks (create an app → add Incoming Webhooks)
Tell the user: this is required for live runs. Dry-run mode skips the Slack step entirely.

---

## Step 5: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's keys:
```
NIMBLE_API_KEY=their_nimble_key_here
OPENROUTER_API_KEY=their_openrouter_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/their/webhook/url
```

Set the search query (the thing to monitor):
```
MONITOR_QUERY=developer tools funding news this week
```

Example queries:
- `fintech Series A this week`
- `climate tech seed round announced`
- `enterprise SaaS acquisition 2026`
- `competitor product launch announcement`

Optionally adjust search settings:
```
NIMBLE_SEARCH_FOCUS=news        # news | social | general
NIMBLE_SEARCH_TIME_RANGE=week   # day | week | month
```

---

## Step 6: Run a dry-run first

From inside `deal-monitor/`:

```bash
python3 agent.py --dry-run
```

Tell the user: dry-run mode skips all external API calls and simulates the full graph flow with a sample result. Expected output:
```
DRY RUN: would search Nimble for: <your query>
Found 1 new result(s)
DRY RUN: would send Slack alert: ...
DRY RUN: state not written
```

If this output looks correct, proceed to Step 7.

---

## Step 7: Run live

```bash
python3 agent.py
```

The agent will:
1. Search Nimble for the query
2. Filter out any URLs already in `.state.json`
3. Summarize new results with the OpenRouter model
4. Post the digest to Slack
5. Save seen URLs so the next run skips them

Tell the user: if no new results are found, no Slack message is sent and `.state.json` is not updated.

You can also pass the query directly without editing `.env`:
```bash
python3 agent.py --query "AI infrastructure startup funding this week"
```

---

## Step 8: Set up a cron (optional)

To run the monitor automatically every 6 hours:

```bash
crontab -e
```

Add this line (update the path to match where the repo is cloned):
```cron
0 */6 * * * cd /path/to/nimble-data-apps/deal-monitor && python3 agent.py >> monitor.log 2>&1
```

The agent only sends a Slack message when it finds new results, so frequent runs stay quiet.

---

## Notes

- `.state.json` is the local seen-list — gitignored, lives in `deal-monitor/`. Delete it to reset the monitor and re-alert on all current results.
- `monitor.log` captures output from cron runs — also gitignored.
- To add LangSmith tracing, set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY=your_key` in `.env`. All LangGraph and LangChain calls will appear in the LangSmith dashboard.
- See `COOKBOOK.md` for how to swap the Slack step for email/Discord/webhook, add a scoring node, or adapt the query for different monitoring jobs.
