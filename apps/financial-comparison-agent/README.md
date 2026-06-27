# Financial Comparison Agent

A live **comparable-company analysis** agent for US equities. Give it a ticker; it discovers the company's public peers, pulls current valuation multiples for each, surfaces recent catalysts, and returns a relative-valuation verdict — then lets you ask follow-up questions that can pull fresh data on demand.

Built on **Nimble** Web Search Agents (live web data), **Claude** (reasoning), **LangGraph** (the agent loop), **Supabase** (persistence), and **Chainlit** (the dashboard).

---

## What it does

Type `CMG` and the agent:

1. **Discovers peers** — finds Chipotle's public comparables (CAVA, WING, DPZ, TXRH, SBUX, DRI…).
2. **Pulls financials** — current P/E, forward P/E, P/S, EV/EBITDA, PEG, revenue growth, margins, ROE, and analyst price target for the target and every peer.
3. **Finds catalysts** — recent dated earnings, guidance, and analyst-rating moves.
4. **Delivers a verdict** — a one-line stance plus bulleted highlights comparing the target to the peer median, e.g.:

   > **Modestly undervalued on earnings multiples at a 1-year low, but a PEG of 2.27 — the highest in the peer group — caps upside until growth reaccelerates.**
   > - Forward P/E of 24.6x roughly in line with peer median 25.6x — a notable de-rating from its historical premium.
   > - Operating margin of 15.9% is 520 bps above the peer median of 10.7%.
   > - Revenue growth of 5.7% trails the peer median of 8.6% — the single biggest bear case.

You watch each step run live, get an interactive **comps table** + **EV/EBITDA chart**, and every run is **saved to Supabase** and reopenable. Then you can **ask follow-ups** — *"add SHAK"*, *"latest news on CAVA?"*, *"why does CMG trade above the median?"* — and the agent answers, calling Nimble again whenever it needs more data.

### Why it needs Nimble

The comparison is **cross-sectional** (a company vs. its live peers, right now), so it requires fresh, structured financial data from the web for an arbitrary set of tickers — exactly what an LLM cannot produce from its weights. Nimble is the agent's live-web tool.

---

## How it works

```
ticker ─▶ ┌─────────────────────── LangGraph ReAct agent (Claude) ───────────────────────┐
          │  find_peers ──▶ get_financials (target + peers) ──▶ get_catalysts             │
          │        │                  │                              │                     │
          │   Nimble Search      Nimble Extract                Nimble Search               │
          │   (general +         (finviz, parsed                (news focus)                │
          │    include_answer)    deterministically)                                       │
          └──────────────────────────────┬───────────────────────────────────────────────┘
                                          ▼
                  assemble_comps  ─▶  ComparableSet  ─▶  Supabase (persist)
                  (exact numbers,         │
                   re-read from finviz)   ▼
                                   Chainlit dashboard: live steps · comps table ·
                                   EV/EBITDA chart · verdict · follow-up Q&A
```

The agent **curates the peer set and writes the verdict**; the **numbers in the table are parsed deterministically from finviz**, never re-typed by the LLM — so the comps table is immune to number drift.

### The three Nimble surfaces it showcases

| Tool | Nimble surface | Used for |
|------|----------------|----------|
| `get_financials(ticker)` | **Extract** (`/v1/extract`) on finviz | Exact valuation multiples + finviz's peer list + analyst actions |
| `find_peers(company)` | **Search** (`/v1/search`, general focus, `include_answer=true`) | AI-synthesized peer discovery |
| `get_catalysts(ticker)` | **Search** (`/v1/search`, **news** focus, short keyword query) | Recent dated catalysts |

---

## Project structure

```
financial-comparison-agent/
├── app.py               # Chainlit dashboard: trigger, live steps, table/chart, follow-ups
├── agent.py             # LangGraph ReAct agent, structured output, deterministic assembly
├── tools.py             # The 3 Nimble tools (Extract + Search) + in-memory dedup cache
├── parse.py             # Deterministic finviz parser (exact numbers, no LLM)
├── schema.py            # Pydantic models: CompanyMetrics, ComparableSet, Catalyst
├── storage.py           # Supabase persistence (persist / recent_runs / get_run)
├── config.py            # Env loading, model, USE_LIVE flag
├── supabase_setup.sql   # Table DDL — run once in the Supabase SQL editor
├── requirements.txt
├── .env.example
├── chainlit.md          # Welcome / readme splash
└── public/              # Wordmark logo + custom CSS (branding)
```

---

## Setup

### 1. Prerequisites
- Python 3.9+
- A **Nimble** API key, an **Anthropic** API key, and a free **Supabase** project.

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` and fill in:
```bash
NIMBLE_API_KEY=...          # Nimble Web Search Agent platform
ANTHROPIC_API_KEY=...       # Claude
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=...            # service_role (or sb_secret_...) key — bypasses RLS for backend writes
COMPS_MODEL=claude-sonnet-4-6   # optional; fast & cost-effective for the loop
USE_LIVE=true               # set false to serve cached responses (video-safe demos)
```

### 4. Create the Supabase tables
In your Supabase project: **SQL Editor → New query**, paste the contents of `supabase_setup.sql`, and run it. This creates `comps_runs` and `comps_metrics`.

### 5. Run
```bash
chainlit run app.py
```
Open http://localhost:8000.

---

## Using it

- **Start an analysis** — type a ticker (`CMG`, `CRM`, `NKE`) or click a starter button.
- **Watch it work** — the agent's tool calls stream as a live progress feed.
- **Read the result** — verdict (stance + bullets), interactive comps table (target ★ + peer-median row), and an EV/EBITDA-vs-peers chart.
- **Ask follow-ups** — after a result, just type a question. The agent answers in context and can pull fresh data:
  - *"add SHAK to the comparison"* → fetches SHAK and works it in
  - *"what's the latest on CAVA?"* → pulls recent catalysts
  - *"why does CMG trade above the peer median?"* → answered from gathered data
- **New analysis** — click **🔄 New analysis** to start a fresh ticker.
- **History** — recent runs appear as buttons at the start of a chat; click to reopen.

---

## Design notes

- **Numbers are deterministic.** `parse.py` extracts finviz multiples with regex; the agent reasons over exact values and never re-types them. `assemble_comps` re-reads the parsed numbers when building the final table.
- **Structured output without prefill issues.** Current Claude models reject the assistant-prefill that LangGraph's built-in `response_format` uses, so the agent runs a plain ReAct loop and a *separate* structured-extraction call (ending on a user turn) distills the `CompsPlan`.
- **Bounded & deduped.** The ReAct loop has a recursion limit; an in-memory memo ensures a single analysis never fetches the same finviz page twice.
- **Video-safe.** With `USE_LIVE=false`, tool results are served from `data/cache/` — no live API calls.

## Scope & limitations

- US-listed equities with a finviz quote page.
- **Cross-sectional**, not longitudinal — it compares a company to its peers *now*; it does not track history over time.
- Not investment advice — it automates analyst legwork (gathering and structuring comparable data), it does not predict prices.
