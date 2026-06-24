"""A small local append-only log of deliveries.

The Tower Iceberg `deliveries` table only exists inside the Tower runtime, so the
local bridge can't read it during dev or a laptop demo. This JSONL mirror lets two
features work everywhere: the public "Loading Dock" gallery and cross-idea learning
(feeding past deliveries back into naming). On Tower, Iceberg stays the system of
record; this is the always-available local reflection of it.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse the same niche-overlap tokenizer the saturated_niches signal uses, so
# "dog grooming app" matches a past "last-minute dog groomers" delivery.
from .saturated_niches import _tokens

_DEFAULT_PATH = Path(__file__).resolve().parent / ".data" / "deliveries.jsonl"
_LOCK = threading.Lock()
_MAX_LINES = 500  # keep the log bounded; the dock only shows the recent tail

# Outcomes live in a SIBLING append-only JSONL next to the deliveries log, so the
# deliveries corpus stays byte-for-byte unchanged and a missing/corrupt outcome
# log can never affect the core reads. Same lock, same atomic-write + bounded
# trimming model. Bounded a bit larger than deliveries since outcomes are tiny
# (latest-wins per id needs the tail, not the full history).
_DEFAULT_OUTCOMES_PATH = Path(__file__).resolve().parent / ".data" / "outcomes.jsonl"
_MAX_OUTCOME_LINES = 2000

# The allowed founder decisions for an outcome (or None). CAPTURE-ONLY enum.
_OUTCOME_DECISIONS = {"built", "building", "passed", "considering", "dead"}
_NOTE_CAP = 500  # outcome note hard cap (chars)

# Key under which an optional per-row idea embedding is stored on the JSONL row.
# Underscore-prefixed so it reads as bridge-internal metadata (not part of the
# DeliveryPackage contract); pydantic ignores it on model_validate.
_EMBEDDING_KEY = "_idea_embedding"


def _path() -> Path:
    return Path(os.getenv("DELIVERIES_LOG", str(_DEFAULT_PATH)))


def _outcomes_path() -> Path:
    return Path(os.getenv("OUTCOMES_LOG", str(_DEFAULT_OUTCOMES_PATH)))


def _embeddings_enabled() -> bool:
    """OPT-IN flag for the embeddings-backed "niche memory". Default OFF.

    NICHE_EMBEDDINGS=1 turns on best-effort idea embeddings at record() time and
    cosine-ranked semantic recall in for_niche(). With it unset/"0" the store is
    byte-for-byte its prior self: no embedding work, plain token-overlap recall.
    Read at call time so it can be toggled per-process. The same embeddings would
    back an Iceberg vector recall in the Tower runtime; here we operate purely over
    the local JSONL mirror (the system of record in prod).
    """
    return os.getenv("NICHE_EMBEDDINGS", "0").strip() == "1"


def _cosine(a: list[float], b: list[float]) -> float | None:
    """Pure-python cosine similarity (no numpy dependency).

    Returns None for empty, length-mismatched, or zero-magnitude vectors so the
    caller can simply skip/ fall back rather than divide by zero.
    """
    if not a or not b or len(a) != len(b):
        return None
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return None
    return dot / math.sqrt(norm_a * norm_b)


def _idea_embedding(idea: str) -> list[float] | None:
    """Best-effort embedding for one idea string. None on anything unusual."""
    idea = (idea or "").strip()
    if not idea:
        return None
    from .clients import _openrouter

    vectors = _openrouter.embed([idea])
    if vectors and vectors[0]:
        return list(vectors[0])
    return None


def record(package: dict[str, Any]) -> None:
    """Append one delivered package (snake_case model_dump) to the log.

    When NICHE_EMBEDDINGS=1 we ALSO attach a best-effort idea embedding under
    `_idea_embedding`. That whole step is wrapped: a missing key, provider error,
    or unavailable embeddings API just omits the field — the row is still written
    exactly as before. With the flag off this is a no-op and the write is
    byte-for-byte identical to the prior behavior.
    """
    path = _path()
    row = package
    if _embeddings_enabled():
        try:
            vector = _idea_embedding(str(package.get("idea", "")))
            if vector:
                row = dict(package)
                row[_EMBEDDING_KEY] = vector
        except Exception:
            row = package  # any failure → write the original row, no embedding
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        _trim(path)


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > _MAX_LINES:
        path.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")


def _read_all() -> list[dict[str, Any]]:
    path = _path()
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def count_all() -> int:
    """The TRUE number of deliveries ever logged (no domain dedupe).

    `recent()` dedupes by domain for the gallery, which undercounts real activity
    when the same idea/domain ships more than once. Use this for headline totals.
    """
    return len(_read_all())


def recent(limit: int = 24) -> list[dict[str, Any]]:
    """The most recent deliveries, newest first, deduped by domain.

    Each returned row has its LATEST captured outcome folded in as an `outcome`
    field (best-effort; absent/None when none exists). The outcome lookup is done
    once over the whole outcome log (latest-wins) so the dock/list reads stay one
    pass; a missing/corrupt outcome log simply yields rows with no outcome."""
    latest = _latest_outcomes()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for obj in reversed(_read_all()):
        domain = str(obj.get("domain", "")).lower()
        if domain in seen:
            continue
        seen.add(domain)
        out.append(_with_outcome(obj, latest))
        if len(out) >= limit:
            break
    return out


def get(tracking_id: str) -> dict[str, Any] | None:
    """A single delivery by its tracking id (newest match wins), or None.

    The LATEST captured outcome for this id (latest-wins) is folded into the
    returned dict as an `outcome` field. Best-effort: when no outcome exists the
    row is returned unchanged (no `outcome` key), so existing reads (the package,
    GET /deliveries/{id}, /jobs cold fallback) are unaffected."""
    tid = (tracking_id or "").strip().upper()
    if not tid:
        return None
    for obj in reversed(_read_all()):
        if str(obj.get("tracking_id", "")).upper() == tid:
            return _with_outcome(obj, {tid: outcome_for(tid)})
    return None


# ---- outcome capture: the labeled feature store (CAPTURE-ONLY) ----------------
# A founder's thumbs + build/pass decision, keyed by tracking_id, appended to a
# sibling outcomes JSONL (latest-wins on read). Never fed into the score here.

def _utc_iso() -> str:
    """UTC ISO-8601 timestamp (seconds precision, trailing 'Z')."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_append(path: Path, line: str, max_lines: int) -> None:
    """Append one JSONL line, then atomically rewrite a bounded tail.

    Mirrors the existing write model (lock-held append + trim) but the trim
    rewrites via a temp file + os.replace so a crash mid-trim can't leave a
    truncated log. Caller holds _LOCK."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= max_lines:
        return
    tail = "\n".join(lines[-max_lines:]) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tail)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _validate_outcome(outcome: dict[str, Any]) -> dict[str, Any] | None:
    """Validate + normalize a raw outcome dict. Returns the clean dict or None.

    Rules: decision must be a known enum value or None; note clipped to 500;
    at least one of verdict_helpful / decision / note must be present (a wholly
    empty capture is rejected -> None). Never raises."""
    try:
        helpful = outcome.get("verdict_helpful")
        if helpful is not None:
            helpful = bool(helpful)

        decision = outcome.get("decision")
        if decision is not None:
            decision = str(decision).strip().lower()
            if decision == "":
                decision = None
            elif decision not in _OUTCOME_DECISIONS:
                return None  # bad enum -> invalid

        note = outcome.get("note") or ""
        note = str(note).strip()[:_NOTE_CAP]

        if helpful is None and decision is None and note == "":
            return None  # all-empty capture is invalid

        return {
            "verdict_helpful": helpful,
            "decision": decision,
            "note": note,
        }
    except Exception:
        return None


def record_outcome(tracking_id: str, outcome: dict[str, Any]) -> dict[str, Any] | None:
    """VALIDATE + stamp + append one founder outcome event for a delivery.

    Validates (known decision enum or None; >=1 of verdict_helpful/decision/note;
    note clipped to 500), stamps captured_at (UTC ISO) + source ("web" default),
    and appends to the sibling outcomes log (append-only, atomic, bounded).

    Returns the stamped outcome dict (snake_case) on success, or None when the
    tracking id is blank or the outcome is invalid/empty. Best-effort + thread
    safe (reuses _LOCK); NEVER raises into the caller — a write error returns the
    validated outcome (so the API still confirms what it accepted) without
    persisting."""
    tid = (tracking_id or "").strip().upper()
    if not tid:
        return None
    clean = _validate_outcome(outcome or {})
    if clean is None:
        return None

    source = outcome.get("source")
    source = str(source).strip()[:60] if source else "web"
    stamped = {
        **clean,
        "captured_at": _utc_iso(),
        "source": source or "web",
    }
    row = {"tracking_id": tid, **stamped}
    try:
        with _LOCK:
            _atomic_append(_outcomes_path(), json.dumps(row, ensure_ascii=False), _MAX_OUTCOME_LINES)
    except Exception:
        pass  # never raise into the caller; return the accepted outcome anyway
    return stamped


def _read_outcomes() -> list[dict[str, Any]]:
    """All outcome rows in file order (oldest -> newest). Best-effort; [] on miss."""
    try:
        raw = _outcomes_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("tracking_id"):
            out.append(obj)
    return out


def _strip_outcome_row(row: dict[str, Any]) -> dict[str, Any]:
    """The outcome row minus its routing key, ready to fold onto a delivery."""
    return {k: v for k, v in row.items() if k != "tracking_id"}


def _latest_outcomes() -> dict[str, dict[str, Any]]:
    """Map upper-cased tracking_id -> its LATEST outcome (latest-wins).

    Append-only log => the last row for an id is the current one. Best-effort:
    any read/parse failure yields an empty map (rows then carry no outcome)."""
    latest: dict[str, dict[str, Any]] = {}
    try:
        for row in _read_outcomes():  # oldest -> newest; last write wins
            tid = str(row.get("tracking_id", "")).strip().upper()
            if tid:
                latest[tid] = _strip_outcome_row(row)
    except Exception:
        return {}
    return latest


def outcome_for(tracking_id: str) -> dict[str, Any] | None:
    """The LATEST captured outcome for one tracking id (latest-wins), or None.

    Best-effort + never raises: an unreadable outcome log returns None."""
    tid = (tracking_id or "").strip().upper()
    if not tid:
        return None
    try:
        latest: dict[str, Any] | None = None
        for row in _read_outcomes():  # oldest -> newest; keep the last match
            if str(row.get("tracking_id", "")).strip().upper() == tid:
                latest = _strip_outcome_row(row)
        return latest
    except Exception:
        return None


def _with_outcome(row: dict[str, Any], latest: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """Return `row` with its latest outcome folded in as `outcome` (best-effort).

    Only sets the key when an outcome exists, so rows with no outcome are byte-for
    -byte their prior selves and DeliveryPackage.model_validate keeps outcome=None.
    Returns the row untouched on any error."""
    try:
        tid = str(row.get("tracking_id", "")).strip().upper()
        out = latest.get(tid) if tid else None
        if out:
            merged = dict(row)
            merged["outcome"] = out
            return merged
    except Exception:
        pass
    return row


def stats() -> dict[str, Any]:
    """Dataset-level intelligence over the whole lakehouse — the lakehouse *doing*
    something, not just storing. Powers the Loading Dock's aggregate panel.
    """
    rows = recent(limit=1000)  # deduped by domain, newest-first
    verdicts = {"build": 0, "pivot": 0, "pass": 0}
    scores: list[float] = []
    secured = 0.0
    tld_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}

    for r in rows:
        v = r.get("verdict") or {}
        call = str(v.get("call", "")).lower()
        if call in verdicts:
            verdicts[call] += 1
        if isinstance(v.get("score"), (int, float)):
            scores.append(float(v["score"]))
        price = r.get("price_usd")
        if isinstance(price, (int, float)):
            secured += float(price)
        domain = str(r.get("domain", ""))
        if "." in domain:
            tld_counts[domain.rsplit(".", 1)[-1]] = tld_counts.get(domain.rsplit(".", 1)[-1], 0) + 1
        for tok in _tokens(str(r.get("idea", ""))):
            theme_counts[tok] = theme_counts.get(tok, 0) + 1

    top = lambda d, n: sorted(d.items(), key=lambda kv: -kv[1])[:n]  # noqa: E731
    return {
        # TRUE total (every logged delivery), not the domain-deduped `rows` count, so
        # repeated ideas/domains aren't undercounted. Per-bucket aggregations below
        # stay on the deduped `rows` (one row per distinct domain).
        "total": count_all(),
        "verdicts": verdicts,
        "avgScore": round(sum(scores) / len(scores)) if scores else 0,
        "securedValueUsd": round(secured, 2),
        "topTlds": [{"tld": t, "count": c} for t, c in top(tld_counts, 4)],
        # Only themes that recur — the lakehouse spotting contested spaces.
        "topThemes": [{"token": t, "count": c} for t, c in top(theme_counts, 6) if c > 1],
    }


def _for_niche_tokens(idea: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """The original token-overlap recall — the always-available fallback."""
    idea_tokens = _tokens(idea)
    if not idea_tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for obj in _read_all():
        overlap = len(idea_tokens & _tokens(str(obj.get("idea", ""))))
        if overlap:
            scored.append((overlap, obj))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [obj for _overlap, obj in scored[:limit]]


def for_niche_semantic(idea: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Embeddings-backed niche recall — ranks past deliveries by cosine similarity
    to this idea's embedding.

    Only engages when NICHE_EMBEDDINGS=1 AND we can embed this idea AND at least
    one past row carries a stored embedding. In every other case — flag off, no
    embeddings provider, no embedded rows, or ANY error — it FALLS BACK to the
    token-overlap recall, so it's always safe to call. Operates over the local
    JSONL mirror; the same vectors would back an Iceberg vector recall on Tower.
    """
    try:
        if not _embeddings_enabled():
            return _for_niche_tokens(idea, limit=limit)
        query = _idea_embedding(idea)
        if not query:
            return _for_niche_tokens(idea, limit=limit)
        scored: list[tuple[float, dict[str, Any]]] = []
        for obj in _read_all():
            vec = obj.get(_EMBEDDING_KEY)
            if isinstance(vec, list) and vec:
                sim = _cosine(query, vec)
                if sim is not None:
                    scored.append((sim, obj))
        if not scored:
            # No embedded history yet — keep behavior useful via token overlap.
            return _for_niche_tokens(idea, limit=limit)
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [obj for _sim, obj in scored[:limit]]
    except Exception:
        return _for_niche_tokens(idea, limit=limit)


def for_niche(idea: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Past deliveries whose idea overlaps this one — fuel for cross-idea learning.

    Transparently uses the embeddings-backed semantic path when NICHE_EMBEDDINGS=1
    (and falls back to token overlap on any miss/error). With the flag off this is
    exactly the original token-overlap recall — same inputs, same outputs — so all
    existing callers (orchestrator, niche_intel) are unaffected.
    """
    if _embeddings_enabled():
        return for_niche_semantic(idea, limit=limit)
    return _for_niche_tokens(idea, limit=limit)


def _com_taken_in(delivery: dict[str, Any]) -> bool | None:
    """Was the `.com` unavailable in a past delivery? Reads its TLD grid.

    Returns True (taken) / False (was open) / None (no `.com` signal recorded).
    """
    for opt in delivery.get("domain_options") or []:
        if str(opt.get("tld", "")).lower() == "com":
            avail = opt.get("available")
            if isinstance(avail, bool):
                return not avail
    return None


def _steer_note(in_theme: int, com_taken: int, com_checked: int, contested: list[str]) -> str:
    """A one-line, human steer the agent acts on and the UI shows verbatim."""
    if in_theme <= 0:
        return ""
    parts: list[str] = []
    if com_checked and com_taken:
        parts.append(
            f".com taken in {com_taken}/{com_checked} past deliveries here → "
            "lead with .delivery"
        )
    else:
        plural = "y" if in_theme == 1 else "ies"
        parts.append(f"{in_theme} past deliver{plural} in this theme to learn from")
    if contested:
        parts.append("contested themes: " + ", ".join(contested[:3]))
    return "; ".join(parts)


def niche_intel(idea: str, *, limit: int = 8) -> dict[str, Any]:
    """A compact, prompt-ready read of the lakehouse for one idea's niche.

    Composes for_niche() (past deliveries overlapping this idea) with stats()
    (whole-dataset aggregates) into a small grounding summary. This is the
    "data-to-AI" hop: the agent feeds these aggregates back into its naming +
    verdict prompts, and the UI surfaces them. Read-only; keys are snake_case so
    they map straight onto the LakehouseIntel schema model.
    """
    prior = for_niche(idea, limit=limit)
    agg = stats()

    com_checked = 0
    com_taken = 0
    theme_counts: dict[str, int] = {}
    for d in prior:
        taken = _com_taken_in(d)
        if taken is not None:
            com_checked += 1
            if taken:
                com_taken += 1
        for tok in _tokens(str(d.get("idea", ""))):
            theme_counts[tok] = theme_counts.get(tok, 0) + 1

    com_taken_pct = round(100 * com_taken / com_checked) if com_checked else None

    # Contested themes: tokens recurring across these niche deliveries; fall back
    # to the dataset's top recurring themes when the niche is too small to recur.
    contested = [t for t, c in sorted(theme_counts.items(), key=lambda kv: -kv[1]) if c > 1]
    if not contested:
        contested = [t["token"] for t in agg.get("topThemes", []) if t.get("token")]
    contested = contested[:6]

    return {
        "deliveries_in_theme": len(prior),
        "com_taken_pct": com_taken_pct,
        "contested_themes": contested,
        "total_delivered": int(agg.get("total", 0)),
        "steer_note": _steer_note(len(prior), com_taken, com_checked, contested),
    }
