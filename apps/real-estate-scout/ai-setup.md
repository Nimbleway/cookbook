# AI Setup Instructions — Real Estate Investment Scout

You are helping the user set up and run the Real Estate Investment Scout. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

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
ls cookbook-real-estate-scout
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook-real-estate-scout
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-real-estate-scout
cd cookbook-real-estate-scout
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This includes `pydeck` for 3D map rendering. No Mapbox token is required — the maps use open tiles.

---

## Step 4: Get API keys

Ask the user if they already have both keys, or need to get one or both.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to collect market data from Redfin and active listings from Zillow (phases 1 and 3).

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by Claude to score all 100 cities and select the top 10 investment markets with thesis and risk (phase 2).

Note: neither key is needed to run the dashboard with the included dataset. If the user chooses Path A in Step 5, skip this step.

---

## Step 5: Choose a path

Ask the user:

> "The app includes a complete dataset collected May 2026 — 100 US cities scored, 1,199 active Zillow listings, and deep market reports for the top 10 cities. You can explore the full dashboard right now with no API calls. Or I can collect fresh data, which takes a few minutes and uses your Nimble and Anthropic keys.
>
> Which would you prefer?
> A) Explore the included dataset now
> B) Collect fresh data"

**If they choose A** — skip Steps 6 and 7, go directly to Step 8 (Launch the dashboard).

**If they choose B** — continue with Step 6.

---

## Step 6: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's keys:
```
NIMBLE_API_KEY=their_nimble_key_here
ANTHROPIC_API_KEY=their_anthropic_key_here
```

---

## Step 7: Run the pipeline

Run each phase in order:

```bash
# Phase 1 — collect Redfin market data for 100 US cities
python3 phase1_collect.py
```
Tell the user: pulls market statistics (median price, YoY appreciation, transaction volume, days on market) for 100 cities from Redfin. Takes 2–3 minutes.

```bash
# Phase 2 — score all cities and select top 10 with Claude
python3 phase2_score.py
```
Tell the user: scores all 100 cities algorithmically, then Claude selects the top 10 investment markets and writes an investment thesis and key risk for each. Takes ~1 minute.

```bash
# Phase 3 — collect Zillow listings for top 10 cities
python3 phase3_collect.py
```
Tell the user: pulls active property listings across 3 zip codes per city (30 total). Takes 2–3 minutes.

Each phase caches results — re-running skips already-collected data.

---

## Step 8: Launch the dashboard

```bash
streamlit run dashboard.py
```

The dashboard opens at http://localhost:8501

---

## Step 9: Orient the user

Walk the user through the four dashboard tabs:

1. **National Market Scan** — start here. A 100-city USA map where bubble size shows transaction volume and color shows investment score. Below it: a sortable rankings table and a price vs. YoY appreciation scatter plot.

2. **Top 10 Investment Markets** — radar chart comparing the top 10 cities across 5 investment dimensions, a bar chart with metric selector, and city cards showing Claude's investment thesis and key risk for each market.

3. **Listings Explorer** — filter 1,199 active listings by market, price range, bedrooms, and home type. Interactive map colored by price tier with photo gallery below.

4. **City Deep Dive** — select any top-10 city for its full investment analysis: key metrics, Claude's thesis, a Perplexity market report, neighborhood map, price distribution, and listing photos.

---

## Notes

- The 100-city list is in `cities.csv` — the user can edit this file before running Phase 1 to target different cities.
- Phase 2 uses `claude-sonnet-4-6` for city selection and analysis.
- The Redfin and Zillow agents used are pre-built Nimble Web Search Agents — no custom agent setup needed.
