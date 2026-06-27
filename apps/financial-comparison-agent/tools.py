"""The agent's three Nimble-backed tools.

Each tool exercises a distinct Nimble surface:
  * get_financials -> Extract (finviz) for exact valuation multiples
  * find_peers     -> Search (general focus + include_answer) for peer discovery
  * get_catalysts  -> Search (news focus, SHORT keyword query) for recent catalysts

Results are cached to data/cache so a demo can run with USE_LIVE=false (no live calls).
"""
import json
import time

from langchain_core.tools import tool
from nimble_python import Nimble

import config
from parse import parse_finviz

FINVIZ_URL = "https://finviz.com/quote.ashx?t={ticker}"

_client = None


def _nimble() -> Nimble:
    global _client
    if _client is None:
        _client = Nimble(api_key=config.NIMBLE_API_KEY)
    return _client


def _attr(obj, name, default=None):
    """Read a field whether the SDK returns objects or plain dicts."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _cached(kind: str, key: str, producer) -> str:
    """Return cached JSON for (kind, key), or call producer() and cache it.

    When USE_LIVE is false we serve cache only (video-safe). When true we always
    refresh and overwrite the cache.
    """
    path = config.CACHE_DIR / f"{kind}_{key.replace('/', '_')}.json"
    if not config.USE_LIVE and path.exists():
        return path.read_text()
    result = producer()
    path.write_text(result)
    return result


# Short-lived in-memory memo so a single analysis never re-fetches the same finviz
# page twice (the agent fetches each ticker, then assemble_comps reads it again).
_FIN_TTL_SECONDS = 180
_fin_mem: dict = {}


@tool
def get_financials(ticker: str) -> str:
    """Fetch current valuation multiples and fundamentals for a US-listed stock TICKER
    (e.g. "CMG", "CAVA"). Returns market cap, P/E, forward P/E, P/S, EV/EBITDA, PEG,
    revenue growth, gross/operating/profit margins, ROE, analyst price target and
    consensus recommendation, PLUS finviz's own peer-ticker list and the most recent
    analyst rating actions. All numbers are parsed deterministically from finviz, so
    copy them verbatim. Call this once per company in the comps set."""
    tk = ticker.strip().upper()
    cached = _fin_mem.get(tk)
    if cached and (time.time() - cached[0]) < _FIN_TTL_SECONDS:
        return cached[1]

    def producer() -> str:
        url = FINVIZ_URL.format(ticker=tk)
        res = _nimble().extract(url=url, render=True, formats=["markdown"], country="US")
        data = _attr(res, "data", {})
        markdown = _attr(data, "markdown") or ""
        parsed = parse_finviz(markdown)
        parsed["ticker"] = tk
        parsed["source_url"] = url
        return json.dumps(parsed)

    result = _cached("financials", tk, producer)
    _fin_mem[tk] = (time.time(), result)
    return result


@tool
def find_peers(company: str) -> str:
    """Discover publicly traded peer / comparable companies for a company name or ticker,
    for a valuation comps analysis. Returns an AI-synthesized answer naming likely peer
    tickers plus supporting source links. Treat the result as a suggestion: curate the
    final peer set yourself (similar business model, size class, and sector)."""

    def producer() -> str:
        # Keep the query short and literal. Phrases like "Who are…" or "comps analysis"
        # derail the search (matching WHO / generic methodology articles).
        res = _nimble().search(
            query=f"{company} top publicly traded competitors and peers",
            focus="general",
            include_answer=True,
            max_results=6,
            country="US",
        )
        answer = _attr(res, "answer")
        if answer and "unavailable" in answer.lower():
            answer = None  # include_answer sometimes whiffs — fall back to result snippets
        results = [
            {"title": _attr(r, "title"), "url": _attr(r, "url"),
             "description": _attr(r, "description")}
            for r in (_attr(res, "results", []) or [])
        ]
        return json.dumps({"answer": answer, "results": results})

    return _cached("peers", company.strip().lower(), producer)


@tool
def get_catalysts(ticker: str, company: str = "") -> str:
    """Fetch recent, dated news catalysts for a stock: earnings results, guidance changes,
    analyst rating moves. Uses Nimble's news focus, which expects a SHORT keyword query
    (a ticker plus a few keywords) — never a long question. Returns recent headlines with
    publish dates and an AI-synthesized catalyst summary. Call once per company you want
    catalysts for (at minimum the target)."""
    tk = ticker.strip().upper()

    def producer() -> str:
        query = f"{tk} {company} earnings guidance analyst rating".strip()
        res = _nimble().search(
            query=query,
            focus="news",
            include_answer=True,
            max_results=8,
            time_range="month",
            country="US",
        )
        items = []
        for r in (_attr(res, "results", []) or []):
            extra = _attr(r, "extra_fields", {}) or {}
            items.append({
                "title": _attr(r, "title"),
                "url": _attr(r, "url"),
                "date": extra.get("publish_date") or extra.get("publish_date_raw"),
            })
        return json.dumps({"summary": _attr(res, "answer"), "items": items})

    return _cached("catalysts", tk, producer)


TOOLS = [get_financials, find_peers, get_catalysts]
