# Cookbook page fields — Deal Monitor

Use these fields for the manual Webflow cookbook page.

## Category pill

Live Web Alerts

## Title

Deal Monitor

## Hero copy

Watch any live-web query and get a Slack alert when something new appears.

## Subcopy

A small LangChain/LangGraph app that uses Nimble Search to monitor the web, filter out results it has already seen, summarise new matches with an OpenRouter-compatible model, and post the digest to Slack.

## Who this is for

Built for GTM, DevRel, investing, product, and competitive-intelligence teams that need alerts when the web changes.

## Quick start cards

### Get a Nimble API key

Create a Nimble account and add your API key to `.env`.

### View the repo

Open `langchain/deal_monitor` in the Nimble Cookbook repository.

### Open in Claude Code

Optional: open the folder in Claude Code and use `CLAUDE.md` as the setup/context prompt.

## Inputs

- Monitoring query, for example `developer tools funding news this week`
- Nimble API key
- OpenRouter-compatible LLM API key
- Slack Incoming Webhook URL
- Optional Nimble search settings: focus, time range, depth, result count, locale, and country

## Outputs

- New web results matching the query
- Deduplicated URL list using local `.state.json`
- Short Slack-ready summary of only new matches
- Slack alert when new results appear
- Local state so future runs only alert on new items

## Flexible callout

Dry-run included: Run the full graph without external API calls. The dry-run shows the search, filter, summary, Slack notification, and state-persistence flow without writing `.state.json`.

## Time / complexity cue

Runs locally in under 5 minutes. Requires Nimble, Slack, and an OpenRouter-compatible LLM key for live mode. Dry-run needs no keys.

## How it works

1. Load the monitoring query and environment settings.
2. Run a live web search with Nimble Search.
3. Normalize the returned search results.
4. Compare result URLs against the local seen-list.
5. Summarise only the new results with an OpenRouter-compatible chat model.
6. Send the digest to Slack.
7. Persist the seen-list for the next run.

## Stack

### Nimble

- `langchain-nimble`
- `NimbleSearchTool`
- live web search data

### Runtime

- Python
- LangChain
- LangGraph
- OpenRouter-compatible chat model
- Slack Incoming Webhook
- local JSON state file

## Visual suggestion

Use a terminal screenshot or short clip showing:

1. `python3 agent.py --dry-run`
2. `Found 1 new result(s)`
3. `DRY RUN: would send Slack alert`
