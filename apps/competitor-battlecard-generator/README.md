# Competitor Battlecard Generator

Turn two company URLs into a live, source-backed competitive battlecard your sales, product marketing, or founder team can use immediately.

---

## What it does

| Stage | What happens |
|---|---|
| Input | Company name + URL, competitor name + URL (JSON config) |
| Research | 12 targeted Nimble Search queries across pricing, positioning, reviews, launches, funding, leadership, and market context |
| Raw cache | Each Nimble response is saved to `data/raw/<query-id>.json` before any processing |
| Evidence normalization | Results flattened to typed evidence records with IDs, confidence scores, and source URLs |
| Battlecard generation | Deterministic synthesis into executive summary, SWOT, objection responses, discovery questions, and do-not-claim list |
| Dashboard | Streamlit UI with tab-based report view, evidence browser, and CSV export |

---

## Quickstart: sample dashboard, no API key

```bash
cd competitor-battlecard-generator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501` with bundled sample data (Linear vs Jira).

---

## Run a dry-run collection

Generates a full battlecard report using representative sample data. No API key needed.

```bash
python3 collect.py --dry-run
```

Output lands in `data/runs/<timestamp>/`. Re-running is safe: existing raw files are skipped.

```bash
python3 collect.py --dry-run --output data/dry_run
```

---

## Run live with Nimble Search API

Copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
# edit .env and set NIMBLE_API_KEY=your_key_here
python3 collect.py --config config/example_config.json
```

The live run fetches 12 queries, caches each raw response immediately, then produces `report.json` and `normalized_evidence.json`.

If the run is interrupted, re-running resumes from where it left off (raw files already on disk are skipped).

---

## Create your own battlecard config

Copy and edit `config/example_config.json`:

```json
{
  "company_name": "Your Company",
  "company_url": "https://yourcompany.com",
  "competitor_name": "Competitor Name",
  "competitor_url": "https://competitor.com",
  "country": "US",
  "locale": "en-US",
  "search_depth": "lite",
  "include_answer": true,
  "max_results": 8
}
```

Then run:

```bash
python3 collect.py --config config/my_config.json --output data/runs/my_run
```

---

## Output files

| File | Description |
|---|---|
| `data/<run>/raw/<query-id>.json` | Raw Nimble API response for each query |
| `data/<run>/normalized_evidence.json` | Typed evidence records with IDs and confidence scores |
| `data/<run>/report.json` | Full battlecard report with all sections |
| `data/<run>/schema.json` | Evidence record field definitions |

---

## Project structure

```
competitor-battlecard-generator/
├── collect.py               # CLI collection, normalization, report generation
├── app.py                   # Streamlit dashboard
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   └── example_config.json  # Linear vs Jira sample config
└── data/
    └── sample_run/          # Bundled dry-run output (works without credentials)
        ├── report.json
        ├── normalized_evidence.json
        ├── schema.json
        └── raw/
```

---

## Stack

- Python 3.9+
- Nimble Search API (`POST /v1/search`) for live web research
- Streamlit for the dashboard
- Pandas + Plotly for data handling and charts
- python-dotenv for secrets

---

## Notes and limitations

- V1 uses deterministic report synthesis. No LLM is required. Adding optional Claude/OpenAI synthesis is a planned follow-up.
- Sample data is generated via dry-run (representative snippets) and is clearly labeled as such in the dashboard. It is not fabricated research.
- Every battlecard claim in a live run carries source URLs and evidence IDs.
- Dry-run responses use realistic but synthetic snippets. Do not treat them as factual research.
- Nimble Search returns snippets from the live web. Some signals may be incomplete or outdated.
- The `site:` operator queries for pricing and positioning pages may return fewer results depending on Nimble index coverage.
