# AI Setup Instructions — Amazon Price Intelligence Dashboard

You are helping the user set up and run the Amazon Price Intelligence Dashboard. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

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
ls cookbook-amazon-price-tracker
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook-amazon-price-tracker
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-amazon-price-tracker
cd cookbook-amazon-price-tracker
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This includes `pyarrow` for efficient Parquet data handling — this is how the large dataset (479,000+ data points) is stored and loaded quickly.

---

## Step 4: Get API keys

Ask the user if they already have a Nimble API key, or need to get one.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to collect Amazon product data via the `amazon_pdp` agent.

Note: no API key is needed to run the dashboard with the included dataset. If the user chooses Path A in Step 5, skip this step.

---

## Step 5: Choose a path

Ask the user:

> "The app includes a complete dataset from a 96-hour study conducted May 2026 — 479,000+ data points tracking prices, availability, reviews, and best-seller rankings for 500 Amazon products across 10 US zip codes. You can explore the full dashboard right now with no API calls. Or I can walk you through collecting fresh data, which requires a Nimble API key and runs as a scheduled hourly job.
>
> Which would you prefer?
> A) Explore the included dataset now
> B) Set up fresh data collection"

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

## Step 7: Set up data collection

Important: the full data collection in this app is a **scheduled hourly job**, not a one-shot run. The original dataset was collected by running Phase 1 every hour for 96 hours. Walk the user through the approach before running anything.

Explain to the user:
- Phase 1 collects a snapshot of 500 Amazon products across 10 zip codes using the `amazon_pdp` Nimble agent
- It is designed to be run repeatedly on a schedule (cron, Task Scheduler, etc.)
- Each run appends to the existing dataset — re-running is safe
- The processing phases (1b, 3, 4) transform raw snapshots into the dashboard-ready Parquet files

Run a single collection snapshot to verify everything works:
```bash
python3 phase1_collect.py
```

Then process it:
```bash
python3 phase1_process.py
python3 phase3_process.py
python3 phase4_process.py
```

If the user wants to run ongoing collection, help them set up a cron job or equivalent scheduler to run `phase1_collect.py` on their preferred interval.

---

## Step 8: Launch the dashboard

```bash
streamlit run dashboard.py
```

The dashboard opens at http://localhost:8501

---

## Step 9: Orient the user

Walk the user through the four dashboard tabs:

1. **Overview** — start here. Key stats (total products tracked, % that moved in price, biggest single swing), price distribution across all products, top 10 biggest price swings, and geographic price gaps.

2. **Price Swings** — all 500 products ranked by price movement. Click any row to see the full price timeline for that product across the entire collection window.

3. **Zip Comparison** — the products with geographic price differences between zip codes, and a lookup tool for all 500 products to compare prices across all 10 zip codes.

4. **Signals & Events** — title A/B tests (products Amazon was alternating between two titles), stock-out events, MSRP changes, and multi-signal cascade events where several signals fired at once.

---

## Notes

- The dataset uses 5 city zip codes and 5 rural zip codes to test for geographic pricing differences. 97% of products showed no geographic variation.
- The `amazon_pdp` Nimble agent captures: price, availability, review count, review rating, best-seller rank, title, and ASIN.
- The 500 ASINs used in the original study are in `data/asins.csv` — the user can replace these with their own ASINs before running collection.
