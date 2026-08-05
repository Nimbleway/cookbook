"""Plain-language product -> candidate tariff codes, with citations.

Most people have no idea what an HTS code is, which makes the rest of the app
unusable to them. This is the way in: describe the product, get a short list of
candidate subheadings quoted from the official schedule, pick one.

Two deliberate choices:

  * **No text parsing.** The agent returns structured JSON via `output_schema`, and
    `claims` are keyed by JSON path, so each candidate carries its own citation. An
    earlier sketch used Nimble Search plus a regex over the result snippets; letting
    the platform do the extraction is both less code and better evidence.
  * **Candidates, never a decision.** Classification is a human call — a wrong code
    yields a confidently wrong duty for the wrong product. The agent is instructed to
    return 2-5 options and to say what a person still has to decide.

`medium` effort — about 2 minutes, against the corpus agents' 4. `low` was tried first
and produced nothing: it searched but filled no candidates.

Two findings from getting this working, both worth knowing:

  * **`input_data` steers the agent into row-enrichment mode.** Passing
    `{"product": ...}` made it echo the row back with no research at all — one
    `pre_existing` claim, zero sources. The product description belongs in the task
    text. `input_data` is for rows you want fields filled on, not for a subject you
    want researched.
  * **A reverse lookup needs different sources than a forward one.** The tariff
    schedule is organised BY CODE, so restricting to `usitc.gov` answered "rate for
    8507.60.00" well and "which code covers a drinks bottle" not at all. CBP's ruling
    database is searchable by product description and every ruling names the
    subheading it classified under — which is what a person would actually use.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from llama_index.tools.nimble import NimbleAgentRunError, NimbleAgentToolSpec

from .agents_config import HTS_SCHEMA

HERE = Path(__file__).parent.parent
CACHE_DIR = HERE / "data" / "hts_lookups"
SAMPLE_DIR = HERE / "data" / "hts_samples"

TASK = (
    "Which HTS subheadings of the Harmonized Tariff Schedule of the United States "
    "might cover this product? Return 2 to 5 candidates, most likely first, quoting "
    "each line's description verbatim from the official schedule and citing the "
    "chapter document you read it from. Do not choose one — say what a person still "
    "has to decide between them."
)

TIMEOUT_S = 600
POLL_INTERVAL_S = 5


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug[:70] or "query"


def use_live() -> bool:
    return os.environ.get("USE_LIVE", "false").strip().lower() in {"1", "true", "yes"}


def cached(product: str) -> dict[str, Any] | None:
    """A previous lookup for this product, or None. Unreadable files are skipped
    rather than raised — a corrupt cache entry must not break the lookup box."""
    from .research import read_json

    name = f"{slugify(product)}.json"
    for path in (CACHE_DIR / name, SAMPLE_DIR / name):
        if path.exists():
            record = read_json(path)
            if record is not None:
                return record
    return None


def find_candidates(product: str, force: bool = False) -> dict[str, Any]:
    """Candidate codes for a product description.

    Returns {candidates, what_would_settle_it, citations, from_cache, elapsed_s} or
    {error} — never raises into the UI, because a failed lookup should not take the
    page down.
    """
    product = (product or "").strip()
    if not product:
        return {"error": "Describe the product first."}

    if not force:
        hit = cached(product)
        if hit:
            return {**hit, "from_cache": True}

    if not use_live():
        return {"error": ("`USE_LIVE=false`, so lookups replay cached results only, and "
                          "this product isn't cached. Set `USE_LIVE=true` to look it up.")}

    agent_id = os.environ.get("NIMBLE_HTS_AGENT_ID")
    if not agent_id:
        return {"error": "NIMBLE_HTS_AGENT_ID is not set — run setup_agents.py."}

    tool = NimbleAgentToolSpec(
        agent_id=agent_id, effort="medium",
        timeout=TIMEOUT_S, poll_interval=POLL_INTERVAL_S,
    )
    started = time.monotonic()
    try:
        doc = tool.run(f"{TASK}\n\nProduct: {product}", output_schema=HTS_SCHEMA)
    except NimbleAgentRunError as err:
        return {"error": f"{type(err).__name__}: {err}"}
    except Exception as err:  # noqa: BLE001 — a lookup must not break the page
        return {"error": f"{type(err).__name__}: {err}"}

    elapsed = round(time.monotonic() - started, 1)
    meta = dict(doc.metadata or {})
    text = doc.text or ""
    try:
        content = json.loads(text.split("\nSources:")[0].strip())
    except json.JSONDecodeError:
        return {"error": "The agent's answer was not the structured shape expected.",
                "raw": text[:800]}

    # Attach each candidate's own citation, keyed by JSON path. This is what
    # output_schema buys: provenance per row, no parsing.
    claims = {c.get("path"): c for c in (meta.get("claims") or []) if c.get("path")}
    candidates = []
    for idx, candidate in enumerate(content.get("candidates") or []):
        claim = (claims.get(f"$.candidates[{idx}].hts_code")
                 or claims.get(f"$.candidates[{idx}].description")
                 or claims.get(f"$.candidates[{idx}]"))
        citation = ((claim or {}).get("citations") or [{}])[0]
        candidates.append({
            **candidate,
            "citation_url": citation.get("url") or candidate.get("source_url"),
            "citation_title": citation.get("title"),
            "citation_excerpt": (citation.get("excerpts") or [None])[0],
            "confidence": (claim or {}).get("confidence"),
        })

    record = {
        "product": product,
        "candidates": candidates,
        "what_would_settle_it": content.get("what_would_settle_it"),
        "overall_confidence": meta.get("confidence"),
        "run_id": meta.get("run_id"),
        "elapsed_s": elapsed,
        "from_cache": False,
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{slugify(product)}.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8")
    return record
