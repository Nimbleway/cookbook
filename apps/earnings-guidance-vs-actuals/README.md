# earnings-guidance-vs-actuals — Earnings Guidance vs Actuals

Ticker watchlist in, audit-grade guidance-vs-delivery scorecard out. A research agent built on [Nimble](https://nimbleway.com) Web Search Agents reconstructs what each company's management guided for every fiscal quarter — from archived earnings releases, SEC filings, and call transcripts — pairs it with what was actually reported, and grades every quarter beat / miss / inline with a citation behind every number. The ledger lives in Snowflake and grows with every run.

![Built with Nimble + Snowflake](https://img.shields.io/badge/Built%20with-Nimble%20%2B%20Snowflake-edc602)

## What it does

1. **Research** — one Web Search Agent ("Guidance Scorecard Agent", a sell-side-analyst persona) researches each ticker's guidance and actuals, 4 quarters per run, with field-level trust claims
2. **Backfill** — `backfill.py` batches the full watchlist (12 tickers × 8 quarters = 24 runs, 4 concurrent, resumable) so the longitudinal dataset exists on day one — no waiting for earnings season
3. **Grade** — `ingest.py` parses guided ranges deterministically ("$26.0B–$26.5B", "±2%"), computes beat/miss/inline per metric app-side, and refuses to grade scale-mismatched comparisons (percent guidance vs dollar actuals) rather than fabricate verdicts
4. **Store** — three Snowflake tables (runs, ledger, claims) plus a headline view that handles every guidance style: formal ranges, segment-level guidance, and outlook-only companies
5. **Act** — scorecards post to Slack via webhook after each ticker lands
6. **Ask** — natural-language questions answered two ways: Claude writes SQL over the ledger (LlamaIndex), or new questions go back to the live agent with the ticker's research context (multi-turn)

## Stack

- [Nimble Web Search Agents](https://nimbleway.com) — the research layer: cited, schema-conforming answers with per-claim trust
- [Snowflake](https://snowflake.com) — the guidance ledger (3 tables + headline views)
- [LlamaIndex](https://llamaindex.ai) — NL→SQL query engine over the ledger
- [Anthropic Claude](https://anthropic.com) — powers the Ask-the-Desk SQL lane
- [Streamlit](https://streamlit.io) — scorecard grid, company drill-down, Ask the Desk

## Setup

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/earnings-guidance-vs-actuals
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Keys you need:
- `NIMBLE_API_KEY` — get one at [nimbleway.com](https://nimbleway.com)
- Snowflake account + user (a free trial works; see `.env.example` comments for the account-identifier format and MFA notes)
- `SLACK_WEBHOOK_URL` — an incoming webhook (api.slack.com/apps → Incoming Webhooks)
- `ANTHROPIC_API_KEY` — for the NL→SQL lane

Then, in order:

```bash
python setup_agent.py      # creates the Web Search Agent (once; id saved to agents.json)
python setup_snowflake.py  # creates warehouse, database, tables, views (idempotent)
python backfill.py         # 24 research runs, ~60-90 min, resumable - rerun to retry failures
python ingest.py           # parse + grade + load the ledger
streamlit run app.py
```

## Usage

Open the app → **Scorecard** shows the 12-ticker verdict grid (latest 8 quarters each). Drill into a company for per-metric guided-vs-actual rows with source links. Ask the Desk: *"Which company beat revenue guidance most often?"* runs as SQL over the ledger; *"Why did IBM defer its full-year outlook?"* goes to the live agent as new research (5–10 min).

To add a quarter after the next earnings day, run `backfill.py <TICKER>` — same code path, the ledger MERGEs idempotently.

## Project structure

```
├── config.py           # watchlist (with per-company guidance-style notes), paths, env
├── setup_agent.py      # creates the Guidance Scorecard Agent (full config inline)
├── setup_snowflake.py  # warehouse + EARNINGS_DESK.LEDGER schema + headline views
├── wsa.py              # Web Search Agents client: start/poll/fetch with 408-retry
├── backfill.py         # batch engine: chunked, concurrent, resumable
├── ingest.py           # deterministic parsing, verdict grading, claim-URL repair, MERGE
├── slack_post.py       # scorecard → Slack webhook
├── ask.py              # Ask the Desk: LlamaIndex NL→SQL lane + live multi-turn lane
├── app.py              # Streamlit UI (3 pages)
└── data/sample_run/    # one verbatim agent result (MSFT) showing the output shape
```

## Output

`EARNINGS_DESK.LEDGER.GUIDANCE_LEDGER` — one row per (ticker, fiscal_quarter, metric):

| column | type | description |
|---|---|---|
| ticker, fiscal_quarter, report_date | STRING/DATE | company fiscal label + calendar report date |
| metric, metric_raw | STRING | normalized + verbatim metric name |
| guided_value_raw, guided_range_raw | STRING | guidance exactly as management stated it |
| guided_low, guided_mid, guided_high | FLOAT | deterministically parsed range (NULL when guidance is qualitative) |
| actual_value_raw, actual_value_num | STRING/FLOAT | reported result, verbatim + parsed |
| metric_verdict | STRING | beat / miss / inline / not_guided — computed app-side |
| quarter_verdict | STRING | the agent's own quarter-level verdict (cross-check) |
| guidance_source_url, actual_source_url | STRING | full public URLs |

Plus `RUNS` (one row per agent run, raw result as VARIANT, interaction ids for multi-turn) and `CLAIMS` (field-level provenance: JSON path, confidence, citation URL, excerpt — the audit trail).

## Going further

- **Change the watchlist** — edit `WATCHLIST` in `config.py`; the fiscal notes matter (companies that guide qualitatively or full-year need their style described, or runs come back thin)
- **Different metrics** — extend the agent's `output_schema` in `setup_agent.py`
- **Schedule the append** — run `backfill.py <TICKER>` from a scheduler after each earnings date; the production story is a Monitor-style always-current ledger

## Notes

- `not_guided` means "management did not guide this" — deliberately distinct from data gaps; grading qualitative commentary would be fabrication, so the app refuses
- Live runs vary: a repeated backfill can return slightly different metric coverage per quarter; `ingest.py` flags runs with fewer than 4 quarters as degraded so they can be re-run
- Agent effort is pinned to `high` — lower tiers fail; a 4-quarter run takes 8–16 minutes
