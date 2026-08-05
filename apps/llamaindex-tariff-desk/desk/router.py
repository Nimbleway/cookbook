"""Retrieval: lane facts from the index, corpus questions from metadata.

Two engines, and LlamaIndex chooses between them:

  * **lane facts** — a metadata-filtered retriever over the vector index, scoped to
    the exact `doc_id`s the normalizer resolved. Filtering by lane key rather than
    relying on similarity alone is deliberate: "8507.60.00 from Vietnam" and
    "8507.60.00 from China" are near-identical strings, and a top-k that mixes them
    would attribute China's overlays to Vietnam. Similarity picks passages; the
    filter guarantees the right lane.
  * **corpus questions** — "what changed?", "what's stale?", "what do you cover?"
    answered from node metadata and the change log, with **no research run and no
    LLM call over the index**. Cheap, exact, and impossible to hallucinate.

The freshness guard sits in the lane path, so an expired fact cannot be answered
from silently.

Requires an embedding model only where it touches the index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llama_index.core import Settings, get_response_synthesizer
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.vector_stores import (
    FilterOperator, MetadataFilter, MetadataFilters,
)

from . import ingest
from .freshness import FreshnessPostprocessor, freshness_preamble, stale_report
from .research import Lane

HERE = Path(__file__).parent.parent
CHANGES_LOG = HERE / "data" / "changes.jsonl"

ANSWER_TMPL = (
    "You are answering a customs and trade question from a corpus of researched, "
    "cited facts.\n\n"
    "Rules you must follow:\n"
    "- Report the base schedule rate and any duty overlays separately. Never present "
    "a single blended figure unless you show the components you added.\n"
    "- State the research date for every figure, and name the source.\n"
    "- If a fact is marked STALE, say so instead of presenting it as current.\n"
    "- If the context does not contain a figure, say it is not covered. Never "
    "estimate a duty rate.\n"
    "- This is decision-support, not customs advice. Where confidence is not high, "
    "tell the reader to confirm against a binding ruling.\n\n"
    "{freshness}\n\n"
    "Context:\n{context_str}\n\n"
    "Question: {query_str}\n"
    "Answer:"
)


def lane_filters(lane: Lane) -> MetadataFilters:
    """Both Documents for this lane: the origin-free rate and the lane overlay.

    A single flat `IN` over the two doc_keys, not an OR of two AND groups —
    `SimpleVectorStore` raises "Nested MetadataFilters are not supported". The keys
    are unambiguous on their own (`8507.60.00|United States` for the rate,
    `8507.60.00|Vietnam|United States` for the overlay), so `kind` never needs to be
    part of the filter.
    """
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="doc_key",
                value=[lane.rate_key, lane.key],
                operator=FilterOperator.IN,
            )
        ]
    )


def retrieve_lane_nodes(index, lane: Lane, strict: bool = True,
                        top_k: int = 8) -> tuple[list, list]:
    """(kept, withheld) nodes for a lane after the freshness guard."""
    retriever = VectorIndexRetriever(
        index=index, similarity_top_k=top_k, filters=lane_filters(lane)
    )
    nodes = retriever.retrieve(f"duty treatment for {lane.hts_code} from {lane.origin}")
    guard = FreshnessPostprocessor(strict=False)
    annotated = guard.postprocess_nodes(list(nodes))
    if not strict:
        return annotated, []
    kept = [n for n in annotated if not n.node.metadata.get("is_stale")]
    withheld = [n for n in annotated if n.node.metadata.get("is_stale")]
    return kept, withheld


def answer_lane(index, lane: Lane, question: str, strict: bool = True) -> dict[str, Any]:
    """Answer a lane question from the corpus. Does NOT research — the caller decides.

    Returns the answer plus what was withheld and why, so the UI can offer to
    re-research rather than pretending the corpus is complete.
    """
    kept, withheld = retrieve_lane_nodes(index, lane, strict=strict)
    if not kept:
        return {
            "answered": False,
            "reason": "stale" if withheld else "not_covered",
            "withheld": withheld,
            "nodes": [],
            "answer": None,
        }

    # Synthesize from the nodes already retrieved and already guarded — never
    # re-retrieve. A second retrieval inside a query engine can select different
    # nodes by similarity and then have the strict guard drop all of them, which
    # returned a literal "Empty Response" for a lane whose base rate was perfectly
    # fresh.
    synth = get_response_synthesizer(
        llm=Settings.llm,
        text_qa_template=_qa_template(freshness_preamble(kept)),
    )
    response = synth.synthesize(question, nodes=kept)
    return {
        "answered": True,
        "reason": None,
        "withheld": withheld,
        "nodes": kept,
        "answer": str(response),
    }


def _qa_template(freshness_text: str):
    from llama_index.core import PromptTemplate

    return PromptTemplate(ANSWER_TMPL.replace("{freshness}", freshness_text or ""))


# --- corpus questions: no run, no index, no hallucination -----------------


def load_changes(limit: int = 50) -> list[dict[str, Any]]:
    if not CHANGES_LOG.exists():
        return []
    entries = []
    for line in CHANGES_LOG.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    entries.sort(key=lambda e: e.get("at") or "", reverse=True)
    return entries[:limit]


def _readable(key: str | None) -> str:
    """`8507.60.00|Vietnam|United States` -> `Vietnam → United States (HTS 8507.60.00)`.

    "Lane" is freight jargon and stays in the code, where it is the right word. It
    should never reach a reader who has no reason to know it.
    """
    parts = (key or "").split("|")
    if len(parts) == 3:
        return f"{parts[1]} → {parts[2]} (HTS {parts[0]})"
    if len(parts) == 2:
        return f"base rate into {parts[1]} (HTS {parts[0]})"
    return key or "unknown"


def answer_corpus(question: str) -> dict[str, Any]:
    """Answer a question about the corpus itself, deterministically."""
    records = ingest.load_records()
    low = question.lower()
    cov = ingest.coverage(records)
    report = stale_report(records)

    if any(w in low for w in ("changed", "change log", "delta", "moved", "what's new")):
        changes = [c for c in load_changes() if c.get("changes")]
        if not changes:
            body = ("Nothing has been refreshed yet, so there is no change history. "
                    "A refresh records what moved — and 'nothing moved' is a valid result.")
        else:
            body = "What the corpus learned at the last refreshes:\n" + "\n".join(
                f"- {c['at'][:10]} · {c['summary'][:300]}" for c in changes[:12]
            )
        return {"kind": "changes", "answer": body, "rows": changes}

    if any(w in low for w in ("stale", "fresh", "old", "expired", "up to date")):
        stale = [r for r in report if r["stale"]]
        if stale:
            body = f"{len(stale)} of {len(report)} facts are out of date:\n" + "\n".join(
                f"- {_readable(r['doc_key'])} — researched {int(r['age_days'] or 0)} days "
                f"ago, held for {r['ttl_days']}"
                for r in stale
            )
        else:
            body = (f"All {len(report)} facts are current "
                    f"(duty details are re-checked after 7 days, base rates after 90).")
        return {"kind": "freshness", "answer": body, "rows": report}

    routes = "\n".join(f"- {_readable(k)}" for k in cov["lanes"])
    body = (
        f"The corpus holds {cov['records']} researched facts: "
        f"{cov['rate_docs']} base rate(s) across {len(cov['hts_codes'])} tariff code(s), "
        f"and duty details for {cov['overlay_docs']} product-and-origin combination(s)."
        f"\n\nCovered:\n{routes}\n\n"
        "Ask about something not listed and it will be researched and added."
    )
    return {"kind": "coverage", "answer": body, "rows": report}
