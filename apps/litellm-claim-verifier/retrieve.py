"""
Retrieval: one Nimble search per claim, through LiteLLM.

This is the only module that talks to a search API, and it is deliberately the
only one that knows Nimble exists. `search_provider` is a string, so pointing the
whole app at a different provider is a one-line change here — nothing downstream
sees a provider-specific shape.

Two things measured against the live API drive the design:

1. `snippet` is the FULL page markdown (10k chars is normal, 262k has been seen),
   because LiteLLM maps `snippet = content or description`. Passing it straight to
   a model would cost roughly 50x the $0.005 search call, so every snippet is
   truncated to a claim-relevant window before it leaves this module.

2. Every search uses Nimble's default (general) focus, including time-sensitive
   claims. `focus: "news"` looked ideal for those — it returns dated results whose
   descriptions often state the fact outright — but measured against the live API
   **every news result comes back with `url: ""`**. A verdict without a citable
   source is worthless here, so news focus cannot be used by this app at all.
   Verified against the raw Nimble endpoint, so it is an API behaviour rather than
   anything LiteLLM does: `title`, `description` and `additional_data` are
   populated, `url` and `content` are empty strings.

   `focus` is still a passthrough param — LiteLLM forwards it untouched, which is
   how this was diagnosed in the first place. Anything that does not need
   per-result citations can use it freely.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import litellm

import gateway
from schemas import Claim, Evidence

SEARCH_PROVIDER = "nimble"

# Truncation budget. 1500 chars is ~375 tokens; four results is ~1.5k tokens of
# evidence per claim, which keeps token spend in the same order as the search spend.
WINDOW_CHARS = 1500
MAX_RESULTS = 4
CONCURRENCY = 5

_STOPWORDS = frozenset(
    """a an the and or but of in on at to for from by with as is are was were be been
    being that this these those it its than then so such not no nor only own same too
    very can will just should now about into over after before during above below up
    down out off again further once here there all any both each few more most other
    some what which who whom whose when where why how""".split()
)


def _significant(token: str) -> bool:
    """
    Is this token worth keeping in a query or a keyword set?

    Any token containing a digit is significant regardless of length — dropping "5"
    from "$5 per million input tokens" turns a precise claim into a vague one, and
    the figures are usually the whole point of the claim. An early version filtered
    tokens by length alone and silently discarded them.
    """
    bare = token.lower().strip(".,;:'’\"")
    if not bare:
        return False
    if any(ch.isdigit() for ch in bare):
        return True
    return len(bare) > 2 and bare not in _STOPWORDS


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9$][A-Za-z0-9'’\-\.%$]*", text)


def _keywords(text: str) -> list[str]:
    """Significant words from a claim, de-duplicated, in document order."""
    out: dict[str, None] = {}
    for tok in _tokens(text):
        if _significant(tok):
            out.setdefault(tok.strip(".,"), None)
    return list(out)


def build_query(claim: Claim) -> str:
    """
    Build the search query for a claim.

    The extractor already restates each claim as a self-contained proposition with
    pronouns resolved, which makes it a good query as it stands. General focus
    handles a full natural-language query well and benefits from the extra context.
    """
    return claim.text.rstrip(".")


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)


def _clean_markdown(text: str) -> str:
    """
    Strip the page furniture out of Nimble's markdown before windowing.

    Nimble returns genuine full-page markdown, which means navigation menus, image
    references and wiki infobox tables come along with the prose. Those score well
    on keyword matching — claim keywords appear in link text — so without this the
    window selector reliably picks a nav menu over the paragraph that answers the
    question. Measured on a 262k-char Wikipedia result.
    """
    text = _MD_IMAGE.sub("", text)

    keep: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        # Table rows and horizontal rules.
        if stripped.count("|") >= 2 or set(stripped) <= set("-|=_* "):
            continue

        # Link density is measured BEFORE links are flattened. Flattening first would
        # turn a nav menu into innocent-looking prose — which is exactly how a
        # Wikipedia sidebar ("Wikidata / Official website / …") beat the real passage
        # on an early version of this function.
        link_targets = stripped.count("](")
        flattened = _MD_HEADING.sub("", _MD_LINK.sub(r"\1", stripped))
        if link_targets and len(flattened) / max(link_targets, 1) < 60:
            continue

        if not flattened:
            continue
        letters = sum(ch.isalpha() or ch.isspace() for ch in flattened)
        if letters / len(flattened) < 0.75:
            continue

        # Sentence-likeness: nav items and captions are short and wordless. Real prose
        # runs long enough to carry a claim.
        if len(flattened) < 40 or len(flattened.split()) < 7:
            continue

        keep.append(flattened)

    return re.sub(r"\s+\n", "\n", "\n".join(keep))


def _minimal_clean(text: str) -> str:
    """Flatten markdown without discarding anything — the safety net for short snippets."""
    text = _MD_IMAGE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_HEADING.sub("", text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{2,}", "\n", text)).strip()


def _prose_ratio(chunk: str) -> float:
    """How sentence-like a chunk is — used to break ties between equal keyword scores."""
    if not chunk:
        return 0.0
    return sum(ch.isalpha() or ch.isspace() for ch in chunk) / len(chunk)


def _window(snippet: str, claim: Claim, size: int = WINDOW_CHARS) -> str:
    """
    Cut a full page down to the passage most likely to settle the claim.

    Deterministic on purpose: scoring windows by distinct-keyword hits is cheap and
    reproducible, and it keeps a model call out of the retrieval path entirely.
    """
    cleaned = _clean_markdown(snippet)

    # The aggressive filters are tuned for full pages. Nimble also returns short
    # snippets (a description, a title line), and on those the sentence-likeness rule
    # can delete everything — which would hand the adjudicator an empty source and
    # produce a false `unverifiable`. Fall back to a light clean whenever the strict
    # pass leaves less than it was given.
    if len(cleaned) < 80 < len(snippet) or not cleaned.strip():
        cleaned = _minimal_clean(snippet)

    if len(cleaned) <= size:
        return cleaned.strip()

    kws = [k.lower() for k in _keywords(claim.text)][:12]
    if not kws:
        return cleaned[:size].strip() + " …"

    low = cleaned.lower()

    # Weight each keyword by how rare it is on this page. A claim about "Claude Opus 5
    # priced at $5 per million" shares "claude" and "opus" with every paragraph on
    # Anthropic's site, so those carry almost no signal — while "$5" and "million"
    # point straight at the pricing table. Unweighted counting picks the wrong window.
    weights = {k: 1.0 / (1 + low.count(k)) for k in kws}

    step = max(size // 8, 1)
    best_start, best_key = 0, (-1.0, 0.0)
    for start in range(0, max(len(cleaned) - size, 0) + 1, step):
        chunk = low[start : start + size]
        score = sum(w for k, w in weights.items() if k in chunk)
        # Rarity-weighted coverage first, prose-likeness as the tie-break.
        key = (score, _prose_ratio(chunk))
        if key > best_key:
            best_start, best_key = start, key

    excerpt = cleaned[best_start : best_start + size]
    # Trim to whitespace boundaries so a word is never cut in half.
    if best_start > 0:
        excerpt = excerpt.partition(" ")[2]
    if best_start + size < len(cleaned):
        excerpt = excerpt.rpartition(" ")[0]

    prefix = "… " if best_start > 0 else ""
    suffix = " …" if best_start + size < len(cleaned) else ""
    return f"{prefix}{excerpt.strip()}{suffix}"


def _cost(response: object) -> float:
    hidden = getattr(response, "_hidden_params", None) or {}
    return float(hidden.get("response_cost") or 0.0)


def _as_dict(response: object) -> dict:
    if isinstance(response, dict):
        return response
    dump = getattr(response, "model_dump", None)
    return dump() if callable(dump) else dict(response)  # type: ignore[arg-type]


async def retrieve_for_claim(claim: Claim, raw_dir: Path | None = None) -> tuple[list[Evidence], str, str, float]:
    """
    Search Nimble for one claim.

    Returns (evidence, focus_used, query_used, search_cost). Raw responses land on
    disk before parsing so a schema surprise is debuggable after the fact.
    """
    focus = "general"
    query = build_query(claim)

    if gateway.ENABLED:
        # Through the proxy: same query, same params, one credential. The proxy applies
        # the Nimble config registered under its search_tool name and returns the same
        # normalised shape, so nothing below this branch changes.
        async with httpx.AsyncClient(timeout=60.0) as client:
            http = await client.post(
                gateway.search_url(),
                headers={"Authorization": f"Bearer {gateway.KEY}"},
                json={
                    "query": query,
                    "max_results": MAX_RESULTS,
                    "search_domain_filter": ["-reddit.com", "-quora.com"],
                },
            )
            http.raise_for_status()
            payload = http.json()
            # The proxy does not hand back litellm's _hidden_params, so cost comes from
            # the header it sets instead. Without this the terminal would report $0 for
            # search while the dashboard reported the real figure.
            cost = float(http.headers.get("x-litellm-response-cost") or 0.0)
    else:
        response = await litellm.asearch(
            query=query,
            search_provider=SEARCH_PROVIDER,
            max_results=MAX_RESULTS,
            # Unified param: a `-` prefix means exclude. Forums are noise for fact-checking.
            search_domain_filter=["-reddit.com", "-quora.com"],
        )
        payload = _as_dict(response)
        cost = _cost(response)

    # Raw first, parse second. A schema surprise raises during construction below, and
    # the payload is exactly what is needed to diagnose it.
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{claim.id}.json").write_text(
            json.dumps({"query": query, "focus": focus, "response": payload}, indent=2, default=str)
        )

    # A result with no URL is dropped: a verdict has to name the source that decided
    # it, and an uncitable passage cannot do that.
    evidence = [
        Evidence(
            url=item.get("url") or "",
            title=item.get("title") or "(untitled)",
            text=_window(item.get("snippet") or "", claim),
            date=item.get("date"),
            date_raw=(item.get("additional_data") or {}).get("publish_date_raw")
            if isinstance(item.get("additional_data"), dict)
            else None,
            full_length=len(item.get("snippet") or ""),
        )
        for item in (payload.get("results") or [])
        if item.get("url")
    ]

    return evidence, focus, query, cost


async def retrieve_all(
    claims: list[Claim],
    raw_dir: Path | None = None,
    on_start=None,
    on_done=None,
) -> dict[str, tuple]:
    """
    Retrieve for every claim concurrently, capped. Claims are independent.

    `on_start` fires when a claim actually acquires a slot rather than when it is
    queued, so a progress display shows what is in flight instead of what is waiting.
    """
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def one(claim: Claim):
        async with semaphore:
            if on_start:
                on_start(claim.id)
            try:
                result = await retrieve_for_claim(claim, raw_dir)
                if on_done:
                    on_done(claim.id, True)
                return claim.id, result
            except Exception as exc:  # a single failed search must not sink the run
                if on_done:
                    on_done(claim.id, False)
                print(f"  ! search failed for {claim.id}: {type(exc).__name__}: {exc}")
                return claim.id, ([], "general", build_query(claim), 0.0)

    return dict(await asyncio.gather(*(one(c) for c in claims)))
