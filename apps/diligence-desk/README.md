# Diligence Desk

Turn a company name into an audit-grade diligence memo — researched by a Nimble Web Search Agent, reviewed by a CrewAI crew, delivered as a PDF to the deal team's inbox. Every claim cited, every verdict evidenced, and an analyst that permanently learns your firm's diligence rules.

Built on [Nimble Web Search Agents](https://nimbleway.com) — the `research` use case at maximum effort: hundreds of sources synthesized into one judgment, with claim-level citations as the audit trail.

## What it does

1. **Research** — a Diligence Analyst agent (cloned from Nimble's `due-diligence` template, customized) investigates the target across SEC EDGAR, Crunchbase, PitchBook, LinkedIn, court records, and the press. One run, 10–20 minutes, every field cited.
2. **Verdict** — the memo leads with a judgment: `proceed`, `proceed_with_conditions`, `caution`, or `do_not_proceed`, with a rationale tied to specific findings.
3. **Review** — a CrewAI crew audits the research: a QA analyst checks it against acceptance criteria, a Risk Officer flags load-bearing claims resting on weak evidence, an Editor writes the partner-ready narrative.
4. **Act** — the app generates a PDF memo (verdict badge, risk table, evidence-gap appendix, full citation appendix) and emails it to the deal team via Resend.
5. **Ask anything** — follow-up questions re-enter the live agent with the memo's research context (`previous_interaction_id`). New research, not chat over stored data.
6. **Learn** — standing instructions from analysts are PATCHed into the agent itself. *"Always check EU regulatory exposure"* becomes permanent behavior, with an auditable learning log.

## Stack

| Layer | Technology |
|---|---|
| Research | Nimble Web Search Agents (`/v1/task-agents`, `research` use case, max effort) |
| Evidence | Nimble trust framework — per-claim citations, confidence grades, JSON-path provenance |
| Review crew | CrewAI (QA → Risk Officer → Editor) on Claude `claude-sonnet-4-6` |
| Storage | Supabase (Postgres, free tier) |
| Actions | fpdf2 (PDF memo) + Resend (email, optional) |
| UI | Streamlit |

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/Nimbleway/cookbook
cd cookbook/apps/diligence-desk
pip install -r requirements.txt
cp .env.example .env        # add your keys (see below)
# run supabase/schema.sql in your Supabase SQL editor
python3 setup_agent.py      # creates the Diligence Analyst in your Nimble workspace
python3 -m streamlit run app.py
```

Keys: `NIMBLE_API_KEY` ([get one](https://nimbleway.com)), `ANTHROPIC_API_KEY`, `SUPABASE_URL` + `SUPABASE_KEY`, and optionally `RESEND_API_KEY` for real email sends (without it the app previews the email instead).

**No time for a live run?** Set `USE_LIVE=false` to replay the bundled sample memo — two real diligence runs (Perplexity AI and Mistral AI) with their full trust data — through the same code paths.

For a guided setup, open `ai-setup.md` in Claude Code (or any AI coding assistant) and let it walk you through.

## Project structure

```
diligence-desk/
├── app.py               # Streamlit UI: New memo / Memos / Teach the analyst
├── config.py            # agent config (single source of truth) + app constants
├── setup_agent.py       # idempotent agent create/update
├── wsa.py               # WSA run lifecycle + multi-turn + teach (PATCH)
├── crew.py              # CrewAI review crew
├── actions.py           # PDF memo + email delivery
├── db.py                # Supabase data layer
├── e2e_test.py          # end-to-end test + sample-dataset capture
├── supabase/schema.sql  # four dd_ tables
└── data/sample_run/     # verbatim sample memo for USE_LIVE=false
```

## How the trust framework is used

Every memo field arrives with `trust.claims[]` — each claim carries a JSON path (`$.financial_health.revenue`), a confidence grade, and citations with excerpts. The app:

- stores one row per claim (`dd_claims`) — the queryable audit trail
- badges every memo section with its worst-claim confidence and a count breakdown
- feeds the claims to the Risk Officer, whose evidence-gap list ships inside the PDF
- prints the full citation appendix in the memo — low confidence is flagged, never hidden

## Notes

- Memo runs are real multi-source research and take 10–20 minutes by design; follow-ups run at `high` effort (~5–10 minutes).
- Raw API responses are saved verbatim before any transformation — reprocessing never re-spends research.
- The service_role Supabase key bypasses row-level security; keep it server-side.
