# Comps Agent — Code Walkthrough

## File structure

```
comps-agent/
│
├── app.py          Chainlit dashboard — UI, live streaming, history reload
├── agent.py        LangGraph ReAct agent + comps assembly
├── tools.py        3 Nimble tools (Extract + Search)
├── parse.py        finviz markdown → exact numbers
├── schema.py       Pydantic models + peer-median math
├── storage.py      Supabase persistence (runs + metrics)
├── config.py       env, model, USE_LIVE flag
│
├── public/         logos, style.css, new.svg, history.svg
├── data/cache/     cached API responses (video-safe mode)
└── .env            NIMBLE / ANTHROPIC / SUPABASE keys
```

The pipeline: **tools → agent → assemble → render**.

---

## 1 · The three Nimble tools
*`tools.py` — one SDK, three jobs*

```python
@tool
def get_financials(ticker):
    # Nimble EXTRACT — exact multiples from finviz
    res = _nimble().extract(url=FINVIZ_URL, render=True, formats=["markdown"])

@tool
def find_peers(company):
    # Nimble SEARCH (general) — AI-discovered peers
    res = _nimble().search(query=f"{company} competitors and peers", focus="general")

@tool
def get_catalysts(ticker):
    # Nimble SEARCH (news) — recent dated headlines
    res = _nimble().search(query=f"{ticker} earnings analyst", focus="news")
```

> **Extract** pulls the hard numbers. **Search** handles discovery and news.

---

## 2 · The core idea: model judges, figures are deterministic
*`agent.py`*

```python
def assemble_comps(plan):
    companies = [_metrics_from_finviz(target)]      # numbers ← finviz
    for ticker in plan.peer_tickers:                # tickers ← the LLM
        companies.append(_metrics_from_finviz(ticker))
```

> The agent only chooses *which* companies to compare.
> Every financial figure is parsed deterministically — the table can't hallucinate.

---

## 3 · The agent — a ReAct loop in 3 lines
*`agent.py`*

```python
def build_agent():
    llm = ChatAnthropic(model=config.MODEL)
    return create_react_agent(llm, tools=TOOLS, prompt=SYSTEM_PROMPT)
```

> Claude + 3 tools + a prompt. LangGraph runs reason → call tool → observe until done.

---

## 4 · The payoff: table + chart + verdict
*`app.py` — `render_comps()`*

```python
async def render_comps(comps):
    await cl.Message(
        content=f"## {comps.target_ticker}\n#### Verdict\n{comps.verdict}",
        elements=[
            cl.Dataframe(data=comps_dataframe(comps)),   # comps table
            cl.Plotly(figure=ev_ebitda_chart(comps)),    # EV/EBITDA vs peers
        ],
    ).send()
```

> The final answer is three things: a **comps table**, an **EV/EBITDA chart** with a
> dashed peer-median line, and the agent's **verdict** — all from one `ComparableSet`.
