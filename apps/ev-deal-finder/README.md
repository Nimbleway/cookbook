# EV Deal Finder

A Streamlit dashboard that scores and ranks 818 used electric vehicle listings from eBay Motors and Carvana — filtered, sortable, and linked directly to live listings.

Built with [Nimble Web Search Agents](https://nimbleway.com) + Python.

---

## What's inside

| File | Description |
|---|---|
| `app.py` | Streamlit dashboard — filters, charts, ranked table |
| `score.py` | Scoring engine — 5-factor weighted deal score |
| `data/listings.json` | 818 scored EV listings (eBay + Carvana) |
| `ev_deals_export.csv` | Full ranked dataset as CSV |
| `BUILD_RECAP.md` | How this was built — data collection, scoring, dashboard |

---

## Quickstart

**1. Clone and install**

```bash
git clone https://github.com/your-org/ev-deal-finder
cd ev-deal-finder
pip install -r requirements.txt
```

**2. Run the dashboard**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

**3. Export to CSV**

```bash
python3 app.py --export
# → writes ev_deals_export.csv
```

---

## Dashboard features

- **Sidebar filters** — model, year range, max price, max mileage, minimum deal score
- **Overview tab** — deal score distribution, price vs. mileage scatter, listings by year, score breakdown for the top deal
- **Top Deals tab** — cards for the 4 highest-scoring listings with direct links
- **Per-metric tabs** — ranked tables for Price, Mileage, Year, Condition, and Safety
- **All listings table** — sortable, with clickable links to every live listing

---

## Scoring model

Each listing is scored on five factors and combined into a single `deal_score` (0–1):

| Factor | Weight | Logic |
|---|---|---|
| Price | 30% | Lower is better — scored relative to full dataset |
| Mileage | 25% | Lower is better — scored relative to full dataset |
| Year | 20% | Newer is better — scored relative to full dataset |
| Condition | 15% | Text label → score map |
| Title Status | 10% | Clean title = 1.0, Salvage = 0.20 |

All continuous metrics are scored relative to the full 818-listing dataset, not per model. A $10,000 Tesla Model S competes directly against a $10,000 Nissan Leaf on price.

---

## Dataset

818 listings collected on April 30, 2026:

| Source | Count | Models |
|---|---|---|
| Carvana | 761 | Tesla Model 3, Model Y, Model S, Chevy Bolt, Kia EV6, Hyundai Ioniq 5/6, and more |
| eBay Motors | 57 | Tesla Model S, Model 3, Nissan Leaf, Chevy Bolt EUV |

Data was collected using Nimble Web Search Agents:
- **eBay**: `ebay_search_results_community_2026_03_23` + Batch Extract API for listing detail pages
- **Carvana**: `carvana_electric_cars_serp_2026_04_30_auw1p8rf` (custom agent built with Nimble Agent Builder)

To refresh the dataset with live data, you'll need a [Nimble API key](https://nimbleway.com).

---

## How it was built

See [`BUILD_RECAP.md`](./BUILD_RECAP.md) for a full walkthrough — data collection approach, Nimble agent setup, scoring engine logic, and dashboard construction.

---

## Requirements

```
nimble-python
python-dotenv
streamlit
plotly
pandas
```

Python 3.9+.
