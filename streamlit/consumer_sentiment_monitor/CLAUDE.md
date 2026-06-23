# Claude Code setup — Consumer Sentiment Monitor

Use this file as the Claude Code context prompt when opening `streamlit/consumer_sentiment_monitor`.

## Goal

Help the user run, adapt, and explain the Consumer Sentiment Monitor cookbook.

The app tracks launch sentiment around a product across social discussion, Reddit, reviews/comparison pages, and news/blog coverage. It uses Nimble Search API, caches raw responses, normalizes results, builds a lightweight sentiment report, and displays the output in a Streamlit dashboard.

## Product framing

Position this as a product-launch intelligence workflow powered by live web search.

One-line description:

> Track launch sentiment from live web sources and turn it into a dashboard your team can act on.

Nimble's role:

- Nimble Search API runs focused live-web searches across social, news, and general web results.
- The app layer normalizes, classifies, and summarizes the results.
- Streamlit displays the report and source-linked findings.

## Setup steps

```bash
cd streamlit/consumer_sentiment_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the bundled sample dashboard without credentials:

```bash
streamlit run dashboard.py
```

Run the dry-run collector without credentials:

```bash
python3 collect.py --dry-run
streamlit run dashboard.py
```

Run live mode only after credentials are set:

```bash
cp .env.example .env
# edit .env and set NIMBLE_API_KEY
python3 collect.py --config config/example_config.json
streamlit run dashboard.py
```

## Verification

A safe verification pass should include:

```bash
python3 -m py_compile collect.py dashboard.py
python3 collect.py --dry-run --output /tmp/consumer-sentiment-monitor-dry-run
python3 -m json.tool /tmp/consumer-sentiment-monitor-dry-run/report.json >/dev/null
python3 -m json.tool data/sample_run/report.json >/dev/null
```

The dashboard should load `data/sample_run/` by default even without credentials.

## Safe customisations

Common changes:

- copy `config/example_config.json` for a new product
- change product name, launch context, country, locale, and query list
- add or remove query groups such as social, Reddit, news, reviews, and comparisons
- replace the lightweight sentiment classifier with an LLM or a custom model
- adjust the Streamlit dashboard sections for a different reporting need

## Guardrails

- Keep sample dashboard mode working without credentials.
- Keep `--dry-run` working without credentials.
- Do not commit `.env`, `data/runs/`, `data/dry_run/`, `.venv/`, `__pycache__/`, or `.pyc` files.
- Preserve raw response caching before parsing so the run is auditable and resumable.
- Be explicit that the sentiment classifier is intentionally lightweight and replaceable.
