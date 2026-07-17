# AI Setup Guide: Competitor Battlecard Generator

## Goal

Build a competitive battlecard from two company URLs using Nimble Search API for live web research. The output is a structured, source-linked battlecard covering pricing, positioning, reviews, recent launches, funding, SWOT, objection responses, and discovery questions.

## Product framing

The demo value is: live web research plan, raw auditable evidence, and a battlecard UI that makes Nimble look like the data layer for competitive intelligence workflows. V1 is deterministic (no LLM required). Keep it simple.

---

## Setup steps

```bash
cd competitor-battlecard-generator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add NIMBLE_API_KEY to .env if you have one
```

---

## Verification commands

```bash
# compile check
python3 -m py_compile collect.py app.py

# dry-run (no API key needed)
python3 collect.py --dry-run --output /tmp/battlecard-test

# verify output structure
python3 -m json.tool /tmp/battlecard-test/report.json >/dev/null
python3 -m json.tool /tmp/battlecard-test/normalized_evidence.json >/dev/null

# dashboard smoke test
streamlit run app.py
```

---

## Safe customisations

- **Change the companies:** Edit `config/example_config.json` or create a new config and pass it with `--config`.
- **Adjust result count:** Change `max_results` in the config (default 8, max 20).
- **Change search depth:** `search_depth` can be `lite` or `fast`. Use `fast` for quicker runs, `lite` for more results.
- **Add a new query:** Extend `QUERY_PLAN_TEMPLATE` in `collect.py` with a new entry following the existing shape.

---

## Guardrails

- Do not fabricate evidence. If a signal is missing, the report section says "No reliable signal found in this run."
- Do not claim specific G2 scores, pricing numbers, or funding amounts without source-linked evidence.
- Dry-run sample data uses synthetic but representative snippets. It is clearly labeled as dry-run in the dashboard.
- Raw Nimble responses are saved before any transformation. If output looks wrong, inspect `data/<run>/raw/` directly.
- Run resumption is safe: existing raw files are skipped. Delete the raw directory to force a fresh run.
