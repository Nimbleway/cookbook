# AI Setup Instructions — Market Mapper

You are helping the user set up and run Market Mapper, an app that maps the universe of companies fitting an ICP using Nimble Web Search Agents, with enrichment and per-field trust stored in Supabase. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**pip**
```bash
pip --version
```
If missing: direct the user to https://pip.pypa.io/en/stable/installation/

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook
```

**If the directory exists** — navigate to the app and pull the latest:
```bash
cd cookbook/apps/market-mapper
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/market-mapper
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This installs LangChain (Anthropic integration), the Supabase client, Streamlit, Pandas, Requests, and python-dotenv.

---

## Step 4: Get API keys and a Supabase project

Ask the user which of the following they already have.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: this powers both Web Search Agents — the Mapper that discovers companies matching the ICP, and the Enricher that fills firmographics, funding, contacts, and buying signals with per-field citations.

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by Claude for the chat tab — natural-language questions over the mapped dataset.

**Supabase project (free tier)**
Create one at: https://supabase.com/dashboard
Tell the user: stores the mapped companies, enrichment fields, and trust data in two Postgres tables. The URL and service_role key are under **Project Settings → API**.
Note: free-tier projects pause after about a week of inactivity — an existing project may need restoring from the dashboard first.

---

## Step 5: Create the database tables

Tell the user: open the Supabase dashboard, go to **SQL Editor → New query**, paste the full contents of `supabase/schema.sql`, and click **Run**.

Read `supabase/schema.sql` and display it so the user can copy it. Tell them what it creates:
- `mm_runs` — one row per mapping run: ICP prompt, exclusion list, run and interaction ids, raw discovery result
- `mm_companies` — one row per company: discovery fields, enrichment fields, per-field trust claims, verbatim raw responses

Expected runtime: ~1 second. Ask the user to confirm it ran without errors before continuing.

---

## Step 6: Configure environment

```bash
cp .env.example .env
```

Open `.env` and add the user's values:
```
NIMBLE_API_KEY=their_nimble_key
ANTHROPIC_API_KEY=their_anthropic_key
SUPABASE_URL=https://their-project.supabase.co
SUPABASE_KEY=their_service_role_key
USE_LIVE=true
ENRICH_CAP=10
```

Tell the user: `USE_LIVE=false` replays the bundled sample dataset (a real healthcare-AI market map) through the same code paths — useful for exploring the UI without API calls. `ENRICH_CAP` is how many companies each "Enrich" click processes.

---

## Step 7: Create the agents

```bash
python3 setup_agents.py
```

This creates two Web Search Agents in the user's Nimble workspace and writes their ids to `agents.json`:
- **Market Mapper — Mapper**: cloned from the `gtm-lead-discovery` gallery template, customized with a 10-field output schema, hard-constraint goals, and an exclusion-list rule
- **Market Mapper — Enricher**: cloned from the `lead-enrichment` gallery template

The script is idempotent — safe to re-run; it finds existing agents by name and re-applies the configuration.

Expected runtime: ~5 seconds. Confirm `agents.json` now exists with two ids starting `wsa_`.

---

## Step 8: Launch the app

```bash
python3 -m streamlit run app.py
```

The app opens at http://localhost:8501

---

## Step 9: Orient the user

Walk the user through the app:

1. **Describe an ICP** in the sidebar — e.g. `"AI-powered vertical SaaS companies in healthcare, 11-200 employees, US or Israel, Series A or later"`. Optionally upload an exclusion list (one domain per line — companies already in their CRM). Click **Map the market**.

2. **The wait is real research** — discovery runs take 5–10 minutes; the status box shows elapsed time. Suggest trying `USE_LIVE=false` first if the user wants instant results from the sample dataset.

3. **Enrich** — once companies appear, click **Enrich next 10**. Each company gets funding stage, total raised, investors, headcount, tech stack, named contacts with LinkedIn URLs, and buying signals. Takes ~5 minutes per batch of 10.

4. **Trust** — the table shows an overall confidence badge per company. Open a **Company detail** to see per-field trust: every field's worst-claim confidence, a claim-count breakdown (array fields carry one cited claim per element — a single company can have 70+), and citation links.

5. **Expand the map** — one click re-runs the Mapper with `previous_interaction_id`, adding new companies to the same map without repeating domains. Takes ~8–10 minutes.

6. **Chat** — ask questions over the map: *"Which companies raised most recently?"*, *"Who has a VP of Engineering listed?"*

7. **Export** — Download CSV, or query the `mm_companies` table directly in Supabase.

8. **Headless mode** — mention that the full pipeline also runs without the UI: `python3 mapper.py "<ICP>" [--exclude domains.txt] [--no-enrich]` — the embed path for calling collection from the user's own product or scheduler.

---

## Notes

- Every mapping and enrichment run is a live Web Search Agents run — results vary with the live web, and runs take minutes by design (the agent is doing real multi-source research).
- Failed enrichment runs mark the row `enrich_status = failed` rather than crashing; re-clicking Enrich skips non-pending rows (resume-safe).
- Raw API responses are stored verbatim in `mm_runs.raw_result` and `mm_companies.raw_enrichment` — reprocessing or re-aggregating trust data never requires re-running agents.
- The Mapper's source allow-list is a hard whitelist — the agent searches only within it. Edit `MAPPER_SOURCES` in `setup_agents.py` to change where discovery looks.
- The chat uses `claude-sonnet-4-6`.
