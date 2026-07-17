# AI Setup — Earnings Guidance vs Actuals

You are helping the user set up and run Earnings Guidance vs Actuals: a Nimble Web Search Agents app that builds an audit-grade guidance-vs-delivery scorecard for a stock watchlist, stores it in Snowflake, posts scorecards to Slack, and answers questions over the ledger. Follow these steps in order. Check each prerequisite before proceeding. Tell the user what you're doing at each step.

---

## Step 1 — Check prerequisites

Run each check; help the user install anything missing.

```bash
python3 --version    # need 3.10+
git --version
```

Account-level prerequisites — confirm with the user before continuing:
- **Nimble API key** — from their Nimble workspace (nimbleway.com). Used for every research run.
- **Snowflake account** — a free trial (no credit card) works, or a company account. The user needs a role that can create a database and warehouse (trial default works; on company accounts ask for SYSADMIN or similar).
- **Slack workspace** where they can add an incoming webhook.
- **Anthropic API key** — used only by the Ask-the-Desk SQL lane.

---

## Step 2 — Clone the repo

```bash
if [ -d cookbook ]; then cd cookbook && git pull; else git clone https://github.com/Nimbleway/cookbook && cd cookbook; fi
cd apps/earnings-guidance-vs-actuals
```

---

## Step 3 — Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Takes 1–2 minutes (Snowflake connector and LlamaIndex are the heavy ones).

---

## Step 4 — Get API keys

For each key, tell the user where to get it and what it does in this app:

1. **NIMBLE_API_KEY** — Tell the user: "This powers the research agent — every guidance/actuals run is a Nimble Web Search Agents run with per-claim citations." Get it from the Nimble dashboard.
2. **Snowflake credentials** — Tell the user: "Snowflake holds the guidance ledger — three tables that grow with every run." Gotchas that cost real time, handle them proactively:
   - The account identifier in Snowsight copies as `ORGNAME.ACCOUNTNAME` — the connector needs `ORGNAME-ACCOUNTNAME` (dash, not dot).
   - If the org enforces MFA on passwords, password auth will fail with "MFA with TOTP is required". Switch to key-pair auth: generate a key (`openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out .keys/snowflake_rsa_key.p8 -nocrypt`), print the public key (`openssl rsa -in .keys/snowflake_rsa_key.p8 -pubout`), have the user run `ALTER USER <name> SET RSA_PUBLIC_KEY='<key body>';` in a Snowsight SQL sheet, and set `SNOWFLAKE_PRIVATE_KEY_PATH=.keys/snowflake_rsa_key.p8` in `.env`.
   - On company accounts the default role often cannot create databases — set `SNOWFLAKE_ROLE=SYSADMIN` (or whatever elevated role the user has).
3. **SLACK_WEBHOOK_URL** — Tell the user: "Scorecards get posted here — the agent acts, not just reports." Create at api.slack.com/apps → New App → Incoming Webhooks → Add to a channel; copy the `https://hooks.slack.com/services/...` URL.
4. **ANTHROPIC_API_KEY** — Tell the user: "Claude writes SQL over the ledger for natural-language questions." From console.anthropic.com.

---

## Step 5 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill every non-optional line. Show the user the file and confirm each value is set before continuing.

---

## Step 6 — Create the agent and the ledger

```bash
python setup_agent.py      # ~5s; prints the new agent id, saved to agents.json
python setup_snowflake.py  # ~30s; creates warehouse EARNINGS_WH, database EARNINGS_DESK, 3 tables + 2 views
```

Ask the user to confirm both ran without errors before continuing. `setup_snowflake.py` is idempotent — safe to rerun after fixing credentials.

---

## Step 7 — Backfill the ledger

```bash
python backfill.py
```

This is the long step: 24 research runs (12 tickers × 2 four-quarter chunks), 4 concurrent, **60–90 minutes total**. Each run prints progress. The loop is resumable — if anything fails or is interrupted, rerun the same command; completed chunks are skipped. To test the pipe quickly first, run a single ticker: `python backfill.py MSFT` (~15 min).

Then load the ledger:

```bash
python ingest.py           # ~2 min; prints rows + claims per file
```

If ingest flags any file as `DEGRADED RUN`, delete that file from `data/raw/` and rerun `backfill.py <TICKER>` — some companies' guidance styles occasionally produce thin runs.

---

## Step 8 — Launch

```bash
streamlit run app.py
```

Opens at http://localhost:8501. Success = the Scorecard page shows a verdict grid with one row per ticker.

---

## Step 9 — Orient the user

Walk them through:
- **Scorecard** — the verdict grid (latest 8 quarters per ticker) and track records. Point out the honest gaps: companies like banks show n/a where they genuinely issue no numeric guidance.
- **Company drill-down** — pick NVDA or MSFT: per-metric guided vs actual with source links; the basis label in each quarter header says how the verdict was derived. The 📣 button posts that scorecard to Slack.
- **Ask the Desk** — suggest trying:
  1. "Which company beat revenue guidance most often?" (SQL lane, ~30s, shows the generated SQL)
  2. "Show MSFT's guided vs actual revenue by quarter" (SQL lane)
  3. "What did management say about next quarter's margins?" with a ticker selected (live lane — a real research run, 5–10 minutes)

---

## Notes

- Live agent runs vary in coverage run-to-run; the deterministic grader marks anything unverifiable as `not_guided` rather than guessing.
- The Snowflake session self-heals on token expiry; the warehouse auto-suspends after 60s idle, so cost is minimal.
- Backfill cost: ~24 Nimble runs at high effort. Ask-the-Desk live questions are one run each.
- If a run fails with "array output is empty", the company's guidance style needs a better fiscal note in `config.py` — see the JNJ/AAPL entries for examples.
