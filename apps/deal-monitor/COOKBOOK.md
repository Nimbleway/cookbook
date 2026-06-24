# Deal Monitor Cookbook

This app is intentionally small so developers can fork it quickly.

## The basic pattern

```text
search live web -> filter seen URLs -> summarize new items -> notify -> persist state
```

That pattern works for many monitoring jobs:

- funding announcements
- competitor launches
- acquisition news
- pricing/page changes
- regulatory updates
- hiring signals
- product mentions

## Change 1: the query

Set `MONITOR_QUERY` in `.env`:

```bash
MONITOR_QUERY=developer tools funding news this week
```

Or pass it directly:

```bash
python3 agent.py --query "new vector database launches this week"
```

## Change 2: Nimble search settings

The demo defaults to news-oriented recent search:

```bash
NIMBLE_SEARCH_FOCUS=news
NIMBLE_SEARCH_TIME_RANGE=week
```

If you want broader web monitoring, change the focus/time-range values supported by your Nimble account and `langchain-nimble` version.

## Change 3: the output

The notification step lives in `notify_slack()` inside `agent.py`.

Replace that function to send the digest somewhere else:

- email
- Discord
- Telegram
- a database row
- a JSON file
- a webhook endpoint

The rest of the graph can stay the same.

## Add scoring

For noisy queries, add a scoring node between `filter_seen` and `summarize_results`:

```text
fetch_news -> filter_seen -> score_results -> summarize_results -> notify_slack -> persist_state
```

A scoring node can rank by:

- keyword match
- company stage
- source authority
- geography
- recency
- dollar amount
- competitor name

## Add LangSmith tracing

Set these values in `.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=nimble-deal-monitor
```

LangGraph and LangChain calls will then be visible in LangSmith for debugging and demos.

## Production notes

This app uses `.state.json` because a flat file keeps the demo easy to understand.

For production, swap it for:

- Redis for short-lived monitoring state
- Postgres for team-visible history
- S3/GCS for cheap append-only archives

Also consider:

- deduping by canonical URL
- adding alert severity levels
- rate-limiting Slack alerts
- storing raw Nimble results for auditability
- adding retries around external network calls
