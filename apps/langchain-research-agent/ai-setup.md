# AI Setup — LangChain Gap Filler

Drop this file into Claude Code (or any coding agent) and follow it top to bottom. It fills the
missing fields in a company list and records where every answer came from.

## Step 1 — Check prerequisites

**Python 3.10 or newer is mandatory.** `langchain-nimble` 4.x declares `>=3.10`, and macOS ships
3.9. On 3.9 pip fails with `No matching distribution found for langchain-nimble>=4.0.0`, which reads
like the package doesn't exist — it does, the interpreter is just too old.

```bash
python3 --version          # if this says 3.9.x, find a newer one:
python3.12 --version || python3.13 --version || python3.11 --version
```

Use whichever 3.10+ interpreter you have in the next step.

## Step 2 — Clone and enter the app

```bash
git clone https://github.com/Nimbleway/cookbook.git
cd cookbook/apps/langchain-research-agent
```

## Step 3 — Install dependencies

```bash
python3.12 -m venv .venv          # substitute your 3.10+ interpreter
.venv/bin/pip install -r requirements.txt
```

## Step 4 — Fast path: see it work with no keys

```bash
.venv/bin/python fill_gaps.py
```

This replays a cached result and writes `data/filled.csv`. No API calls, no keys. Open that file:
six companies, 20 previously-empty cells filled, and three sidecar columns beside each value showing
the source, the confidence and which tier answered.

Three cells stay empty on purpose. The app leaves a hole rather than guessing.

## Step 5 — Get keys for a live run

- **Nimble API key** — https://online.nimbleway.com/account-settings/api-keys (free trial available)
- **Anthropic API key** — for the routing model. Optional: without it the app skips the cheap search
  tier and sends every blank to a cited research run, which works but costs more.

```bash
cp .env.example .env
# edit .env and fill in NIMBLE_API_KEY and ANTHROPIC_API_KEY
```

## Step 6 — Live run on the sample data

```bash
USE_LIVE=true .venv/bin/python fill_gaps.py
```

Expect 4–6 minutes. You will see the escalation as it happens:

```
Ramp       headquarters     tier 2 search    22.7s  unverified
Vanta      employee_count   tier 3 agent    235.0s  high
```

Tier 2 is a quick Nimble Search the model chooses to make. Tier 3 is a Nimble Web Search Agent run —
minutes, but every value comes back with a citation and a confidence grade.

On the first live run the app creates its own enrichment agent and records it in `data/agent.json`.
Subsequent runs reuse it.

## Step 7 — Run it on your own file

```bash
USE_LIVE=true .venv/bin/python fill_gaps.py --input mylist.csv --key-column company
```

Requirements for your CSV: a header row, one column holding the entity name, and empty cells where
you want values. Your column names pass through to the output verbatim.

Useful flags:

- `--governed employee_count,funding_stage,total_raised` — columns that must come from a cited
  research run and are never answered by cheap search. This is the default; see the note below.
- `--chunk 10` — how many companies go into each research run.

## Step 8 — Read the output

`data/filled.csv` has your original columns plus, for each one, `<col>__source`,
`<col>__confidence` and `<col>__tier`.

Tier values tell you what happened:

| tier | meaning |
|---|---|
| `file` | you supplied it — nothing was fetched |
| `search` | quick Nimble Search; confidence reads `unverified` |
| `agent` | Nimble Web Search Agent run; confidence is graded from the run's own trust data |
| empty | could not be confirmed, deliberately left blank |

## Notes

**Why `--governed` exists.** `NimbleSearchTool` accepts no domain filter, so the agent's source
allow-list governs the research tier only. Left to itself the model answered `funding_stage` and
`total_raised` from whatever it found — including sources outside the allow-list — despite a system
prompt telling it not to. Prompt instructions are not a control surface, so those columns are
withheld from cheap search in code. Widen or narrow it with `--governed`.

**Why the agent is built from scratch.** The `lead-enrichment` gallery template is configured for one
specific company, so cloning it inherits a source allow-list that cannot answer questions about
anything else. This app creates its own agent, using source groups with empty `domains` arrays —
which express priority as a category hint without whitelisting anyone out.

**Two API details worth knowing if you adapt this.** `output_schema` is required when `use_case` is
`enrichment`, and a per-run `output_schema` override is honoured in full — which is how your CSV
header becomes the agent's schema without creating a new agent per file.
