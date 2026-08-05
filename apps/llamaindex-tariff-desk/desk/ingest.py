"""Run records -> LlamaIndex Documents -> a persisted, refreshable index.

Everything above the index build is embedding-free and unit-tested. Only
`build_index` / `load_index` touch an embedding model.

The key discipline (DESIGN.md §5): a Document's `doc_id` is stable across
re-research, so `refresh_ref_docs()` upserts in place and only re-embeds what
actually changed. Rate documents are keyed origin-free.

**On trusting the agent's output.** An earlier version of this file carried four
text heuristics that tried to detect when an answer contradicted itself — regexes
over prose, instrument-ID matching between fields, negation detection. Each one
produced false positives (one flagged a duty as unconfirmed because an unrelated
*exclusion* was unverified; another broke on the dot in "8507.60"), and together
they buried the thing this cookbook is meant to show. Nimble already returns
`confidence`, per-path `claims` with citations, and an `unverified` list. Surfacing
that verbatim is both more honest and more useful than inferring meaning from
sentences. What remains here reads *structured* fields the agent explicitly set —
no guessing.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from llama_index.core import Document

HERE = Path(__file__).parent.parent
RUNS_DIR = HERE / "data" / "runs"
SAMPLES_DIR = HERE / "data" / "samples"
STORAGE_DIR = HERE / "storage"

# Grades that mean "this came from the question, not from research".
ECHO_GRADES = {"pre_existing"}


def active_dir() -> Path:
    """The one corpus directory everything must agree on.

    The index, the sidebar and the corpus engine have to read the same records or
    they contradict each other — an earlier version had the corpus engine reporting
    "all facts are inside their TTL" while the retrieval guard was withholding a
    stale one, because one read `data/runs/` and the other `data/samples/`.
    """
    choice = os.environ.get("DESK_CORPUS", "").strip().lower()
    if choice == "runs":
        return RUNS_DIR
    if choice == "samples":
        return SAMPLES_DIR
    live = os.environ.get("USE_LIVE", "false").strip().lower() in {"1", "true", "yes"}
    if live and RUNS_DIR.exists() and any(RUNS_DIR.glob("*.json")):
        return RUNS_DIR
    if SAMPLES_DIR.exists() and any(SAMPLES_DIR.glob("*.json")):
        return SAMPLES_DIR
    return RUNS_DIR


def load_records(directory: Path | None = None) -> list[dict[str, Any]]:
    """Every saved run record, newest research first."""
    directory = directory or active_dir()
    records = []
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda r: r.get("researched_at") or "", reverse=True)
    return records


# --- reading the trust payload --------------------------------------------


def split_claims(metadata: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """(researched, echoes) — echoes are `pre_existing`, zero-citation input mirrors.

    Verified in smoke 1: `$.product`, `$.origin` and `$.hts_code` come back graded
    `pre_existing` with no citations because they were supplied in `input_data`.
    Presenting them as researched facts would be a lie of omission.
    """
    researched, echoes = [], []
    for claim in metadata.get("claims") or []:
        grade = (claim.get("confidence") or "").strip().lower()
        has_citations = bool(claim.get("citations"))
        (echoes if (grade in ECHO_GRADES and not has_citations) else researched).append(claim)
    return researched, echoes


def source_urls(metadata: dict[str, Any]) -> list[str]:
    return [s.get("url") for s in (metadata.get("sources") or []) if s.get("url")]


def primary_source_count(metadata: dict[str, Any]) -> int:
    return sum(1 for s in (metadata.get("sources") or []) if s.get("type") == "primary")


def parsed_content(record: dict[str, Any]) -> dict[str, Any] | None:
    """The structured answer. `output_type` is json, so the text leads with JSON."""
    text = record.get("text") or ""
    head = text.split("\nSources:")[0].strip()
    try:
        value = json.loads(head)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def claim_index(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """JSON path -> claim, so the UI can cite an individual cell.

    This is why `output_schema` is worth using: with it, claims are keyed by path
    (`$.additional_duties[0].rate`); without it they are keyed by prose callout and
    cannot be attached to a field.
    """
    out = {}
    for claim in metadata.get("claims") or []:
        key = claim.get("path")
        if key:
            out[key] = claim
    return out


def split_duties(content: dict[str, Any] | None,
                 as_of: str | None = None) -> tuple[list[dict], list[dict]]:
    """(in_force, not_in_force) from `additional_duties`.

    Two checks only, both reading fields the agent explicitly set:

      * `in_force is False` — it told us this one doesn't apply
      * `ends` earlier than the research date — the window has closed

    Both exist because the schema asks for them, so this is schema validation, not
    interpretation. Anything subtler than that is the reader's call, informed by the
    `unverified` list and the citations — which is what the UI shows.
    """
    if not content:
        return [], []
    from .freshness import parse_stamp

    cutoff = parse_stamp(as_of) or datetime.now(timezone.utc)
    in_force, excluded = [], []
    for duty in content.get("additional_duties") or []:
        if not isinstance(duty, dict):
            continue
        reasons = []
        if duty.get("in_force") is False:
            reasons.append("the agent marked it not in force")
        ends = parse_stamp(duty.get("ends"))
        if ends is not None and ends < cutoff:
            reasons.append(f"its window closed on {duty.get('ends')}")
        if reasons:
            excluded.append({**duty, "excluded_because": " and ".join(reasons)})
        else:
            in_force.append(duty)
    return in_force, excluded


# --- documents -------------------------------------------------------------


def node_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """What every node carries — freshness, provenance and trust travel together."""
    meta = record.get("metadata") or {}
    content = parsed_content(record) or {}
    researched, echoes = split_claims(meta)
    in_force, excluded = split_duties(content, as_of=record.get("researched_at"))
    lane = record.get("lane") or {}
    return {
        "doc_key": record.get("doc_key") or record.get("lane_key"),
        "lane_key": record.get("lane_key"),
        "kind": record.get("kind"),
        "hts_code": lane.get("hts_code"),
        # A rate Document is origin-free and applies to every origin of the code;
        # carrying the origin of whichever lane researched it would scope it wrongly.
        "origin": lane.get("origin") if record.get("kind") != "rate" else "any",
        "destination": lane.get("destination"),
        "product": lane.get("product") or "",
        "researched_at": record.get("researched_at"),
        "confidence": meta.get("confidence"),
        "reasoning": meta.get("reasoning"),
        "run_id": meta.get("run_id"),
        "agent_id": meta.get("web_search_agent_id") or meta.get("agent_id"),
        "effort": meta.get("effort"),
        "source_urls": source_urls(meta),
        "primary_sources": primary_source_count(meta),
        "researched_claims": len(researched),
        "echoed_claims": len(echoes),
        "duties_in_force": len(in_force),
        "duties_excluded": len(excluded),
        # Coverage gaps matter as much as the answer: `confidence` does not capture
        # them. A run can return `high` while leaving several facts unverified.
        "unverified": content.get("unverified") or [],
        "confirmed_absent": content.get("confirmed_absent") or [],
    }


def to_document(record: dict[str, Any]) -> Document:
    """One saved run -> one Document with a stable doc_id."""
    kind = record.get("kind") or "fact"
    doc_id = record.get("doc_id") or f"{record.get('doc_key') or record.get('lane_key')}#{kind}"
    lane = record.get("lane") or {}
    meta = node_metadata(record)

    if kind == "rate":
        header = (
            f"Base tariff schedule rate for HTS {lane.get('hts_code')} "
            f"into {lane.get('destination')}"
            "\nThis Column 1 General (MFN) rate applies to imports from ANY country of "
            "origin. Any origin named in the source run below is incidental to how the "
            "research was triggered and does not limit the rate's scope."
        )
    else:
        header = (
            f"Duty policy overlays for HTS {lane.get('hts_code')} "
            f"from {lane.get('origin')} into {lane.get('destination')}"
        )
    if lane.get("product"):
        header += f" ({lane['product']})"

    # The research date goes in the TEXT as well as the metadata, because an agent
    # only ever sees a node's text — metadata is dropped on the way in.
    body = (
        f"{header}\n"
        f"Researched: {record.get('researched_at')}\n"
        f"Overall confidence: {meta.get('confidence')}\n\n"
        f"{record.get('text') or ''}"
    )
    doc = Document(text=body, doc_id=doc_id, metadata=meta)
    # Metadata is prepended to node text for embedding and counts against the chunk
    # budget; the full payload overflows a 1024-token chunk outright. These stay on
    # the node for the UI to read, they just aren't embedded.
    bulky = ["unverified", "confirmed_absent", "reasoning", "source_urls",
             "run_id", "agent_id"]
    doc.excluded_embed_metadata_keys = list(bulky)
    doc.excluded_llm_metadata_keys = list(bulky)
    return doc


def to_documents(records: Iterable[dict[str, Any]]) -> list[Document]:
    return [to_document(r) for r in records]


# --- index build (the only embedding-dependent part) ----------------------


def _storage_exists(storage_dir: Path) -> bool:
    return (storage_dir / "docstore.json").exists()


def build_index(documents: list[Document], storage_dir: Path | None = None):
    """Create or update the index, re-embedding only what changed."""
    from llama_index.core import (
        StorageContext, VectorStoreIndex, load_index_from_storage,
    )

    storage_dir = storage_dir or STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)

    if _storage_exists(storage_dir):
        ctx = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(ctx)
        # Stable doc_ids + upsert-by-hash: unchanged Documents are not re-embedded.
        refreshed = index.refresh_ref_docs(documents)
        index.storage_context.persist(persist_dir=str(storage_dir))
        return index, refreshed

    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=str(storage_dir))
    return index, [True] * len(documents)


def load_index(storage_dir: Path | None = None):
    from llama_index.core import StorageContext, load_index_from_storage

    storage_dir = storage_dir or STORAGE_DIR
    if not _storage_exists(storage_dir):
        return None
    ctx = StorageContext.from_defaults(persist_dir=str(storage_dir))
    return load_index_from_storage(ctx)


def coverage(records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """What the corpus holds — drives the sidebar and 'what do you cover?'."""
    records = records if records is not None else load_records()
    lanes, codes = set(), set()
    for r in records:
        if r.get("kind") == "overlay" and r.get("lane_key"):
            lanes.add(r["lane_key"])
        code = (r.get("lane") or {}).get("hts_code")
        if code:
            codes.add(code)
    return {
        "records": len(records),
        "lanes": sorted(lanes),
        "hts_codes": sorted(codes),
        "rate_docs": sum(1 for r in records if r.get("kind") == "rate"),
        "overlay_docs": sum(1 for r in records if r.get("kind") == "overlay"),
    }
