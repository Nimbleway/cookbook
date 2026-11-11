"""Pricing comparison agent (Pattern A).

A LangChain agent extracts each vendor's pricing structure from its own site using
Nimble's Search API. The extraction is all the agent does: normalizing the different
billing units onto one basis and computing a modeled annual cost for a buyer profile is
deterministic code (pricing_model.py), not left to the LLM.

Retrieval note: the search tool calls Nimble's official ``nimble-python`` SDK directly.
See ``agent_api_v2.py`` for the Pattern B version (delegating research to a Nimble Web
Search Agent).
"""

from __future__ import annotations

import datetime as dt
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from nimble_python import Nimble

from config import build_system_prompt
from pricing_model import build_cost_ranking
from schema import PricingComparisonResult, VendorExtractionBatch

load_dotenv()

DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.1")
DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "60"))
CONTENT_CHAR_CAP = int(os.getenv("NIMBLE_CONTENT_CHAR_CAP", "8000"))


def _slice_relevant(content: str, query: str, cap: int) -> str:
    """Keep the query-relevant windows of a long page, not just the head."""
    if len(content) <= cap:
        return content
    win = 1600
    chunks = [content[i : i + win] for i in range(0, len(content), win)]
    terms = {t for t in re.findall(r"[a-z0-9]{4,}", query.lower())}
    order = sorted(range(len(chunks)), key=lambda i: (-sum(t in chunks[i].lower() for t in terms), i))
    keep = {0}
    used = len(chunks[0])
    for i in order:
        if i in keep or used + len(chunks[i]) > cap:
            continue
        keep.add(i)
        used += len(chunks[i])
    return "\n…\n".join(chunks[i] for i in sorted(keep)) + "\n…[sliced to query-relevant sections]"


def _compact(results, query: str, full: bool, cap: int) -> list[dict]:
    out = []
    for r in results or []:
        item = {"title": getattr(r, "title", None), "url": getattr(r, "url", None), "description": getattr(r, "description", None)}
        content = getattr(r, "content", "") or ""
        if full and content:
            item["content"] = _slice_relevant(content, query, cap)
        elif content:
            item["content"] = content[:1200]
        out.append(item)
    return out


def _make_search_tool():
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    @tool
    def nimble_search(
        query: str,
        num_results: int = 6,
        search_depth: str = "standard",
        full_content: bool = False,
        include_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> list[dict]:
        """Search the live web via Nimble. Returns [{title, url, description, content?}].

        search_depth="lite":     metadata only. Use to find the right page (e.g. locate
                                 the changelog URL) before reading it.
        full_content=True:       fetch and extract the full page text, sliced to the
                                 query-relevant sections. Use this for the actual pricing
                                 page and changelog entries you will extract numbers from,
                                 num_results <= 4.
        include_domains:         scope to one vendor's own domain, e.g. ["datadoghq.com"].
                                 Do not search multiple vendors in one call.
        time_range / start_date: bias toward recent changelog entries. Pass one, not both.
        """
        depth = "lite" if search_depth == "lite" else "standard"
        kwargs = {"query": query, "search_depth": depth}
        kwargs["max_results"] = min(num_results, 4) if full_content else num_results
        if full_content:
            kwargs["full_content"] = True
        if include_domains:
            kwargs["include_domains"] = include_domains
        if start_date:
            kwargs["start_date"] = start_date
        elif time_range:
            kwargs["time_range"] = time_range
        scope = f" [{', '.join(include_domains)}]" if include_domains else ""
        print(f"  nimble search: {query!r}{scope}", flush=True)
        try:
            resp = client.search(**kwargs)
        except Exception as exc:
            print(f"    -> error: {exc}", flush=True)
            return [{"error": f"{type(exc).__name__}: {exc}"}]
        out = _compact(resp.results, query, full_content, CONTENT_CHAR_CAP)
        print(f"    -> {len(out)} result(s)", flush=True)
        return out

    return nimble_search


def _make_llm(model: str | None):
    name = model or DEFAULT_MODEL
    kwargs = {} if any(t in name for t in ("gpt-5", "o1", "o3", "o4")) else {"temperature": 0}
    return init_chat_model(name, **kwargs)


def build_agent(vendors: list[str], model: str | None = None, today: str | None = None):
    today = today or dt.date.today().isoformat()
    return create_agent(
        model=_make_llm(model),
        tools=[_make_search_tool()],
        system_prompt=build_system_prompt(today, vendors),
        response_format=VendorExtractionBatch,
    )


def compare(vendors: list[str], buyer_profile: dict, model: str | None = None) -> PricingComparisonResult:
    """Run the agent to extract pricing, then compute the cost model deterministically."""
    today = dt.date.today().isoformat()
    agent = build_agent(vendors, model, today)
    print(f"Starting agent: extracting pricing for {', '.join(vendors)}...", flush=True)
    result = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Extract current pricing for these vendors: {', '.join(vendors)}. "
                    f"For each, find its pricing/plans page and its changelog or release "
                    f"notes. Today is {today}.",
                )
            ]
        },
        {"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    print("Agent finished extracting pricing. Computing cost model...", flush=True)
    batch: VendorExtractionBatch = result["structured_response"]
    ranking, quote_required = build_cost_ranking(batch.vendors, buyer_profile)
    return PricingComparisonResult(
        buyer_profile=buyer_profile,
        as_of_date=today,
        vendors=batch.vendors,
        cost_ranking=ranking,
        quote_required=quote_required,
    )
