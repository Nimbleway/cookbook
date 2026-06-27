"""The Comps Agent: a LangGraph ReAct loop with Claude + three Nimble tools.

The agent curates the peer set and writes the valuation verdict. The numeric
comps table is then assembled deterministically from finviz (see assemble_comps),
so the displayed multiples are never subject to LLM number drift.
"""
from __future__ import annotations

import json
from typing import List, Optional, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

import config
import tools as nimble_tools
from schema import Catalyst, CompanyMetrics, ComparableSet

# Numeric fields copied verbatim from the deterministic finviz parse.
_METRIC_FIELDS = [
    "market_cap_b", "pe", "forward_pe", "ps", "ev_ebitda", "peg", "rev_growth",
    "gross_margin", "op_margin", "profit_margin", "roe", "price_target", "analyst_recom",
]


class CompsPlan(BaseModel):
    """The agent's structured output: which companies, plus its reasoning."""
    target_ticker: str
    target_name: Optional[str] = None
    peer_tickers: List[str] = Field(
        default_factory=list,
        description="Curated public peer tickers for the comps set, EXCLUDING the target.",
    )
    catalysts: List[Catalyst] = Field(
        default_factory=list,
        description="Recent dated catalysts (earnings, guidance, rating changes) for the target and notable peers.",
    )
    stance: str = Field(
        description="A one-line bottom-line call on the target's relative valuation, e.g. "
                    "'Modestly undervalued vs. peers — premium margins aren't fully priced in.'",
    )
    highlights: List[str] = Field(
        default_factory=list,
        description="3-5 short, punchy bullet points supporting the stance. Each is ONE sentence "
                    "comparing the target to the peer median on a specific dimension (a valuation "
                    "multiple, growth, or margins) or citing a recent catalyst or risk. Be specific "
                    "with numbers.",
    )


SYSTEM_PROMPT = """You are an equity research analyst building a comparable-company \
analysis ("comps") for a US-listed stock.

You have three tools:
- get_financials(ticker): exact valuation multiples + finviz's peer list + recent analyst actions.
- find_peers(company): an AI-synthesized list of candidate public peers.
- get_catalysts(ticker, company): recent dated news catalysts. Pass a SHORT keyword query only.

Process:
1. Call get_financials on the TARGET to get its multiples, finviz's peer list, and analyst actions.
2. Call find_peers for additional peer ideas.
3. Curate 4-6 genuinely comparable PUBLIC peers. Use judgment: prefer the same business model, \
size class, and growth profile. finviz often lists large-cap names that aren't the best comps — \
you may include better peers it didn't list, and drop poor ones it did.
4. Call get_financials on each chosen peer.
5. Call get_catalysts for the target (and any peer with a notable recent move). Use short queries \
like "CMG Chipotle earnings analyst".
6. Produce a CompsPlan: the target, the curated peer_tickers (excluding the target), dated \
catalysts (prefer items with dates — the analyst actions from get_financials are dated), a one-line \
`stance`, and 3-5 `highlights`.

`stance` is your one-line bottom-line call (e.g. "Modestly undervalued vs. peers — premium margins \
aren't fully priced in"). Each `highlight` is ONE short sentence comparing the target to the peer \
median on a specific dimension (a valuation multiple, growth, or margins) or citing a recent \
catalyst or risk. Be specific with numbers. Reason only over the exact values the tools return."""


def build_agent():
    """Compile the ReAct agent graph."""
    llm = ChatAnthropic(
        model=config.MODEL,
        max_tokens=4096,
        api_key=config.ANTHROPIC_API_KEY,
    )
    return create_react_agent(
        llm,
        tools=nimble_tools.TOOLS,
        prompt=SYSTEM_PROMPT,
    )


_EXTRACT_DIRECTIVE = (
    "Based on your research above, output the final CompsPlan now: the target ticker and "
    "name, the curated peer_tickers (exclude the target), dated catalysts (prefer items "
    "with dates), a one-line stance, and 3-5 highlight bullets comparing the target to the "
    "peer median (valuation, growth, margins) and noting key catalysts or risks."
)


def extract_plan(messages) -> CompsPlan:
    """Distill the agent's conversation into a structured CompsPlan.

    Done as a separate call that ends on a user turn, so it avoids the assistant-prefill
    restriction that LangGraph's built-in response_format hits with current Claude models.
    """
    extractor = ChatAnthropic(
        model=config.MODEL, max_tokens=4096, api_key=config.ANTHROPIC_API_KEY,
    ).with_structured_output(CompsPlan)
    return extractor.invoke(list(messages) + [HumanMessage(content=_EXTRACT_DIRECTIVE)])


def _metrics_from_finviz(ticker: str, is_target: bool = False,
                         name: Optional[str] = None) -> CompanyMetrics:
    """Build CompanyMetrics from the deterministic finviz parse (cache hit if the
    agent already fetched this ticker)."""
    data = json.loads(nimble_tools.get_financials.invoke({"ticker": ticker}))
    return CompanyMetrics(
        ticker=ticker.strip().upper(),
        name=name or data.get("name"),
        is_target=is_target,
        source_url=data.get("source_url"),
        **{f: data.get(f) for f in _METRIC_FIELDS},
    )


def assemble_comps(plan: CompsPlan) -> ComparableSet:
    """Turn the agent's plan into a ComparableSet with authoritative numbers."""
    target_tk = plan.target_ticker.strip().upper()
    companies = [_metrics_from_finviz(target_tk, is_target=True, name=plan.target_name)]
    seen = {target_tk}
    for tk in plan.peer_tickers:
        tk = tk.strip().upper()
        if tk and tk not in seen:
            seen.add(tk)
            companies.append(_metrics_from_finviz(tk))
    verdict_md = f"**{plan.stance}**"
    if plan.highlights:
        verdict_md += "\n\n" + "\n".join(f"- {h}" for h in plan.highlights)
    return ComparableSet(
        target_ticker=target_tk,
        target_name=plan.target_name or companies[0].name,
        companies=companies,
        catalysts=plan.catalysts,
        verdict=verdict_md,
    )


def run(ticker: str) -> Tuple[ComparableSet, CompsPlan]:
    """Synchronous end-to-end run (used for testing / CLI)."""
    agent = build_agent()
    state = agent.invoke(
        {"messages": [{"role": "user",
                       "content": f"Build a comparable-company analysis for {ticker}."}]},
        config={"recursion_limit": 60},
    )
    plan = extract_plan(state["messages"])
    return assemble_comps(plan), plan
