"""The freshness guard — the piece that makes this RAG rather than a search box.

A normal vector store answers from whatever it holds and never mentions that the
fact is four months old. Here every node carries `researched_at` and a `ttl_days`
set by its fact class (rate: 90 days, overlay: 7), and expired nodes cannot be
answered from silently.

Two enforcement points, deliberately:
  1. `FreshnessPostprocessor` annotates retrieved nodes and, in strict mode, drops
     expired ones so the synthesizer cannot quote them at all.
  2. `freshness_preamble()` puts the dates into the prompt, so an answer built from
     surviving nodes still has to state when each fact was researched.

Pure date arithmetic — no embeddings, no network. Unit-tested in tests/.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from .agents_config import TTL_DAYS

STALE_KEY = "is_stale"
AGE_KEY = "age_days"


def parse_stamp(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def ttl_for(kind: str | None) -> int:
    """TTL in days for a fact class. Unknown kinds get the strictest TTL."""
    if kind in TTL_DAYS:
        return TTL_DAYS[kind]
    return min(TTL_DAYS.values())


def age_in_days(researched_at: Any, now: datetime | None = None) -> float | None:
    stamp = parse_stamp(researched_at)
    if stamp is None:
        return None
    now = now or datetime.now(timezone.utc)
    return round((now - stamp).total_seconds() / 86400, 2)


def is_stale(researched_at: Any, kind: str | None, now: datetime | None = None) -> bool:
    """A fact with no usable timestamp is stale — absence of proof is not freshness."""
    stamp = parse_stamp(researched_at)
    if stamp is None:
        return True
    now = now or datetime.now(timezone.utc)
    return now - stamp >= timedelta(days=ttl_for(kind))


@dataclass
class FreshnessVerdict:
    kind: str | None
    researched_at: str | None
    age_days: float | None
    ttl_days: int
    stale: bool

    def describe(self) -> str:
        if self.researched_at is None:
            return f"{self.kind or 'fact'}: no research date recorded — treat as stale"
        age = "today" if (self.age_days or 0) < 1 else f"{self.age_days:g} days ago"
        state = "STALE" if self.stale else "fresh"
        return (
            f"{self.kind or 'fact'}: researched {age} "
            f"({self.researched_at[:10]}), TTL {self.ttl_days}d — {state}"
        )


def assess(metadata: dict[str, Any], now: datetime | None = None) -> FreshnessVerdict:
    kind = metadata.get("kind")
    researched_at = metadata.get("researched_at")
    return FreshnessVerdict(
        kind=kind,
        researched_at=researched_at if isinstance(researched_at, str) else None,
        age_days=age_in_days(researched_at, now=now),
        ttl_days=ttl_for(kind),
        stale=is_stale(researched_at, kind, now=now),
    )


class FreshnessPostprocessor(BaseNodePostprocessor):
    """Annotate every retrieved node with its freshness; optionally drop stale ones.

    strict=True is the app's default: an expired node is withheld from the
    synthesizer entirely, so the UI offers to re-research instead of quietly
    serving an old rate. strict=False keeps stale nodes but marks them, which is
    what the "show me anyway" path uses.
    """

    strict: bool = True
    now: datetime | None = None

    @classmethod
    def class_name(cls) -> str:
        return "FreshnessPostprocessor"

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: QueryBundle | None = None,
    ) -> list[NodeWithScore]:
        kept: list[NodeWithScore] = []
        for nws in nodes:
            verdict = assess(nws.node.metadata or {}, now=self.now)
            nws.node.metadata[STALE_KEY] = verdict.stale
            nws.node.metadata[AGE_KEY] = verdict.age_days
            if verdict.stale and self.strict:
                continue
            kept.append(nws)
        return kept


def freshness_preamble(nodes: list[NodeWithScore], now: datetime | None = None) -> str:
    """Prompt text forcing the answer to carry its own dates.

    Without this, a synthesizer happily reports a rate with no indication of when
    it was true — which is the exact failure this whole app exists to prevent.
    """
    if not nodes:
        return ""
    lines = []
    for nws in nodes:
        meta = nws.node.metadata or {}
        label = meta.get("doc_key") or meta.get("lane_key") or "fact"
        lines.append(f"- {label} — {assess(meta, now=now).describe()}")
    return (
        "Freshness of the retrieved facts:\n"
        + "\n".join(lines)
        + "\n\nState the research date alongside every figure you report, and name the "
        "source it came from. If a fact is marked STALE, say so plainly rather than "
        "presenting it as current. Never present a value graded pre_existing as a "
        "researched fact — those are echoes of the question's own input."
    )


def stale_report(records: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    """Per-record freshness, newest first — powers the sidebar and 'what's stale?'."""
    rows = []
    for record in records:
        verdict = assess(
            {"kind": record.get("kind"), "researched_at": record.get("researched_at")},
            now=now,
        )
        rows.append({
            "doc_key": record.get("doc_key") or record.get("lane_key"),
            "lane_key": record.get("lane_key"),
            "kind": record.get("kind"),
            "researched_at": verdict.researched_at,
            "age_days": verdict.age_days,
            "ttl_days": verdict.ttl_days,
            "stale": verdict.stale,
            "confidence": (record.get("metadata") or {}).get("confidence"),
        })
    rows.sort(key=lambda r: (not r["stale"], -(r["age_days"] or 0)))
    return rows
