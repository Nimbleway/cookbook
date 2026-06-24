# Cookbook page fields — Consumer Sentiment Monitor

Use these fields for the manual Webflow cookbook page.

## Category pill

Launch Intelligence

## Title

Consumer Sentiment Monitor

## Hero copy

Track launch sentiment from live web sources and turn it into a dashboard your team can act on.

## Subcopy

A Streamlit data app that uses Nimble Search to collect social, Reddit, review/comparison, and news coverage around a product launch, then turns the results into sentiment buckets, risk signals, representative links, and follow-up searches.

## Who this is for

Built for product marketing, DevRel, growth, and launch teams that need to understand how the market is reacting across live web sources.

## Quick start cards

### Run sample dashboard

Open the bundled sample report without an API key.

### Collect live data

Add a Nimble API key and run the collector against your product config.

### Open in Claude Code

Optional: open the folder in Claude Code and use `CLAUDE.md` as the setup/context prompt.

## Inputs

- Product name
- Launch context
- Country and locale
- Search depth and result count
- Query plan covering social, Reddit, reviews/comparison, and news/blog coverage
- Nimble API key for live mode

## Outputs

- Raw Nimble responses saved before parsing
- Normalized source-linked results
- Sentiment counts and source breakdown
- Risk terms and recurring concerns
- Representative positive, negative, and neutral examples
- Recommended follow-up searches
- Streamlit dashboard

## Flexible callout

Sample dashboard included: Open the dashboard with bundled data before adding credentials. Dry-run mode also verifies the full cache, normalize, report, and dashboard pipeline without making API calls.

## Time / complexity cue

Runs locally in under 5 minutes with bundled sample data. Live collection requires a Nimble API key.

## How it works

1. Read the product config and query plan.
2. Run focused searches with Nimble Search API.
3. Save every raw API response immediately.
4. Normalize results into one schema.
5. Classify lightweight sentiment and risk terms.
6. Build a structured report with follow-up searches.
7. Render the report in a Streamlit dashboard.

## Stack

### Nimble

- Nimble Search API
- live web search across social, news, and general web focus modes
- raw response cache for auditability

### Runtime

- Python
- Streamlit
- Pandas
- Plotly
- local JSON config and report files

## Visual suggestion

Use a dashboard screenshot showing:

1. sentiment summary cards
2. source breakdown
3. representative links/findings
4. follow-up searches
