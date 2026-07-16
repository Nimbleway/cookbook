# AI Setup Instructions — Diligence Desk

You are helping the user set up and run Diligence Desk, an app that turns a company name into an audit-grade diligence memo using a Nimble Web Search Agent, reviews it with a CrewAI crew, and acts on it — PDF memo, email delivery, live follow-up questions, and a self-learning analyst. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.10+** (CrewAI requires it)
```bash
python3 --version
```
If missing or below 3.10: direct the user to https://python.org/downloads

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
cd cookbook/apps/diligence-desk
git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/diligence-desk
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This installs CrewAI (with the Anthropic provider), the Supabase client, Streamlit, fpdf2, Resend, Requests, and python-dotenv. CrewAI has a large dependency tree — expect this step to take a few minutes.

---

## Step 4: Get API keys and a Supabase project

Ask the user which of the following they already have.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: this powers the Diligence Analyst — a Web Search Agent that researches the target company across filings, registries, press, and court records at maximum effort, returning every claim with citations.

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by the CrewAI review crew — a QA analyst, a risk officer, and an editor that turn the research into the final memo.

**Supabase project (free tier)**
Create one at: https://supabase.com/dashboard
Tell the user: stores memos, per-claim trust data, follow-up answers, and the analyst's learning log. The URL and service_role key are under **Project Settings → API**.
Note: free-tier projects pause after about a week of inactivity — an existing project may need restoring from the dashboard first.

**Resend API key (optional)**
Get one at: https://resend.com
Tell the user: enables the email action — the memo PDF sent straight to the deal team. Without it, the app still generates the PDF and shows an email preview instead of sending.

---

## Step 5: Create the database tables

Tell the user: open the Supabase dashboard, go to **SQL Editor → New query**, paste the full contents of `supabase/schema.sql`, and click **Run**.

Read `supabase/schema.sql` and display it so the user can copy it. Tell them what it creates:
- `dd_memos` — one row per diligence memo: prompt, verdict, verbatim raw result, narrative, PDF path
- `dd_claims` — one row per trust claim: JSON path, confidence, citations (the audit trail)
- `dd_followups` — follow-up questions and the agent's researched answers
- `dd_agent_updates` — the analyst's learning log: every standing instruction with before/after

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
RESEND_API_KEY=optional_resend_key
USE_LIVE=true
```

Tell the user: `USE_LIVE=false` replays the bundled sample memo (a real diligence run on Perplexity AI) through the same code paths — useful for exploring the UI without API calls or the ~15-minute research wait.

---

## Step 7: Create the agent

```bash
python3 setup_agent.py
```

This creates the **Diligence Desk — Analyst** agent in the user's Nimble workspace and writes its id to `agent.json`: cloned from the `due-diligence` gallery template, then customized with a verdict-led output schema, six acceptance-criteria goals, twelve source groups (SEC EDGAR, Crunchbase, PitchBook, court records, and more), and maximum research effort.

The script is idempotent — safe to re-run; it re-applies the configuration to the existing agent.

Expected runtime: ~5 seconds. Confirm `agent.json` now exists with an id starting `wsa_`.

---

## Step 8: Launch the app

```bash
python3 -m streamlit run app.py
```

The app opens at http://localhost:8501

---

## Step 9: Orient the user

Walk the user through the app:

1. **Run a diligence** — on the New memo page, describe the target: `"Due diligence on Perplexity AI (perplexity.ai) for a strategic investment"`. The wait is real research — max-effort runs take 10–20 minutes while the agent reads filings, registries, press, and court records. Suggest `USE_LIVE=false` first for instant results from the sample memo.

2. **Read the memo** — verdict first (proceed / proceed with conditions / caution / do not proceed), then the sections. Every section carries a confidence badge aggregated from its claims; the **trust panel** at the bottom lists every claim with its citations and excerpts — the audit trail.

3. **Evidence gaps** — the Risk Officer lists the load-bearing claims that rest on weak evidence, each with a verify-by-hand recommendation. Low confidence is flagged, never hidden.

4. **Act on it** — generate the PDF memo (verdict badge, risk table, citation appendix) and email it to the deal team. Without a Resend key the app shows the email preview instead.

5. **Ask it anything** — follow-up questions go back to the live agent with the memo's research context. This is new research, not chat over stored data — expect 1–5 minutes per answer.

6. **Teach the analyst** — on the Teach page, add a standing instruction like *"Always assess exposure to pending AI copyright litigation and name the specific cases."* The instruction is written into the agent itself; every future memo honors it, and the learning log shows what the analyst has learned and when.

---

## Notes

- Every memo and follow-up is a live Web Search Agents run — results vary with the live web, and runs take minutes by design.
- Raw API responses are stored verbatim in `dd_memos.raw_result` and `dd_followups.raw_result` — reprocessing never requires re-running agents.
- Failed runs are logged as failed memos rather than crashing; re-run from the New memo page.
- The review crew uses `claude-sonnet-4-6`; the memo research effort is `max` and follow-ups run at `high` for faster answers.
