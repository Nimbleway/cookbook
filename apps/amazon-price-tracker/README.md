# Amazon Price Intelligence Dashboard

A 96-hour study of how Amazon prices 500 products across 10 US zip codes — built with [Nimble Web Search Agents](https://nimbleway.com) and Streamlit.

Every hour from May 10 to May 14, 2026, Nimble's `amazon_pdp` agent captured a full snapshot of 500 Amazon products across 5 city and 5 rural zip codes. That's **479,000+ data points** on prices, availability, reviews, and best-seller rankings — revealing algorithmic repricing, title A/B testing, and geographic pricing gaps in real time.

**Live dataset included.** The `data/` folder contains the complete processed dataset so you can run the dashboard immediately with no API calls.

---

## Key findings

- **33% of products moved in price** at least once during the 96-hour window
- **Algorithmic repricing is real**: one KN95 mask crashed 67% — from $24.98 to $8.09 — six times in 96 hours
- **Amazon pricing is overwhelmingly national**: 97% of products cost the same whether you shop from New York or Valentine, Nebraska
- **11 products ran live title A/B tests**, alternating between two titles every few hours throughout the window

---

## What the dashboard shows

| Tab | What it shows |
|---|---|
| **Overview** | Key stats, price distribution, top 10 biggest swings, geographic price gaps |
| **Price Swings** | All 500 products ranked by movement — click any row for the full timeline |
| **Zip Comparison** | The 12 products with geographic price differences, and a lookup for all 500 |
| **Signals & Events** | Title A/B tests, stock-outs, MSRP changes, and multi-signal cascade events |

---

## Quickstart — just the dashboard

The dataset is already included. Run the dashboard in under a minute:

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

---

## Run the full pipeline yourself

To collect fresh data, you'll need a [Nimble API key](https://nimbleway.com).

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your Nimble API key to .env
```

Then run each phase in order:

```bash
# Phase 1a — collect 500 ASINs from Amazon Best Sellers (10 categories)
python phase1_collect.py

# Phase 1b — normalize to data/asins.csv
python phase1_process.py
```

Phase 2 is a Nimble Agent Job — a scheduled batch that runs `amazon_pdp` across all 5,000 ASIN × zip combinations on an hourly cron. Set it up in [Nimble Studio](https://online.nimbleway.com/workflow-builder) using `data/asins.csv` as input, then download the resulting parquet files.

```bash
# Phase 3 — process the raw job output parquets into dashboard-ready parquets
# (place raw parquet files in the project root before running)
python phase3_process.py

# Phase 4 — extract non-price signals (title changes, OOS events, MSRP shifts)
python phase4_process.py

# Launch the dashboard
streamlit run dashboard.py
```

---

## Dataset

| File | Description | Rows |
|---|---|---|
| `data/price_history.parquet` | One row per ASIN × zip × hourly run | 479,880 |
| `data/asin_meta.parquet` | Stable metadata per ASIN (title, brand, ratings) | 497 |
| `data/asin_swings.parquet` | Price swing summary per ASIN (min, max, % change) | 497 |
| `data/zip_stats.parquet` | Median price per ASIN × zip code | 4,970 |
| `data/signals_history.parquet` | Signals per ASIN × run (BSR, availability, list price) | 47,700 |
| `data/title_changes.parquet` | Title change events with before/after BSR | 46 |
| `data/oos_summary.parquet` | Out-of-stock rate per ASIN across the window | 497 |
| `data/signal_alerts.parquet` | Multi-signal change events (2+ signals in one run) | — |
| `data/asins.csv` | The 500 ASINs collected (category, rank, name) | 500 |

**Zip codes tracked:**

| Type | Location | Zip |
|---|---|---|
| City | New York, NY | 10001 |
| City | Los Angeles, CA | 90001 |
| City | Chicago, IL | 60601 |
| City | Houston, TX | 77001 |
| City | Miami, FL | 33101 |
| Rural | Havre, MT | 59501 |
| Rural | Valentine, NE | 69201 |
| Rural | Greenwood, MS | 38930 |
| Rural | Pikeville, KY | 41501 |
| Rural | Dickinson, ND | 58601 |

---

## Project structure

```
amazon-price-tracker/
├── dashboard.py          ← Streamlit dashboard (4 pages)
├── phase1_collect.py     ← Fetch 500 ASINs from Amazon Best Sellers
├── phase1_process.py     ← Normalize raw JSON to asins.csv
├── phase3_process.py     ← Process raw Agent Job parquets → dashboard parquets
├── phase4_process.py     ← Extract non-price signals
├── requirements.txt
├── .env.example
└── data/
    ├── price_history.parquet
    ├── asin_meta.parquet
    ├── asin_swings.parquet
    ├── zip_stats.parquet
    ├── signals_history.parquet
    ├── title_changes.parquet
    ├── oos_summary.parquet
    ├── signal_alerts.parquet
    └── asins.csv
```

---

## Nimble agents used

| Agent | What it does |
|---|---|
| `amazon_best_sellers` | Pulls the top-ranked ASINs per category |
| `amazon_pdp` | Fetches full product detail: price, availability, BSR, title, reviews |
