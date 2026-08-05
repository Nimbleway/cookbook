"""What changed between two research runs of the same fact.

The change log is the app's best evidence that a refreshed corpus is worth having,
so the diff is computed from the structured content rather than by eyeballing prose.
Embedding-free and pure — unit-tested.
"""

from __future__ import annotations

from typing import Any

# Fields compared directly, per fact class.
SCALAR_FIELDS = {
    "rate": ["general_rate", "htsus_revision", "verified_against_official_schedule"],
    "overlay": ["last_changed", "origin_rules_notes"],
}

# Lists of objects compared as sets of identity tuples.
LIST_FIELDS = {
    "overlay": {
        "additional_duties": ("authority", "rate", "effective_date"),
        "exclusions_in_force": ("description", "expires"),
    },
}


def _identity(item: dict[str, Any], fields: tuple[str, ...]) -> tuple:
    return tuple(str(item.get(f) or "").strip() for f in fields)


def _label(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    parts = [str(item.get(f)) for f in fields if item.get(f)]
    return " · ".join(parts) if parts else "(empty)"


def diff_content(kind: str, before: dict[str, Any] | None,
                 after: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ordered list of changes. Empty list means nothing material moved."""
    if after is None:
        return []
    if before is None:
        return [{"type": "added", "field": "*", "before": None,
                 "after": "first research of this fact"}]

    changes: list[dict[str, Any]] = []

    for field in SCALAR_FIELDS.get(kind, []):
        old, new = before.get(field), after.get(field)
        if str(old or "").strip() != str(new or "").strip():
            changes.append({"type": "changed", "field": field,
                            "before": old, "after": new})

    for field, id_fields in LIST_FIELDS.get(kind, {}).items():
        old_items = before.get(field) or []
        new_items = after.get(field) or []
        old_map = {_identity(i, id_fields): i for i in old_items if isinstance(i, dict)}
        new_map = {_identity(i, id_fields): i for i in new_items if isinstance(i, dict)}
        for key in new_map.keys() - old_map.keys():
            changes.append({"type": "added", "field": field, "before": None,
                            "after": _label(new_map[key], id_fields),
                            "source_url": new_map[key].get("source_url")})
        for key in old_map.keys() - new_map.keys():
            changes.append({"type": "removed", "field": field,
                            "before": _label(old_map[key], id_fields), "after": None})

    # Coverage movement matters even when no value changed: a fact that slipped
    # into `unverified` is a real regression the reader should see.
    for field in ("unverified", "confirmed_absent"):
        old_n = len(before.get(field) or [])
        new_n = len(after.get(field) or [])
        if old_n != new_n:
            changes.append({"type": "coverage", "field": field,
                            "before": old_n, "after": new_n})

    return changes


def summarize(kind: str, doc_key: str, changes: list[dict[str, Any]]) -> str:
    """One human line for the change log."""
    if not changes:
        return f"{doc_key} [{kind}] unchanged"
    parts = []
    for change in changes:
        if change["type"] == "changed":
            parts.append(f"{change['field']}: {change['before']} → {change['after']}")
        elif change["type"] == "added":
            parts.append(f"+{change['field']}: {change['after']}")
        elif change["type"] == "removed":
            parts.append(f"−{change['field']}: {change['before']}")
        elif change["type"] == "coverage":
            parts.append(f"{change['field']} {change['before']}→{change['after']}")
    return f"{doc_key} [{kind}] " + "; ".join(parts)
