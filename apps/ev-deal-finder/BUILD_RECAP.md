# EV Deal Finder — Build Recap

**Date:** April 30, 2026
**Stack:** Python · Nimble CLI + Batch API · Nimble Agent Builder · Streamlit · Plotly

---

## Step 1 — Data Collection: eBay Motors + Carvana

**Goal:** Pull structured used EV listings from two sources into a single normalized dataset.

### eBay Motors

Used the eBay Search Results agent to collect item IDs across broad EV queries — Tesla, Nissan Leaf, Chevy Bolt, Hyundai Ioniq, Kia EV6, Ford Mustang Mach-E, Rivian, VW ID.4, BMW i3, Audi e-tron, and more.

Search pages require a strong render tier to access reliably. `vx10-pro` — Nimble's stealth headful browser — ensures smooth access and clears any challenges.

```bash
nimble --transform "data.parsing" agent run \
  --agent ebay_search_results_community_2026_03_23 \
  --params '{"keyword": "used Tesla electric car"}'
```

Item IDs extracted from search results were then batched through the **Nimble Batch Extract API** to pull individual listing pages in parallel:

```python
import requests, os

batch_payload = {
    "requests": [
        {"url": f"https://www.ebay.com/itm/{item_id}", "format": "html"}
        for item_id in item_ids
    ]
}

resp = requests.post(
    "https://sdk.nimbleway.com/v1/extract/batch",
    json=batch_payload,
    headers={"Authorization": f"Bearer {os.getenv('NIMBLE_API_KEY')}"}
)
batch_id = resp.json()["batch_id"]
```

Each listing's **Item Specifics** section was parsed with BeautifulSoup:

```python
from bs4 import BeautifulSoup

def parse_item_specifics(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    specs = {}
    for dl in soup.find_all("dl", class_="ux-labels-values"):
        labels = [dt.get_text(strip=True) for dt in dl.find_all("dt")]
        values = [dd.get_text(strip=True) for dd in dl.find_all("dd")]
        specs.update(dict(zip(labels, values)))
    return specs
```

**57 eBay listings collected** across Tesla Model S, Model 3, Nissan Leaf, Chevy Bolt EUV, and others.

---

### Carvana

Carvana had no pre-built Nimble agent. A new agent was created from scratch using **Nimble Agent Builder** — no selectors written by hand.

```bash
# Agent built via Nimble Studio + Agent Builder MCP
# Published as: carvana_electric_cars_serp_2026_04_30_auw1p8rf
```

The agent paginates through `carvana.com/cars/electric` and returns structured results per page:

```bash
nimble --transform "data.parsing" agent run \
  --agent carvana_electric_cars_serp_2026_04_30_auw1p8rf \
  --params '{"page": "1"}'
```

**761 Carvana listings collected** across 30+ pages of live inventory.

---

### Normalized Schema

Both sources merged into a single `data/listings.json` with this unified schema:

| Field | eBay | Carvana |
|---|---|---|
| `source` | `"ebay"` | `"carvana"` |
| `url` | eBay listing URL | Carvana listing URL |
| `make` | Parsed from Item Specifics | From agent |
| `model` | Parsed from Item Specifics | From agent |
| `year` | Parsed integer | From agent |
| `trim` | `null` | From agent |
| `price` | From listing | From agent |
| `mileage` | From Item Specifics | From agent |
| `condition` | From Item Specifics | `"Used"` |
| `title_status` | From Item Specifics | `"Clean"` |
| `fuel_type` | `"Electric"` | `"Electric"` |
| `city` | From Item Specifics | From agent |

**Total: 818 listings** ready for scoring.

---

## Step 2 — Scoring Engine: `score.py`

Each listing is scored on five factors and combined into a single `deal_score` between 0 and 1.

### Weights

| Factor | Weight | Logic |
|---|---|---|
| Price | 30% | Lower is better |
| Mileage | 25% | Lower is better |
| Year | 20% | Newer is better |
| Condition | 15% | Text → score map |
| Title Status | 10% | Text → score map |

### Relative Scoring

All continuous metrics (price, mileage, year) are scored relative to the **full dataset** — not per model. The cheapest car across all 818 listings scores 1.0 on price, regardless of make.

```python
WEIGHTS = {
    "price":     0.30,
    "mileage":   0.25,
    "year":      0.20,
    "condition": 0.15,
    "safety":    0.10,
}

def _relative_score(value, lo, hi, lower_is_better=True):
    if hi == lo:
        return 0.5
    if lower_is_better:
        return max(0.0, min(1.0, 1.0 - (value - lo) / (hi - lo)))
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))
```

### Condition Score Map

| Label | Score |
|---|---|
| Certified Pre-Owned | 1.00 |
| Excellent | 0.95 |
| Very Good | 0.85 |
| Good | 0.75 |
| Used | 0.70 |
| Fair | 0.55 |
| Remanufactured | 0.50 |
| For Parts | 0.10 |

### Title Status Score Map

| Label | Score |
|---|---|
| Clean | 1.00 |
| Lien | 0.80 |
| Rebuilt | 0.50 |
| Salvage | 0.20 |
| Parts Only | 0.10 |

Run the engine:

```bash
python3 score.py
# Scored 807 listings.
# Top 5 deals printed to terminal.
```

Each listing in `listings.json` gets five component scores plus `deal_score` written back in place.

---

## Step 3 — Dashboard: `app.py`

A Streamlit + Plotly dashboard that loads the pre-scored `listings.json` and makes it browsable and filterable.

```bash
streamlit run app.py
```

### What's in the dashboard

**Header:** National average gas price ($4.229/gal — highest since August 2022) as the news hook for why this matters right now.

**Sidebar filters:**
- Make / model
- Year range
- Max price
- Max mileage
- Minimum deal score

**Charts:**
- Price vs. mileage scatter (color-coded by deal score)
- Deal score distribution by model
- Listings by year bar chart
- Score breakdown for the top deal

**Listings table:** Filterable, sortable, with a `View →` link to the live eBay or Carvana listing for every row.

**CSV export:**

```bash
python3 app.py --export
# Writes ev_deals_export.csv — full ranked dataset
```

---

## Results at a Glance

| Metric | Value |
|---|---|
| Total listings collected | 818 |
| Sources | eBay Motors + Carvana |
| Models covered | Tesla Model S, Model 3, Nissan Leaf, Chevy Bolt, Kia EV6, Hyundai Ioniq, and more |
| Listings scored | 807 |
| New agents built | 1 (Carvana, from scratch via Agent Builder) |
| Existing agents used | 2 (eBay SERP, eBay PDP) |
| Dashboard filters | 6 |
| Data refresh time | ~2 min (batch extract) |
