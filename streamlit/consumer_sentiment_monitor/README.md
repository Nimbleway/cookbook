# Consumer Sentiment Monitor

A Nimble data app for tracking launch sentiment around a product across social discussion, Reddit, reviews/comparison pages, and news/blog coverage.

It uses Nimble's Search API:

```http
POST https://sdk.nimbleway.com/v1/search
Authorization: Bearer $NIMBLE_API_KEY
```

The app turns focused web searches into a structured sentiment report with source links, sentiment buckets, risk signals, and recommended follow-up searches — displayed in a dark-themed Streamlit dashboard.

## What it does

| Step | What happens | Nimble capability |
|---|---|---|
| 1 | Reads a product config and query plan | — |
| 2 | Runs social, Reddit, review, and news searches | Nimble Search API with `focus` modes |
| 3 | Saves every raw API response before parsing | Resumable raw cache |
| 4 | Normalizes results into one schema | App layer |
| 5 | Classifies lightweight sentiment and risk terms | App layer |
| 6 | Writes a structured report and renders a dashboard | Streamlit |

## Quickstart — sample dashboard, no API key

```bash
cd streamlit/consumer_sentiment_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard.py
```

The dashboard loads `data/sample_run/` by default, so it works without credentials.

## Run a dry-run collection

```bash
python3 collect.py --dry-run
streamlit run dashboard.py
```

Dry-run mode writes synthetic Nimble-shaped responses to `data/dry_run/`. This verifies the full cache → normalize → report pipeline without making any API calls.

## Run with Nimble Search API

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your NIMBLE_API_KEY
python3 collect.py --config config/example_config.json
streamlit run dashboard.py
```

Each live run is saved to `data/runs/<timestamp>/`. The dashboard sidebar lets you switch between runs.

## Bundled configs

Three ready-to-use configs are included in `config/`:

| Config | What it monitors |
|---|---|
| `example_config.json` | Acme AI Notes (placeholder, safe to copy and adapt) |
| `nimble_config.json` | Nimble's own Search API and web data platform |

Run either with:

```bash
python3 collect.py --config config/nimble_config.json
```

## Create your own config

Copy `config/example_config.json` and edit it:

```json
{
  "product_name": "Your Product",
  "launch_context": "What launched and who it is for.",
  "country": "US",
  "locale": "en-US",
  "search_depth": "lite",
  "include_answer": true,
  "max_results": 8,
  "queries": [
    {
      "id": "reddit_reactions",
      "label": "Reddit reactions",
      "focus": "social",
      "source_type": "reddit/social",
      "query": "Your Product launch Reddit reactions pricing"
    },
    {
      "id": "vs_alternatives",
      "label": "Competitor comparisons",
      "focus": "general",
      "search_depth": "fast",
      "source_type": "reviews/comparison",
      "query": "Your Product vs alternatives comparison review"
    }
  ]
}
```

### `search_depth` rules

The Nimble Search API enforces which depth values work with each focus mode:

| `focus` | Allowed `search_depth` values |
|---|---|
| `general` | `lite`, `fast`, `deep` |
| `social` | `lite`, `deep` |
| `news` | `lite`, `deep` |

Set `"search_depth": "lite"` at the top level as your default, then override to `"fast"` on individual queries that use `focus: "general"`.

### Focus modes

- `social` — social and discussion-style results (Twitter/X, Reddit, forums)
- `news` — launch coverage and blogs
- `general` — reviews, comparisons, broader web

## Output files

Each run produces:

```text
report.json              # executive summary, sentiment buckets, follow-up searches
normalized_results.json  # normalized source-linked records
schema.json              # normalized result schema
raw/*.json               # raw Nimble responses, saved before any parsing
```

## Project structure

```text
streamlit/consumer_sentiment_monitor/
├── collect.py
├── dashboard.py
├── CLAUDE.md
├── WEBFLOW.md
├── config/
│   ├── example_config.json
│   └── nimble_config.json
├── data/
│   └── sample_run/
│       ├── report.json
│       ├── normalized_results.json
│       ├── schema.json
│       └── raw/
├── requirements.txt
└── .env.example
```

## Notes

- The sentiment classifier is intentionally lightweight and transparent — easy to replace with Claude, OpenAI, or a Nimble-powered analysis step later.
- Raw responses are cached on first fetch. Re-running against the same output directory skips already-fetched queries.
- The `data/` directory is gitignored except for `sample_run/`, which ships as a zero-credential demo dataset.
