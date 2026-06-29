---
font: monospace
header-color: yellow
---

# Financial Comparison Agent — Build Report

A conversational agent that produces **live comparable-company analysis** for US equities: give it a ticker, it discovers public peers, pulls current valuation multiples, surfaces recent catalysts, and delivers a relative-valuation verdict — then answers follow-up questions, fetching fresh data as needed.

---

## The Stack

| Layer | Technology |
|---|---|
| **Live web data** | **Nimble** Web Search Agents — Extract + Search (`nimble_python` SDK) |
| **Reasoning** | **Claude** `claude-sonnet-4-6` (via `langchain-anthropic`) |
| **Agent framework** | **LangChain + LangGraph** — `create_react_agent` (ReAct loop) |
| **Storage** | **Supabase** (Postgres) — `comps_runs` + `comps_metrics` |
| **Dashboard** | **Chainlit** — chat-style agent UI |
| **Language** | **Python 3.9** |

Three Nimble surfaces do the data gathering:

| Tool | Nimble surface | Job |
|---|---|---|
| `get_financials` | **Extract** on finviz | Exact valuation multiples + peer list + analyst actions |
| `find_peers` | **Search** (general + `include_answer`) | Web-sourced peer discovery |
| `get_catalysts` | **Search** (news focus) | Recent dated catalysts |

---

## Logical Process

```
   ticker (typed or starter button)
        │
        ▼
 ┌───────────────────────── LangGraph ReAct agent (Claude) ─────────────────────────┐
 │  1. DISCOVER   find_peers (web)  +  finviz peer list from get_financials(target)   │
 │                └─ Claude curates the true comp set (not just same-sector names)    │
 │  2. FINANCIALS get_financials(target + each peer)  →  finviz, parsed deterministically
 │  3. CATALYSTS  get_catalysts(target/peers)  →  news focus, short query             │
 │  4. SYNTHESIZE Claude writes a one-line stance + bulleted highlights,              │
 │                reasoning over the exact tool numbers                               │
 └───────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
 5. ASSEMBLE   ComparableSet built deterministically — table numbers re-read from
               finviz, never re-typed by the LLM (no number drift)
                                      ▼
 6. PERSIST    write run + per-company metrics to Supabase
                                      ▼
 7. RENDER     Chainlit: live progress feed throughout · comps table · EV/EBITDA
               chart · verdict · catalysts
                                      ▼
 8. FOLLOW-UPS same agent continues with tools intact → "add SHAK", "latest on CAVA?"
               trigger fresh Nimble calls; "🔄 New analysis" resets to a new ticker
```

**Key principle:** the agent *curates peers and writes the verdict* (judgment); the *numbers are deterministic from finviz* (accuracy). Reasoning and data are deliberately separated so the comps table is never subject to LLM error.

---

## Key Technologies — why, and the role each plays

**Nimble — live web data**
- *Why:* only way to get fresh, structured financials for an arbitrary peer set — an LLM can't produce this from training data.
- *Why this one:* one SDK, purpose-built surfaces (Extract + Search focus modes); reliable and fast in testing.
- *Role:* every data point in the analysis originates from a Nimble call.

**Claude (Sonnet 4.6) — reasoning**
- *Why:* the hard parts are judgment (which peers are truly comparable, what the multiples mean), not data retrieval.
- *Why Sonnet over Opus:* faster and far cheaper for a many-call tool loop, fully capable here.
- *Role:* curates the peer set, decides which tools to call, writes the verdict.

**LangChain + LangGraph — agent framework**
- *Why:* `create_react_agent` gives a model-driven loop in minimal code — what makes this an agent, not a fixed pipeline.
- *Bonus:* tools and context persist, so follow-up questions are just another turn that can call Nimble again.
- *Role:* orchestrates the reason → act → observe loop and holds conversational state.

**Supabase — persistence**
- *Why:* zero-friction managed Postgres (free tier, clean Python client).
- *Role:* saves every run (run + per-company metrics) for a browsable, reopenable history.

**Chainlit — dashboard**
- *Why:* purpose-built for agent UIs — live progress feed with a heartbeat (never looks stuck) plus rich result elements.
- *Bonus:* pure Python, no separate frontend to build or deploy.
- *Role:* the entire trigger → monitor → display → follow-up experience.
