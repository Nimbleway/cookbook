# AI Setup Instructions — Autonomous SEO Strategist

You are helping the user set up and run the Autonomous SEO Strategist. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

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
ls cookbook-seo-strategist
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook-seo-strategist
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook-seo-strategist
cd cookbook-seo-strategist
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
pip install nimble-python
```

Note: `nimble-python` is installed separately because it is missing from `requirements.txt`. Both commands are needed.

---

## Step 4: Get API keys

The user needs two API keys. Ask them now if they already have both, or need to get one or both.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used for site extraction, URL mapping, and live SERP data (phases 1, 3, 5).

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used for Claude analysis — search term generation, competitor mapping, diagnosis, recommendations (phases 4, 6, 7, 8).

Wait until the user confirms they have both keys before continuing.

---

## Step 5: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's keys:
```
NIMBLE_API_KEY=their_nimble_key_here
ANTHROPIC_API_KEY=their_anthropic_key_here
```

---

## Step 6: Choose a path

Ask the user:

> "The app includes a complete sample SEO analysis for stripe.com — you can explore the full dashboard right now with no API calls. Or I can run a fresh analysis on your own domain, which takes about 5 minutes and uses your Nimble and Anthropic keys.
>
> Which would you prefer?
> A) Explore the sample dashboard now
> B) Run a full analysis on my domain"

**If they choose A** — skip Steps 7 and 8, go directly to Step 9 (Launch the dashboard). The Stripe dataset is already in the repo at `.nimble/seo_runs/stripe.com/`.

**If they choose B** — continue with Step 7.

---

## Step 7: Configure the target domain

Open `config/analysis_config.json`. Ask the user for:

1. **Target domain** — the website they want to analyse (e.g. `https://theirdomain.com`)
2. **Country** — target market for SERP data (default: `US`)
3. **Language** — default: `English`
4. **Business model** — e.g. `B2B SaaS`, `E-commerce`, `Marketplace` — helps Claude generate relevant search terms
5. **Known competitors** — optional, comma-separated domains they know compete with them
6. **Brand terms to exclude** — their own brand name(s), so they don't show up as search terms

Update the file with their answers:
```json
{
  "homepage_url": "https://theirdomain.com",
  "target_country": "US",
  "language": "English",
  "business_model": "B2B SaaS",
  "known_competitors": ["competitor1.com", "competitor2.com"],
  "brand_terms_to_exclude": ["their brand name"],
  "search_term_mode": "balanced"
}
```

---

## Step 8: Run the pipeline

```bash
python3 run_analysis.py
```

This runs all 8 phases in sequence. Tell the user what each phase is doing as it runs:

| Phase | What's happening | Approx. time |
|---|---|---|
| 1 | Fetching homepage as markdown | ~5s |
| 2 | Mapping site URLs + Claude selecting top pages | ~15s |
| 3 | Batch-extracting selected pages | ~30–60s |
| 4 | Claude generating 30 search terms | ~15s |
| 5 | Firing all 30 live Google searches | ~30–60s |
| 6 | Claude mapping competitors across SERPs | ~20s |
| 7 | Claude diagnosing each term with priority scores | ~30s |
| 8 | Claude generating recommendations | ~45s |

Total: roughly 3–5 minutes depending on site size.

Results are saved to `.nimble/seo_runs/{domain}/{timestamp}/`. If a phase fails, re-running `python3 run_analysis.py` will skip already-completed phases.

---

## Step 9: Launch the dashboard

```bash
python3 -m streamlit run dashboard/app.py
```

The dashboard opens at http://localhost:8501

---

## Step 10: Orient the user

Walk the user through the dashboard tabs in this order:

1. **Overview** — start here. Show them their composite SEO score and the SERP status breakdown (winning / wrong page / absent). The executive summary and top quick wins are here.

2. **SERP Rankings** — the full 30-term table. Show them how to filter by status and funnel stage. Click any row to see the full SERP for that term.

3. **Competitors** — who is winning the traffic they should own. Sorted by threat level.

4. **Quick Wins** — the highest-impact, lowest-effort actions. Each card shows the specific page to fix and the search terms affected.

5. **Recommendations** — page briefs, new pages to create, and strategic themes. Most detailed output.

6. **Full Report** — the complete markdown report rendered inline. Tell the user they can copy this into any doc.

---

## Notes

- The repo includes a complete sample run against stripe.com in `.nimble/seo_runs/stripe.com/` — the user can explore it any time by launching the dashboard before running their own analysis.
- Re-running the pipeline on the same domain creates a new timestamped run. The dashboard always loads the most recent one.
- The `search_term_mode` in config can be set to `broad`, `balanced`, or `focused` depending on how exploratory the user wants the search terms to be.
