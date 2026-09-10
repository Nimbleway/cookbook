"""Investment screening / deal-sourcing agent (Pattern A).

A LangChain agent that turns a short investment thesis into a ranked shortlist of
companies. It broadens (discovery searches) to build a candidate set, narrows
(per-candidate research) to qualify each against the thesis criteria, deduplicates,
and returns a structured ScreeningResult.

Retrieval note: the tool calls Nimble's official Python SDK (``nimble-python``, the
same client ``langchain-nimble`` wraps) directly — as of langchain-nimble 4.0.0 the
search wrapper does not expose ``full_content`` and its domain-scoped ranking is weak.
``agent_api_v2.py`` shows Pattern B, which delegates the whole workflow to a Nimble
Web Search Agent.
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
from schema import Excluded, ScreeningResult

load_dotenv()

# Provider-agnostic: "openai:gpt-5.1", "anthropic:claude-sonnet-5", "google_genai:gemini-2.5-pro", ...
DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.1")
DEFAULT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "80"))
DEFAULT_TARGET_COUNT = int(os.getenv("SCREENING_TARGET_COUNT", "25"))
CONTENT_CHAR_CAP = int(os.getenv("NIMBLE_CONTENT_CHAR_CAP", "6000"))


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
            item["content"] = content[:1200]
        out.append(item)
    return out


def _make_search_tool():
    """Nimble Search API exposed as the agent's one retrieval tool."""
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    @tool
    def nimble_search(
        query: str,
        num_results: int = 10,
        search_depth: str = "standard",
        full_content: bool = False,
        include_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> list[dict]:
        """Search the live web via Nimble. Returns [{title, url, description, content?}].

        search_depth="standard": the depth every request is served at (default). Returns a
                                 short content snippet per result — use this for the
                                 broaden phase.
        search_depth="lite":     accepted as a "scan" hint — the request is still sent at
                                 "standard" depth and trimmed locally to
                                 title/url/description. Lite is never sent to the API,
                                 because lite mode silently ignores include_domains and
                                 would pollute the candidate set with off-domain results.
        full_content=True:       fetch and extract the full page text, sliced to the
                                 query-relevant sections. Use in the narrow phase to
                                 confirm one candidate, with num_results <= 4.
        include_domains:         whitelist, e.g. ["crunchbase.com","techcrunch.com"] or a
                                 single candidate's domain. Reliably enforced at standard
                                 depth.
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


def build_agent(model: str | None = None, today: str | None = None, target_count: int | None = None):
    today = today or dt.date.today().isoformat()
    target_count = target_count or DEFAULT_TARGET_COUNT
    return create_agent(
        model=_make_llm(model),
        tools=[_make_search_tool()],
        system_prompt=build_system_prompt(today, target_count),
        response_format=ScreeningResult,
    )


# A "junk" row is a note the model wrote into the candidate list instead of a company
# ("Acme (duplicate of Foo)", "placeholder — see excluded"). Matching these as bare
# substrings deletes real companies: "Pointer Telocation Ltd" is a NASDAQ-listed firm,
# and "Dedupe Software Inc" or "Duplicate Photos Fixer" are plausible names. So each
# marker is anchored — it must appear as a parenthetical annotation, or as a phrase that
# only occurs in an editorial note, never as a bare word anywhere in the name.
_JUNK_PATTERNS = (
    # parenthetical / bracketed annotations: "Foo (duplicate of Bar)", "Foo [placeholder]"
    re.compile(
        r"[(\[]\s*(?:see\s+excluded|duplicate|dupe|dedupe|placeholder|pointer|note"
        r"|now\s+part\s+of|product\s+of|platform\s+component|same\s+as)\b",
        re.I,
    ),
    # editorial phrases that name a parent rather than a company: "X, a division of Y"
    re.compile(
        r"\b(?:duplicate|dedupe|placeholder|rebrand)\s+of\b"
        # "same as" only counts as an annotation, not inside a name like
        # "Same as a Service" — require a preceding comma or dash.
        r"|[,\-–—]\s*same\s+as\b"
        r"|\blegacy\s+brand\b"
        r"|\bproduct\s+(?:line\s+)?within\b"
        r"|\b(?:division|subsidiary)\s+of\b",
        re.I,
    ),
    # a row that is only a note, e.g. "placeholder", "duplicate", "see excluded"
    re.compile(r"^\s*(?:placeholder|duplicate|dedupe|pointer|note|see\s+excluded)\s*$", re.I),
)


def _is_junk_row(name: str) -> bool:
    """True if `name` reads as an editorial note rather than a company name."""
    return any(p.search(name) for p in _JUNK_PATTERNS)


# " X by Y ", " X of Y (product ...)" — a row that names another company as its parent
_SUBENTITY = re.compile(r"\b(?:by|from|part of|within|component of|product of)\b", re.I)

# Trailing legal-entity suffixes to strip before comparing company names.
_LEGAL_SUFFIX = re.compile(
    r"[\s,]+(?:inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited"
    r"|plc|lp|llp|gmbh|s\.?a|ag|nv|bv|oy|ab|pte)\.?$",
    re.I,
)


def _stem(name: str) -> str:
    """Normalize a company name for dedupe: drop parentheticals, punctuation, and
    trailing legal suffixes so 'Sixfold' and 'Sixfold, Inc.' collapse to one key."""
    n = name.strip().lower()
    for cut in ("(", "/", " - ", " – ", " — ", ":"):
        n = n.split(cut)[0]
    n = re.sub(r"[.'’`]", "", n)      # drop periods / apostrophes
    n = re.sub(r"[-_&]", " ", n)      # dashes / ampersand -> space
    prev = None
    while prev != n:                  # strip repeated suffixes ("Foo Inc LLC")
        prev = n
        n = _LEGAL_SUFFIX.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def _clean(result: ScreeningResult) -> ScreeningResult:
    """Deterministic hygiene the model does not reliably do itself: drop
    note/placeholder rows and LinkedIn-only evidence, collapse duplicate companies,
    and rebuild ranked_shortlist / sources. Every dropped candidate is moved to
    ``excluded`` with a reason rather than silently deleted.
    """
    stems = [_stem(c.company_name) for c in result.candidates]
    excluded_stems = {_stem(e.company_name) for e in result.excluded}
    seen: set[str] = set()
    kept = []
    dropped: list[tuple[str, str]] = []
    for idx, c in enumerate(result.candidates):
        name = c.company_name.strip()
        if _is_junk_row(name):
            dropped.append((name, "placeholder / non-company row"))
            continue
        # a row that names another candidate as its parent ("Foo by Bar", "Bar's Foo product")
        if _SUBENTITY.search(name) and any(
            j != idx and stems[j] and stems[j] in name.lower() for j in range(len(stems))
        ):
            dropped.append((name, "sub-product or brand of another candidate — merged into that entry"))
            continue
        # A candidate the model itself listed in `excluded` contradicts its own
        # shortlist; keep the exclusion and drop the recommendation.
        if _stem(name) in excluded_stems:
            dropped.append((name, "also listed in `excluded` — contradicts its own inclusion"))
            continue
        real_evidence = [u for u in c.evidence_urls if "linkedin.com/in/" not in u]
        if not real_evidence:
            reason = (
                "no supporting evidence URLs"
                if not c.evidence_urls
                else "only evidence was a personal LinkedIn profile — not independently verifiable"
            )
            dropped.append((name, reason))
            continue
        c.evidence_urls = real_evidence
        stem = _stem(name)
        if stem in seen:
            dropped.append((name, "duplicate of another candidate after name normalization"))
            continue
        seen.add(stem)
        kept.append(c)

    result.candidates = kept
    # Rebuild the ranking from the survivors, preserving the model's order but
    # emitting each name once — a repeated name would show as duplicate positions.
    keep_names = {c.company_name for c in kept}
    ranked: list[str] = []
    for n in result.ranked_shortlist:
        if n in keep_names and n not in ranked:
            ranked.append(n)
    ranked += [c.company_name for c in kept if c.company_name not in ranked]
    result.ranked_shortlist = ranked

    # move drops into `excluded` (dedup by name), so nothing vanishes without a trace
    excl_names = {e.company_name for e in result.excluded}
    for name, reason in dropped:
        if name not in excl_names:
            result.excluded.append(Excluded(company_name=name, reason=reason))
            excl_names.add(name)

    # rebuild the top-level sources list from real per-candidate evidence URLs
    urls: list[str] = []
    for c in kept:
        for u in c.evidence_urls:
            if u not in urls:
                urls.append(u)
    # Assign unconditionally: if nothing survived, the model's original source list
    # supports no remaining recommendation and must not be presented as if it does.
    result.sources = urls
    return result


def _recursion_limit(target_count: int) -> int:
    """Scale the graph step budget with the number of companies asked for.

    Every candidate costs roughly one scan plus one full_content read, and each tool
    round trip is two LangGraph super-steps. A fixed 80 is not enough headroom for a
    25-company screen, and overrunning raises GraphRecursionError, which loses the
    entire run rather than returning a partial shortlist.
    """
    if os.getenv("AGENT_RECURSION_LIMIT"):
        return DEFAULT_RECURSION_LIMIT
    return max(DEFAULT_RECURSION_LIMIT, 4 * target_count + 40)


def screen(thesis: str, model: str | None = None, target_count: int | None = None) -> ScreeningResult:
    """Run the agent end to end and return the cleaned structured shortlist."""
    today = dt.date.today().isoformat()
    target_count = target_count or DEFAULT_TARGET_COUNT
    agent = build_agent(model, today, target_count)
    limit = _recursion_limit(target_count)
    try:
        result = agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        f"Investment thesis: {thesis}\n\n"
                        f"Find about {target_count} companies that fit this thesis. For each, "
                        f"return headquarters, product focus, target customer, funding, major "
                        f"investors, and supporting evidence. Validate each company actually "
                        f"fits before including it, deduplicate, and rank the shortlist. "
                        f"Today is {today}.",
                    )
                ]
            },
            {"recursion_limit": limit},
        )
    except GraphRecursionError as exc:
        raise RuntimeError(
            f"The agent hit its {limit}-step budget before returning a shortlist. "
            f"Retry with a smaller --count (currently {target_count}) or raise "
            f"AGENT_RECURSION_LIMIT above {limit}."
        ) from exc
    return _clean(result["structured_response"])
