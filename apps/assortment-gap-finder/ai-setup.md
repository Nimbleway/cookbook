# AI Setup — Assortment Gap Finder

You are helping the user set up and run Assortment Gap Finder: a Nimble Web Search Agents app that builds a 300+ SKU retail catalog in Databricks, finds assortment gaps where catalog math and customer complaints agree, verifies each gap against a retailer's live shelf, and files the survivors as Linear tickets. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

```bash
python3 --version    # need 3.10+
git --version
```

Account-level prerequisites — confirm with the user:
- **Nimble API key** (nimbleway.com) — powers all three research agents.
- **Databricks workspace** — Free Edition works; on a company workspace the user needs a Unity Catalog they can create schemas in.
- **Linear workspace** — free plan works. Suggest a dedicated team so demo tickets stay contained, and a clean team key (the issue prefix, e.g. GAP).
- **Anthropic API key** — drives the synthesis agent loop.

---

## Step 2 — Clone the repo

```bash
if [ -d cookbook ]; then cd cookbook && git pull; else git clone https://github.com/Nimbleway/cookbook && cd cookbook; fi
cd apps/assortment-gap-finder
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2–3 minutes; `databricks-sql-connector` and `litellm[proxy]` are the heavy ones. (`litellm[proxy]` looks odd but is required: LiteLLM's tool-calling path imports proxy modules it does not declare.)

---

## Step 4 — Get credentials

For each, tell the user where it lives and what it does in this app:

1. **NIMBLE_API_KEY** — "All three agents run on this: catalog discovery, review mining, live-shelf verification." From the Nimble dashboard.
2. **Databricks** — "The catalog, quotes, and verdicts live in Delta tables."
   - `DATABRICKS_HOST`: the workspace URL up through `.databricks.com`.
   - `DATABRICKS_TOKEN`: avatar → Settings → Developer → Access tokens → Generate.
   - `DATABRICKS_HTTP_PATH`: SQL Warehouses → pick one → Connection details → HTTP path.
   - `DATABRICKS_CATALOG`: a Unity Catalog the user can create a schema in (`main` on fresh workspaces).
3. **Linear** — "Verified gaps get filed here as tickets - the agent acts, not just reports."
   - `LINEAR_API_KEY`: Settings → Security & access → Personal API keys.
   - `LINEAR_TEAM_KEY`: the team's issue prefix (Settings → Teams → Identifier). Warn the user: Linear auto-generates keys from the team name and the result can be unfortunate - have them pick the identifier deliberately (e.g. GAP).
4. **ANTHROPIC_API_KEY** — "Claude runs the synthesis loop: proposing gaps, deciding what to verify, filing tickets." From console.anthropic.com.

---

## Step 5 — Configure environment

```bash
cp .env.example .env
```

Fill every line; show the user the file and confirm before continuing.

---

## Step 6 — Create the agents and the tables

```bash
python setup_agents.py   # ~10s; creates 3 agents, ids saved to agents.json
python delta.py          # ~30s; creates the schema + 5 Delta tables
```

Ask the user to confirm both ran clean. Both are idempotent.

---

## Step 7 — Build the catalog

```bash
python discover.py
```

6 chunked discovery runs, 3 concurrent, **~50 minutes**, resumable (rerun skips completed chunks; a failed chunk retries automatically). Success = the final line reports 300+ distinct SKUs. Then:

```bash
python gaps.py           # instant: the whitespace grid + flagged candidate cells
```

---

## Step 8 — Mine demand and run the synthesis loop

```bash
python mine.py           # ~15-25 min: verbatim review quotes for flagged cells
python synth.py          # ~30-60 min: Claude proposes gaps, verifies each on a live shelf, files tickets
```

`synth.py` prints a final summary table: hypotheses, verdicts, filed ticket ids. Refuted hypotheses are normal and good — they mean the verifier found real counterexamples. Expect 2–4 filed tickets.

---

## Step 9 — Launch and orient the user

```bash
streamlit run app.py
```

Walk them through, in this order (it's the narrative arc):
1. **Catalog & whitespace** — 300+ SKUs and the gap grid
2. **Customer evidence** — verbatim complaints grouped by flagged cell
3. **Gap board** — verdicts with evidence and Linear ticket links
4. **Their Linear team** — open a filed ticket; the full evidence body is in it
5. **Teach the analyst** — add a rule (e.g. "always name a capacity in gap statements"); it PATCHes the verifier agent permanently

---

## Notes

- Live runs vary: chunk yields and verdicts differ run to run; the deterministic parts (dedup, whitespace math) do not
- Delta writes go through parameterized inserts; the app normalizes Databricks' lowercase column names internally
- Cost: full pipeline ≈ 14 agent runs (6 discovery, 2-3 mining, ~5 verification)
- If a discovery chunk fails twice with "array output is empty", split it by price band in `config.CHUNKS` (e.g. "espresso machines under $150" / "over $150")
