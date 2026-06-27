# AI Setup Instructions — Financial Comparison Agent

You are helping the user set up and run the Financial Comparison Agent. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

This app is a **live agent** — there is no bundled offline dataset. It needs API keys to do anything, so all keys are required (see Step 4).

---

## Step 1: Check prerequisites

Run each of the following checks. If any fail, install the missing dependency before continuing.

**Python 3.9+**
```bash
python3 --version
```
If missing or below 3.9: direct the user to https://python.org/downloads

**git**
```bash
git --version
```
If missing: direct the user to https://git-scm.com

Note: this app uses the **`nimble-python` SDK** (installed via `requirements.txt` in Step 3) — the Nimble CLI is not required.

---

## Step 2: Clone the repo

Check whether the repo is already cloned locally:

```bash
ls cookbook
```

**If the directory exists** — navigate into it and pull the latest:
```bash
cd cookbook && git pull
```

**If it does not exist** — clone it:
```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook
```

Then enter the app folder:
```bash
cd apps/financial-comparison-agent
```

---

## Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This installs `nimble-python`, `langchain` + `langgraph` + `langchain-anthropic`, `chainlit`, `supabase`, `pandas`, and `plotly`.

---

## Step 4: Get API keys

All three are required — the agent fetches live data and reasons over it, and persists every run.

**Nimble API key**
Get one at: https://nimbleway.com
Tell the user: used to pull live financials (finviz), discover peers, and find catalysts.

**Anthropic API key**
Get one at: https://console.anthropic.com
Tell the user: used by Claude to curate the peer set, drive the tool loop, and write the verdict.

**Supabase project** (set up in Step 5)
Free tier: https://supabase.com
Tell the user: stores every analysis so past runs can be reopened.

---

## Step 5: Set up Supabase

1. Create a free project at https://supabase.com.
2. In the project, open **SQL Editor → New query**, paste the contents of `supabase_setup.sql`, and run it. This creates the `comps_runs` and `comps_metrics` tables.
3. Go to **Project Settings → API** and copy two values:
   - the **Project URL** (e.g. `https://xxxx.supabase.co`)
   - a **`service_role`** key (or an `sb_secret_…` secret key) — *not* the anon/publishable key. It writes from the backend and bypasses Row-Level Security, so no RLS policies are needed.

---

## Step 6: Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in all four values:
```
NIMBLE_API_KEY=their_nimble_key_here
ANTHROPIC_API_KEY=their_anthropic_key_here
SUPABASE_URL=https://their-project.supabase.co
SUPABASE_KEY=their_service_role_or_secret_key
```

---

## Step 7: Launch the app

```bash
chainlit run app.py
```

The dashboard opens at http://localhost:8000

---

## Step 8: Orient the user

Walk the user through the experience:

1. **Start screen** — clickable **starter cards** ("Analyze Chipotle (CMG)", CRM, NKE, NVDA) for a fresh analysis, plus **"Reopen …" cards** for any past runs saved in Supabase.

2. **Run an analysis** — type a US stock **ticker** (e.g. `CMG`) or click a starter. A **live progress feed** shows the agent working: its reasoning, each Nimble tool call with arguments, the data coming back, and a ticking heartbeat so it never looks stuck.

3. **The result** — a **verdict** (one-line stance + bulleted highlights), an interactive **comps table** (target ★ + a peer-median row), an **EV/EBITDA-vs-peers chart**, and recent **catalysts**.

4. **Follow-up questions** — after a result, just ask. The agent keeps its tools, so questions like *"add SHAK to the comparison"* or *"latest news on CAVA?"* trigger fresh Nimble calls; *"why does CMG trade above the median?"* is answered from data already gathered.

5. **🔄 New analysis** — click to start a fresh ticker. Every run is saved to Supabase and reappears as a "Reopen" starter card.

---

## Notes

- Reasoning model is `claude-sonnet-4-6` (override with `COMPS_MODEL` in `.env`) — fast and cost-effective for the tool loop.
- **Numbers are deterministic**: valuation multiples are parsed from finviz with regex, never re-typed by the LLM. The agent curates peers and writes the verdict; the table numbers are authoritative.
- Three Nimble surfaces power the data: **Extract** (finviz financials), **Search** general + `include_answer` (peer discovery), and **Search** news focus (catalysts).
- `USE_LIVE=false` in `.env` serves cached tool responses from `data/cache/` instead of making live calls.
