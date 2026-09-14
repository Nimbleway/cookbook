"""Company due-diligence agent (Pattern A).

A LangChain agent that controls the research workflow and uses Nimble's Search API
as its web-retrieval tool. It researches a fixed set of diligence dimensions and
returns a structured DiligenceProfile with a strengths/risks scorecard.

Retrieval note: the tool calls Nimble's official Python SDK (``nimble-python``, the
same client ``langchain-nimble`` wraps) directly, because as of langchain-nimble
4.0.0 the search wrapper does not expose ``full_content`` and its domain-scoped
ranking is weak. ``agent_api_v2.py`` shows Pattern B, which delegates the whole
workflow to a Nimble Web Search Agent.
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
from langgraph.errors import GraphRecursionError
from nimble_python import Nimble

from config import build_system_prompt
from schema import DiligenceProfile

load_dotenv()

# Provider-agnostic: "openai:gpt-5.1", "anthropic:claude-sonnet-5", "google_genai:gemini-2.5-pro", ...
DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.1")
DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "48"))
CONTENT_CHAR_CAP = int(os.getenv("NIMBLE_CONTENT_CHAR_CAP", "8000"))


# Description length kept per result on a scan pass. "standard" depth returns much longer
# descriptions than lite did; trimming them keeps a scan as cheap as it used to be.
SCAN_DESC_CHARS = int(os.getenv("NIMBLE_SCAN_DESC_CHARS", "220"))


def _slice_relevant(content: str, query: str, cap: int) -> str:
    """Keep the query-relevant windows of a long document, not just the head."""
    if len(content) <= cap:
        return content
    win = 1600
    chunks = [content[i : i + win] for i in range(0, len(content), win)]
    terms = {t for t in re.findall(r"[a-z0-9]{4,}", query.lower())}
    order = sorted(
        range(len(chunks)),
        key=lambda i: (-sum(t in chunks[i].lower() for t in terms), i),
    )
    keep = {0}
    used = len(chunks[0])
    for i in order:
        if i in keep or used + len(chunks[i]) > cap:
            continue
        keep.add(i)
        used += len(chunks[i])
    joined = "\n…\n".join(chunks[i] for i in sorted(keep))
    return joined + "\n…[sliced to query-relevant sections of a longer document]"


def _compact(results, query: str, full: bool, cap: int, scan: bool = False) -> list[dict]:
    out = []
    for r in results or []:
        desc = getattr(r, "description", None)
        # A scan only needs enough text to judge which documents are worth reading.
        # "standard" depth returns long descriptions (~1.6 KB/result) where lite returned
        # ~140 chars, so trim them on a scan pass to keep the old context cost.
        if scan and desc and len(desc) > SCAN_DESC_CHARS:
            desc = desc[:SCAN_DESC_CHARS].rstrip() + "…"
        item = {
            "title": getattr(r, "title", None),
            "url": getattr(r, "url", None),
            "description": desc,
        }
        content = getattr(r, "content", "") or ""
        if full and content:
            item["content"] = _slice_relevant(content, query, cap)
        elif content and not scan:
            item["content"] = content[:1500]
        out.append(item)
    return out


def _make_search_tool():
    """Nimble Search API exposed as the agent's one retrieval tool."""
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    @tool
    def nimble_search(
        query: str,
        num_results: int = 8,
        search_depth: str = "standard",
        full_content: bool = False,
        include_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> list[dict]:
        """Search the live web via Nimble. Returns [{title, url, description, content?}].

        search_depth="standard": the depth every request is served at (default). Returns a
                                 short content snippet per result.
        search_depth="lite":     accepted as a "scan" hint — the request is still sent at
                                 "standard" depth and trimmed locally to
                                 title/url/description. Use it to find the right pages for
                                 a dimension. Lite is never sent to the API, because lite
                                 mode silently ignores include_domains.
        full_content=True:       fetch and extract the full page text for each result, then
                                 slice it to the query-relevant sections. Slower and higher
                                 cost — use only on the pages you will cite, num_results <= 4.
        include_domains:         whitelist, e.g. ["ramp.com"] or ["crunchbase.com","techcrunch.com"].
                                 Reliably enforced at standard depth.
        time_range:              hour/week/month/year. start_date: "YYYY-MM-DD".
                                 Pass either time_range or start_date, not both.
        """
        # Never send search_depth="lite" to the API. In lite mode the Search API drops
        # `include_domains` server-side (measured ~47% off-domain results vs 0% on
        # "standard"), which would silently break the source scoping this agent depends
        # on. A lite request is honoured as a local metadata-only trim instead, so a scan
        # costs the same context it always did without losing domain scoping.
        scan = search_depth == "lite" and not full_content
        kwargs = {"query": query, "search_depth": "standard"}
        kwargs["max_results"] = min(num_results, 4) if full_content else num_results
        if full_content:
            kwargs["full_content"] = True
        if include_domains:
            kwargs["include_domains"] = include_domains
        if start_date:
            kwargs["start_date"] = start_date
        elif time_range:
            kwargs["time_range"] = time_range
        try:
            resp = client.search(**kwargs)
        except Exception as exc:
            return [{"error": f"{type(exc).__name__}: {exc}"}]
        return _compact(resp.results, query, full_content, CONTENT_CHAR_CAP, scan=scan)

    return nimble_search


def _make_llm(model: str | None):
    name = model or DEFAULT_MODEL
    kwargs = {} if any(t in name for t in ("gpt-5", "o1", "o3", "o4")) else {"temperature": 0}
    return init_chat_model(name, **kwargs)


def build_agent(model: str | None = None, today: str | None = None):
    today = today or dt.date.today().isoformat()
    return create_agent(
        model=_make_llm(model),
        tools=[_make_search_tool()],
        system_prompt=build_system_prompt(today),
        response_format=DiligenceProfile,
    )


def diligence(company: str, model: str | None = None) -> DiligenceProfile:
    """Run the agent end to end and return the structured profile."""
    today = dt.date.today().isoformat()
    agent = build_agent(model, today)
    try:
        result = agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        f"Conduct preliminary investment due diligence on {company}. Research "
                        f"its business model, products, leadership, funding, major "
                        f"partnerships, competitive position, and key risks. Return a "
                        f"structured profile with citations and a confidence grade per "
                        f"dimension. Keep funding.total_raised and funding.last_round to short "
                        f"phrases (e.g. '$1.9B', 'Series F, $750M at $44B'), not paragraphs. "
                        f"Today is {today}.",
                    )
                ]
            },
            {"recursion_limit": DEFAULT_RECURSION_LIMIT},
        )
    except GraphRecursionError as exc:
        raise RuntimeError(
            f"The agent hit its {DEFAULT_RECURSION_LIMIT}-step budget before returning a profile "
            f"for {company!r}. Narrow the request, or raise AGENT_RECURSION_LIMIT "
            f"above {DEFAULT_RECURSION_LIMIT}."
        ) from exc
    return result["structured_response"]
