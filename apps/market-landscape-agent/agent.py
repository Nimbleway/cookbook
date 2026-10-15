"""Market landscape agent (Pattern A).

A LangChain agent discovers candidate vendors and researches each one using Nimble's
Search API. Deduplication, enforcing the include/exclude rule, the bottom-up size
estimate, and the reconciliation against published estimates are all deterministic code
(landscape_model.py), not the LLM's job.

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
from landscape_model import build_result
from schema import LandscapeExtractionBatch, LandscapeResult

load_dotenv()

DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.1")
DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "90"))
CONTENT_CHAR_CAP = int(os.getenv("NIMBLE_CONTENT_CHAR_CAP", "8000"))
DEFAULT_TARGET_COUNT = int(os.getenv("LANDSCAPE_TARGET_COUNT", "30"))


def _slice_relevant(content: str, query: str, cap: int) -> str:
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
            item["content"] = content[:1000]
        out.append(item)
    return out


def _make_search_tool():
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

        full_content=False (default): fast scan for the broaden phase, snippets only.
        full_content=True: full page text, sliced to query-relevant sections, for the
        narrow phase on a specific vendor's own domain, num_results <= 4.
        include_domains: directories/press for broaden, one vendor's own domain for narrow.
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


def build_agent(category: str, inclusion_criteria: list[str], target_count: int, model: str | None = None, today: str | None = None):
    today = today or dt.date.today().isoformat()
    return create_agent(
        model=_make_llm(model),
        tools=[_make_search_tool()],
        system_prompt=build_system_prompt(today, category, inclusion_criteria, target_count),
        response_format=LandscapeExtractionBatch,
    )


def map_landscape(
    category: str, inclusion_criteria: list[str], model: str | None = None, target_count: int = DEFAULT_TARGET_COUNT
) -> LandscapeResult:
    today = dt.date.today().isoformat()
    agent = build_agent(category, inclusion_criteria, target_count, model, today)
    print(f"Starting agent: mapping the {category} category...", flush=True)
    result = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Map the {category} category. Find about {target_count} candidate "
                    f"vendors, rule each include or exclude against the criteria, and "
                    f"collect published size estimates for the category. Today is {today}.",
                )
            ]
        },
        {"recursion_limit": DEFAULT_RECURSION_LIMIT},
    )
    print("Agent finished mapping the category. Computing bottom-up estimate...", flush=True)
    batch: LandscapeExtractionBatch = result["structured_response"]
    return build_result(batch.category, batch.inclusion_criteria, batch.candidates, batch.published_estimates, today)
