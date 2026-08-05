# Setup: Tariff Desk (Nimble × LlamaIndex)

You are helping the user set up and run the Tariff Desk cookbook. Follow these steps in order.
Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

**Python 3.10 or later.** `llama-index-tools-nimble` requires it.

```bash
python3 --version
```

If it reports 3.9 or lower, ask the user to install a newer Python (`brew install python@3.12` on
macOS) and use that interpreter explicitly for every command below.

**git**

```bash
git --version
```

Tell the user they will need three API keys, and that step 4 covers where to get each one:

- **Nimble** — every fact in the corpus comes from a Nimble Web Search Agent run
- **Anthropic** — parses the question and writes the answer from retrieved facts
- **OpenAI** — embeddings only, a fraction of a cent for this corpus

---

## Step 2 — Clone the repo

If a `cookbook` directory already exists, pull instead of cloning.

```bash
if [ -d cookbook ]; then cd cookbook && git pull && cd ..; else git clone https://github.com/Nimbleway/cookbook; fi
cd cookbook/apps/llamaindex-tariff-desk
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

Takes 1–3 minutes. Use `./.venv/bin/python` for every command from here — do not rely on an
activated shell.

Confirm the integration is present:

```bash
./.venv/bin/python -c "import llama_index.tools.nimble as m; print('ok', [n for n in dir(m) if n.endswith('ToolSpec')])"
```

Expect `ok ['NimbleAgentToolSpec', 'NimbleToolSpec']`.

> `requirements.txt` pins `starlette<1` deliberately. Streamlit permits a newer Starlette that
> breaks its own middleware, and the failure is nasty: every page returns a 500 while the health
> endpoint stays green, so it looks like a browser or network problem. Do not relax that pin.

---

## Step 4 — Get API keys

Tell the user where to get each key and what it is for in this app:

1. **`NIMBLE_API_KEY`** — https://online.nimbleway.com/settings/api-keys (free trial available).
   Runs the Web Search Agents that establish every tariff fact in the corpus.
2. **`ANTHROPIC_API_KEY`** — https://console.anthropic.com/settings/keys. Turns a plain question
   into a tariff code plus origin, and writes the final answer from the retrieved facts.
3. **`OPENAI_API_KEY`** — https://platform.openai.com/api-keys. Embeddings only
   (`text-embedding-3-small`). The account needs a positive balance — an unfunded key returns
   `429 insufficient_quota` and the index cannot build.

---

## Step 5 — Configure environment

```bash
cp .env.example .env
```

Then edit `.env` and fill in the three keys:

```
NIMBLE_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

Leave `USE_LIVE=false` for now — that replays the shipped corpus and makes no billable calls.
Leave the three agent-id lines empty; the next step writes them.

---

## Step 6 — Provision the three agents

```bash
./.venv/bin/python setup_agents.py
```

Takes about 10 seconds. It creates three Web Search Agents, verifies each with a `GET`, and writes
their ids into `.env`. Expect three `created wsa_...` lines followed by `verify:` lines showing
non-zero `goals`, `sources.allow` and `schema=Y`.

It is safe to re-run: ids already in `.env` are skipped rather than duplicated.

Ask the user to confirm all three verified before continuing. If any line reports `sources.allow=0`,
stop — source restriction is load-bearing here and an empty allow list means the agent reads the
open web.

---

## Step 7 — Build the index

```bash
./.venv/bin/python build_index.py
```

Takes about 10 seconds and embeds the 17 shipped records. Expect a `document(s) added` list and a
coverage line naming 7 tariff codes.

This is the only step that needs the OpenAI key. If it fails with `insufficient_quota`, the account
needs a balance; everything else in the app works without it.

---

## Step 8 — Run the app

```bash
./.venv/bin/streamlit run app.py
```

Opens on http://localhost:8501. If the page fails to load while the terminal looks healthy, check
the Starlette pin from step 3.

---

## Step 9 — Orient the user

Walk them through it:

**The question box.** Ask about a product and where it's coming from. Try:

- `What's the duty on HTS 8507.60.00 from China?` — answers instantly from the corpus, with the base
  rate and each duty overlay separated, cited and dated
- `What's the duty on 6109.10.00 from India?` — the shipped corpus has this one deliberately
  expired, so the freshness guard withholds the stale overlay instead of answering from it
- `What's out of date?` — answered from index metadata, no agent run
- `What's the tariff on batteries from Vietnam?` — no tariff code, so it declines to guess one

**The code lookup.** Expand *"Don't know the tariff code?"* and try `lithium-ion battery packs` or
`stainless steel insulated drinks bottle` — both cached. Point out that candidates are quoted from
the official schedule, each cited, and that the app never picks one for you.

**The sidebar.** Coverage grouped by product, with each fact's age and whether it is inside its
shelf life. The change log shows what moved the last time something was re-researched.

**To see research actually happen**, set `USE_LIVE=true` in `.env`, restart, and ask about a
product-and-origin not in the corpus. Two agent runs fire, a few minutes each, and the result joins
the index automatically. Warn the user this costs Nimble credits.

---

## Notes

- **Runs take minutes, not seconds.** A base-rate run is 30–90s; an overlay run at `high` effort is
  2–5. The app runs them on background threads and shows progress; closing the tab does not cancel
  them.
- **A timed-out run is not a lost run.** `recover_runs.py` reconciles anything still in flight
  against the agent's run history and files the result when it lands.
- **Never re-submit an ambiguous create.** If a run fails with `NimbleAgentCreateAmbiguousError`, a
  billable run may already exist with no id. Reconcile in the dashboard instead.
- **`confidence` is not completeness.** A run returns `high` while leaving facts in `unverified`.
  The UI shows both; so should anything built on this.
- **Cached lookups cover six products.** Anything else needs `USE_LIVE=true`.
- **The tests need no keys:** `./.venv/bin/python -m pytest tests/ -q` runs 31 checks against the
  shipped corpus with no network calls.
- **This is a demonstration, not a compliance reference.** Figures are a dated snapshot of what the
  agents found, unreviewed by a customs professional.
