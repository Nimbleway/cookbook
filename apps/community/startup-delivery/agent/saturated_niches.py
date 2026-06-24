"""Scheduled Tower refresh for saturated market signals (T12).

The scheduled job writes a small, fresh Iceberg table that the recon step can read
as an extra "crowded space" signal. Nimble calls are SERP-only and cached by the
existing client cache, so reruns do not burn pages.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

DEFAULT_NICHES: tuple[str, ...] = (
    "AI website builders",
    "AI meeting note takers",
    "AI coding agents",
    "pet grooming booking software",
)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "app",
    "apps",
    "for",
    "of",
    "software",
    "that",
    "the",
    "to",
}


def _schema():
    import pyarrow as pa

    return pa.schema(
        [
            pa.field("niche", pa.string(), nullable=False),
            pa.field("query", pa.string(), nullable=False),
            pa.field("competitor_count", pa.int64(), nullable=False),
            pa.field(
                "top_competitors",
                pa.list_(
                    pa.struct(
                        [
                            pa.field("name", pa.string(), nullable=False),
                            pa.field("url", pa.string(), nullable=False),
                        ]
                    )
                ),
                nullable=False,
            ),
            pa.field("crowded", pa.bool_(), nullable=False),
            pa.field("source", pa.string(), nullable=False),
            pa.field("refreshed_at", pa.string(), nullable=False),
            pa.field("notes", pa.string(), nullable=False),
        ]
    )


def _stem(token: str) -> str:
    for suffix in ("ing", "ers", "er", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> set[str]:
    raw = "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
    return {_stem(part) for part in raw if part not in _STOPWORDS}


def _row_for_niche(niche: str, refreshed_at: str) -> dict[str, Any]:
    query = f"{niche} startups companies competitors"
    try:
        from .clients import nimble

        serp = nimble._serp(query)
        competitors = nimble._competitors_from_serp(serp)
        top_competitors = [{"name": c.name, "url": c.url} for c in competitors[:5]]
        count = len(competitors)
        return {
            "niche": niche,
            "query": query,
            "competitor_count": count,
            "top_competitors": top_competitors,
            "crowded": count >= 5,
            "source": "nimble-serp",
            "refreshed_at": refreshed_at,
            "notes": f"Nimble SERP surfaced {count} organic competitors.",
        }
    except Exception as exc:
        return {
            "niche": niche,
            "query": query,
            "competitor_count": 0,
            "top_competitors": [],
            "crowded": False,
            "source": "fallback",
            "refreshed_at": refreshed_at,
            "notes": f"Refresh fallback: {type(exc).__name__}",
        }


def refresh_saturated_niches(niches: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Refresh the Tower Iceberg `saturated_niches` table."""
    import pyarrow as pa
    import tower

    refreshed_at = datetime.now(UTC).isoformat()
    rows = [_row_for_niche(niche, refreshed_at) for niche in (niches or DEFAULT_NICHES)]
    table = tower.tables("saturated_niches").create_if_not_exists(_schema())
    table.upsert(pa.Table.from_pylist(rows, schema=_schema()), join_cols=["niche"])
    return rows


def _best_niche_match(idea: str) -> dict[str, Any] | None:
    """The saturated_niches row whose niche best overlaps the idea, or None."""
    try:
        import tower

        rows = tower.tables("saturated_niches").load().read().to_dicts()
    except Exception:
        return None

    idea_tokens = _tokens(idea)
    best: dict[str, Any] | None = None
    best_overlap = 0
    for row in rows:
        overlap = len(idea_tokens & _tokens(str(row.get("niche", ""))))
        if overlap > best_overlap:
            best = row
            best_overlap = overlap

    return best if best_overlap else None


def crowded_market_signal(idea: str) -> dict[str, Any] | None:
    """Structured crowded-space signal for the matched niche, or None.

    Shape: {niche, competitor_count, crowded, refreshed_at}. Powers the UI's
    "Market Heat" card; mirrors the text in crowded_market_note().
    """
    best = _best_niche_match(idea)
    if not best:
        return None
    return {
        "niche": str(best.get("niche", "")),
        "competitor_count": int(best.get("competitor_count", 0) or 0),
        "crowded": bool(best.get("crowded", False)),
        "refreshed_at": str(best.get("refreshed_at", "")),
    }


def crowded_market_note(idea: str) -> str:
    """Return a short crowded-space note from Tower, or "" if unavailable."""
    best = _best_niche_match(idea)
    if not best:
        return ""

    status = "crowded" if best.get("crowded") else "not yet crowded"
    return (
        "Tower saturated_niches signal: "
        f"'{best['niche']}' is {status} "
        f"({best['competitor_count']} live SERP competitors, refreshed {best['refreshed_at']})."
    )
