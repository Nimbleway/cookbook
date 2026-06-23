# Real Estate Investment Scout

An AI-powered real estate investment research pipeline built with [Nimble Web Search Agents](https://nimbleway.com) and Claude. The full research workflow a human analyst would spend days on — scraping market data, scoring cities, pulling listings, generating reports — done in minutes.

**Live dataset included.** The `data/` folder contains the complete collected dataset (100 cities, 1,199 listings, 10 market reports) so you can run the dashboard immediately without any API calls.

---

## What it does

| Stage | What happens | Nimble Agent |
|---|---|---|
| 1 | Pulls market statistics for 100 US cities from Redfin | `redfin_market_housing_data_community_2026_05_02` |
| 2 | Scores all cities and uses Claude to select the top 10 investment markets with thesis + risk | Claude API |
| 3 | Pulls 1,199 active listings from Zillow across 30 zip codes | `zillow_plp` |
| 4 | Generates deep market reports for each top-10 city via Perplexity | `perplexity` |
| 5 | Renders everything in a 4-tab Streamlit dashboard | — |

---

## Quickstart — just the dashboard

The dataset is already collected and included. To run the dashboard with no API calls:

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

---

## Run the full pipeline

To collect fresh data yourself, you'll need a [Nimble API key](https://nimbleway.com) and an [Anthropic API key](https://console.anthropic.com).

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your keys to .env
```

Then run each phase in order:

```bash
# Phase 1 — collect Redfin market data (100 cities)
python phase1_collect.py

# Phase 2 — score with code, rank top 10 with Claude
python phase2_score.py

# Phase 3 — collect Zillow active listings for top 10 cities
python phase3_collect.py

# Launch the dashboard
streamlit run dashboard.py
```

Each phase caches results — re-running skips already-collected data.

---

## Dashboard tabs

**National Market Scan** — 100-city USA map (bubble size = transaction volume, color = investment score), sortable rankings table, price vs. YoY appreciation scatter.

**Top 10 Investment Markets** — Radar chart comparing 5 investment dimensions, bar chart with metric selector, city cards with Claude's investment thesis and key risk for each market.

**Listings Explorer** — Filter 1,199 active listings by market, price range, bedrooms, and home type. Interactive map colored by price tier. Photo gallery.

**City Deep Dive** — Select any top-10 city for key metrics, Claude's full investment analysis, a Perplexity market report, neighborhood map, price distribution, and listing photos.

---

## Project structure

```
├── phase1_collect.py        # Redfin data collection
├── phase2_score.py          # Claude scoring and ranking
├── phase3_collect.py        # Zillow listings collection
├── dashboard.py             # Streamlit dashboard
├── cities.csv               # 100 US cities with Redfin city IDs
├── requirements.txt
├── .env.example             # API key template
└── data/
    ├── all_cities_scored.json     # All 100 cities with scores
    ├── top10_cities.json          # Top 10 with Claude thesis/risk
    ├── perplexity_reports.json    # Market reports for top 10
    └── raw/
        ├── redfin_*.json          # 100 Redfin market files
        └── zillow/                # 30 Zillow zip code files
```

---

## Dataset

Collected May 2026.

| Dataset | Records | Source |
|---|---|---|
| City market statistics | 100 cities | Redfin |
| Investment scores + Claude analysis | 10 cities | Claude (`claude-sonnet-4-6`) |
| Active property listings | 1,199 listings | Zillow |
| Market reports | 10 cities | Perplexity |

---

## Requirements

- Python 3.9+
- Nimble API key (for data collection only) — [get one here](https://nimbleway.com)
- Anthropic API key (for Phase 2 only) — [get one here](https://console.anthropic.com)
