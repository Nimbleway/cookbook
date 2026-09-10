"""Regulatory & filing intelligence agent (Pattern A).

A LangChain agent that controls the research workflow and uses Nimble's Search API
as its web-retrieval tool. The agent decides what to search, reads the primary
documents, and synthesises a structured RegulatoryBrief.

Retrieval note: the tool calls Nimble's official Python SDK (``nimble-python``, the
same client ``langchain-nimble`` wraps) directly, because as of langchain-nimble
4.0.0 the search wrapper does not expose ``full_content`` and its domain-scoped
ranking is weak for primary-document retrieval. ``agent_api_v2.py`` in this repo
shows Pattern B, which delegates the whole workflow to a Nimble Web Search Agent.
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
from schema import RegulatoryBrief

load_dotenv()

# Provider-agnostic: "openai:gpt-5.1", "anthropic:claude-sonnet-5", "google_genai:gemini-2.5-pro", ...
DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.1")
DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "40"))
# Cap on the extracted text kept per full-content result. Primary filings run to
# hundreds of KB; we keep the query-relevant sections rather than the first N chars.
CONTENT_CHAR_CAP = int(os.getenv("NIMBLE_CONTENT_CHAR_CAP", "8000"))


def _slice_relevant(content: str, query: str, cap: int) -> str:
    """Keep the query-relevant windows of a long document, not just the head.

    A 10-K is ~150-400 KB; the first 8 KB is the cover page. Split the text into
    windows, score each by how many distinct query terms it contains, and keep the
    best windows (plus the opening window for context) up to ``cap``.
    """
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


def _compact(results, query: str, full: bool, cap: int) -> list[dict]:
    out = []
    for r in results or []:
        item = {
            "title": getattr(r, "title", None),
            "url": getattr(r, "url", None),
            "description": getattr(r, "description", None),
        }
        content = getattr(r, "content", "") or ""
        if full and content:
            item["content"] = _slice_relevant(content, query, cap)
        elif content:
            item["content"] = content[:1500]
        # lite / no content: title + description only, no empty "content" key
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

        search_depth="lite":     metadata only (title, url, description). Fast and cheap —
                                 use to scan for the candidate documents worth reading.
        search_depth="standard": adds a short content snippet per result (default).
        full_content=True:       fetch and extract the full page text for each result, then
                                 slice it to the query-relevant sections. Slower and higher
                                 cost — use only on the few documents you will cite, with
                                 num_results <= 4.
        include_domains:         whitelist, e.g. ["sec.gov"] or ["justice.gov","ftc.gov"].
        time_range:              one of hour/day/week/month/year.
        start_date:              "YYYY-MM-DD". Pass either time_range or start_date, not both.
        """
        depth = "lite" if search_depth == "lite" else "standard"
        kwargs = {"query": query, "search_depth": depth}
        kwargs["max_results"] = min(num_results, 4) if full_content else num_results
        if full_content:
            kwargs["full_content"] = True
        if include_domains:
            kwargs["include_domains"] = include_domains
        if start_date:  # start_date and time_range are mutually exclusive in the API
            kwargs["start_date"] = start_date
        elif time_range:
            kwargs["time_range"] = time_range
        try:
            resp = client.search(**kwargs)
        except Exception as exc:  # surface the error so the agent can retry differently
            return [{"error": f"{type(exc).__name__}: {exc}"}]
        return _compact(resp.results, query, full_content, CONTENT_CHAR_CAP)

    return nimble_search


def _make_llm(model: str | None):
    name = model or DEFAULT_MODEL
    # Reasoning models (gpt-5.x, o-series) reject a non-default temperature.
    kwargs = {} if any(t in name for t in ("gpt-5", "o1", "o3", "o4")) else {"temperature": 0}
    return init_chat_model(name, **kwargs)


def build_agent(model: str | None = None, today: str | None = None):
    """Build the LangChain agent graph."""
    today = today or dt.date.today().isoformat()
    return create_agent(
        model=_make_llm(model),
        tools=[_make_search_tool()],
        system_prompt=build_system_prompt(today),
        response_format=RegulatoryBrief,
    )


def research(subject: str, model: str | None = None) -> RegulatoryBrief:
    """Run the agent end to end and return the structured brief."""
    today = dt.date.today().isoformat()
    agent = build_agent(model, today)
    result = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Research recent regulatory and filing developments related to "
                    f"{subject}. Identify material SEC disclosures, regulatory actions, "
                    f"investigations, or policy developments that could affect the "
                    f"subject. Explain what changed, why it matters, and cite the "
                    f"underlying evidence. Today is {today}.",
                )
            ]
        },
        {"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    return result["structured_response"]
