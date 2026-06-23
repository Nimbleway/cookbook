# AI Setup Instructions — EV Deal Finder

You are helping the user set up and run the EV Deal Finder. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**Nimble CLI**
```bash
nimble --version
```
If missing: `npm install -g @nimbleway/nimble`

**nimble-python**
```bash
python3 -c "import nimble_python; print('ok')"
```
If missing: `pip install nimble-python`

**git**
```bash
git --version
```
If missing: direct the user to https://git-scm.com

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook-ev-deal-finder
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook-ev-deal-finder
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-ev-deal-finder
cd cookbook-ev-deal-finder
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4: Get API keys

Ask the user if they already have a Nimble API key, or need to get one.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to collect live EV listings from eBay Motors and Carvana.

Note: no API key is needed to run the dashboard with the included dataset. If the user chooses Path A in Step 5, skip this step.

---

## Step 5: Choose a path

Ask the user:

> "The app includes 818 pre-scored EV listings from eBay Motors and Carvana, collected April 2026 — you can explore the full dashboard right now with no API calls. Or I can refresh the dataset with live listings, which requires a Nimble API key.
>
> Which would you prefer?
> A) Explore the included dataset now
> B) Refresh with live listings"

**If they choose A** — skip Steps 6 and 7, go directly to Step 8 (Launch the dashboard).

**If they choose B** — continue with Step 6.

---

## Step 6: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's Nimble key:
```
NIMBLE_API_KEY=their_nimble_key_here
```

---

## Step 7: Refresh the dataset

The data collection approach for this app is documented in `BUILD_RECAP.md`. Walk the user through it — the collection uses two Nimble agents:

- `ebay_search_results_community_2026_03_23` — eBay Motors listings
- A custom Carvana agent built with Nimble Agent Builder

Show the user `BUILD_RECAP.md` and help them adapt the collection scripts for their needs. Then run the scoring engine:

```bash
python3 score.py
```

---

## Step 8: Launch the dashboard

```bash
streamlit run app.py
```

The dashboard opens at http://localhost:8501

---

## Step 9: Orient the user

Walk the user through the dashboard:

1. **Sidebar filters** — start here. Show them how to filter by EV model, year range, max price, max mileage, and minimum deal score.

2. **Overview tab** — deal score distribution, price vs. mileage scatter, listings by year, and a score breakdown for the top deal.

3. **Top Deals tab** — the 4 highest-scoring listings with direct links to the live listings on eBay or Carvana.

4. **Per-metric tabs** — ranked tables for Price, Mileage, Year, Condition, and Safety individually. Useful if the user prioritizes one factor over the overall score.

5. **All listings table** — every listing, sortable, with clickable links.

---

## Notes

- The deal score (0–1) is calculated across 5 factors: Price (30%), Mileage (25%), Year (20%), Condition (15%), Title Status (10%).
- All metrics are scored relative to the full dataset — a $10,000 Tesla competes directly against a $10,000 Nissan Leaf on price.
- To export the full ranked dataset as CSV: `python3 app.py --export` → writes `ev_deals_export.csv`.
