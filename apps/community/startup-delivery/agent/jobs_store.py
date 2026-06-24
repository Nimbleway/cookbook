"""Durable, file-backed in-progress job store for the delivery pipeline.

Ephemeral across machine restarts on purpose — if a job was running and the
process died, the finished package is the system of record in
``deliveries_store``.  This store powers in-progress resume/polling:
``POST /jobs`` mints a record here at launch, every SSE event folded in via
``apply_event`` updates it atomically, and ``GET /jobs/{id}`` polls it cheaply.

Design constraints:
  - stdlib-only; zero new dependencies
  - thread-safe (one module-level Lock guards all mutation + disk writes)
  - atomic disk writes (temp-file → os.replace in the same directory)
  - never raises to callers (swallow + log internally; ``get`` may return None)
  - Python 3.9-compatible (``from __future__ import annotations`` covers all
    annotation-only uses of modern union syntax; runtime paths use
    ``Optional``/tuple-style isinstance)
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from . import deliveries_store

_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}

JOB_STALE_SECONDS: int = int(os.getenv("JOB_STALE_SECONDS", "900"))

# New deliveries mint 8 random suffix chars; keep 4-char legacy IDs readable so
# already-shared demo links keep working.
TRACKING_ID_RE = re.compile(r"^DEL-[0-9]{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$")

log = logging.getLogger("agent.bridge")  # reuse the bridge logger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _jobs_dir_path() -> Path:
    """Return the jobs directory path without creating it."""
    return deliveries_store._path().parent / "jobs"


def _ensure_jobs_dir() -> Path:
    """Return the jobs directory path, creating it if needed."""
    d = _jobs_dir_path()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tracking_id(tracking_id: str) -> str:
    return (tracking_id or "").strip().upper()


def _valid_tracking_id(tracking_id: str) -> bool:
    return bool(TRACKING_ID_RE.fullmatch(_tracking_id(tracking_id)))


def _job_path(tracking_id: str) -> Path:
    return _jobs_dir_path() / f"{_tracking_id(tracking_id)}.json"


def _norm_domain(d: str) -> str:
    """Lowercase, strip whitespace, remove trailing dots."""
    return (d or "").strip().lower().rstrip(".")


def _now() -> float:
    return time.time()


def _write(record: dict) -> None:
    """Atomically write record to disk (temp-file → os.replace). Caller holds _LOCK."""
    tid = record.get("trackingId", "UNKNOWN")
    target = _ensure_jobs_dir() / f"{tid}.json"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            delete=False,
            suffix=".tmp",
        ) as fh:
            tmp_path = fh.name
            json.dump(record, fh, ensure_ascii=False)
        os.replace(tmp_path, str(target))
    except Exception as exc:
        log.warning(
            "jobs_store write failed trackingId=%s error=%s", tid, repr(exc)
        )
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _candidate_key(candidate: dict) -> str:
    """Stable identity for one brand-name candidate across TLD promotion.

    The LLM may propose ``freshpaws.com`` and name.com may promote the same brand
    to ``freshpaws.delivery``.  Keying only by domain would duplicate the row; a
    normalized brand name is the durable identity, with domain label fallback.
    """
    name = str(candidate.get("name") or "").strip().lower()
    if name:
        return "name:" + "".join(name.split())
    domain = _norm_domain(str(candidate.get("domain") or ""))
    # First label = brand identity (must match the TS `candidateKey` in +page.svelte,
    # which uses `domain.split(".")[0]`). rsplit would diverge on multi-dot TLDs.
    label = domain.split(".", 1)[0] if "." in domain else domain
    return f"label:{label}" if label else f"domain:{domain}"


def _merge_candidate_dict(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for k, v in incoming.items():
        # A later skeleton event should not erase facts learned from name.com.
        if v is None and merged.get(k) is not None:
            continue
        if k == "variants" and not v and merged.get(k):
            continue
        merged[k] = v
    return merged


def _merge_candidates(existing: list, incoming: list) -> list:
    """Merge incoming candidates into existing by normalized brand/label.

    Existing availability/price data (from ``check`` events) is NOT clobbered
    when a ``think`` event arrives with the same brand. This also prevents a
    candidate from appearing twice when `.delivery` promotion changes the domain.
    """
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for c in existing:
        key = _candidate_key(c)
        if key not in by_key:
            order.append(key)
        by_key[key] = dict(c)
    for c in incoming:
        key = _candidate_key(c)
        if key in by_key:
            by_key[key] = _merge_candidate_dict(by_key[key], c)
        else:
            order.append(key)
            by_key[key] = dict(c)
    return [by_key[k] for k in order]


def _merge_one_candidate(existing: list, candidate: dict) -> list:
    """Merge or append one candidate by normalized brand/label."""
    key = _candidate_key(candidate)
    result: list = []
    found = False
    for c in existing:
        if _candidate_key(c) == key:
            result.append(_merge_candidate_dict(c, candidate))
            found = True
        else:
            result.append(c)
    if not found:
        result.append(dict(candidate))
    return result


def _load_from_disk(tracking_id: str) -> Optional[dict]:
    """Try reading a job record from disk.  Returns None on any failure."""
    path = _job_path(tracking_id)
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(tracking_id: str, idea: str, *, build_landing: bool = False) -> None:
    """Create a fresh running record, persist, and best-effort prune old files."""
    now = _now()
    record: dict = {
        "status": "running",
        "trackingId": tracking_id,
        "idea": idea,
        "buildLanding": build_landing,
        "createdAt": now,
        "updatedAt": now,
        "phase": "start",
        "steps": [],
        "_nextStepId": 0,
        "partial": {
            "idea": idea,
            "trackingId": tracking_id,
            "marketSummary": "",
            "competitors": [],
            "reconAt": None,
            "marketHeat": None,
            "complaints": [],
            "positioningGap": "",
            "candidates": [],
            "learnedFrom": 0,
            "verdict": None,
            "securedDomain": None,
        },
        "package": None,
        "error": None,
    }
    with _LOCK:
        _CACHE[tracking_id] = record
        _write(record)
    _prune()


def apply_event(tracking_id: str, kind: str, data: dict) -> None:
    """Thread-safe fold of ONE (already camelCase / JSON-safe) event into the job.

    Never raises.  If no job exists for ``tracking_id``, silently no-ops.
    """
    try:
        with _LOCK:
            record = _CACHE.get(tracking_id)
            if record is None:
                record = _load_from_disk(tracking_id)
                if record is None:
                    return
                _CACHE[tracking_id] = record

            # Work on a shallow copy so we can atomically replace the cache entry.
            record = dict(record)
            partial = dict(record.get("partial") or {})

            if kind == "start":
                partial["idea"] = data.get("idea", partial.get("idea", ""))
                partial["trackingId"] = data.get("trackingId", partial.get("trackingId", ""))
                record["phase"] = "start"

            elif kind == "see":
                partial["marketSummary"] = data.get("marketSummary", "")
                partial["competitors"] = data.get("competitors") or []
                partial["reconAt"] = data.get("reconAt")
                partial["marketHeat"] = data.get("marketHeat")
                partial["complaints"] = data.get("complaints") or []
                record["phase"] = "see"

            elif kind == "think":
                partial["positioningGap"] = data.get("positioningGap", "")
                partial["learnedFrom"] = data.get("learnedFrom", 0)
                incoming = data.get("candidates") or []
                partial["candidates"] = _merge_candidates(
                    partial.get("candidates") or [], incoming
                )
                record["phase"] = "think"

            elif kind == "verdict":
                partial["verdict"] = data.get("verdict")
                record["phase"] = "verdict"

            elif kind == "check":
                candidate = data.get("candidate") or {}
                partial["candidates"] = _merge_one_candidate(
                    partial.get("candidates") or [], candidate
                )
                record["phase"] = "check"

            elif kind == "secured":
                candidate = data.get("candidate") or {}
                partial["candidates"] = _merge_one_candidate(
                    partial.get("candidates") or [], candidate
                )
                domain = candidate.get("domain", "")
                partial["securedDomain"] = _norm_domain(domain) if domain else None
                record["phase"] = "secured"

            elif kind == "build":
                record["phase"] = "build"

            elif kind in ("step", "tool"):
                steps: list = list(record.get("steps") or [])
                step_id: int = record.get("_nextStepId", len(steps))
                ok_raw = data.get("ok")
                steps.append({
                    "id": step_id,
                    "kind": kind,
                    "label": data.get("label"),
                    "tool": data.get("tool"),
                    "detail": data.get("detail"),
                    "ok": ok_raw is not False,
                    "at": _now(),
                })
                if len(steps) > 40:
                    steps = steps[-40:]
                record["steps"] = steps
                record["_nextStepId"] = step_id + 1

            else:
                # Unknown kind: ignore (don't persist either)
                return

            record["partial"] = partial
            record["updatedAt"] = _now()
            _CACHE[tracking_id] = record
            _write(record)

    except Exception as exc:
        log.warning(
            "jobs_store apply_event failed trackingId=%s kind=%s error=%s",
            tracking_id, kind, repr(exc),
        )


def finish(tracking_id: str, package: dict) -> None:
    """Mark the job as done and store the final camelCase package."""
    try:
        with _LOCK:
            record = _CACHE.get(tracking_id)
            if record is None:
                record = _load_from_disk(tracking_id)
            if record is None:
                return
            record = dict(record)
            record["status"] = "done"
            record["package"] = package
            record["phase"] = "done"
            record["updatedAt"] = _now()
            _CACHE[tracking_id] = record
            _write(record)
    except Exception as exc:
        log.warning(
            "jobs_store finish failed trackingId=%s error=%s", tracking_id, repr(exc)
        )


def fail(tracking_id: str, message: str) -> None:
    """Mark the job as failed with an error message."""
    try:
        with _LOCK:
            record = _CACHE.get(tracking_id)
            if record is None:
                record = _load_from_disk(tracking_id)
            if record is None:
                return
            record = dict(record)
            record["status"] = "error"
            record["error"] = message
            record["phase"] = "error"
            record["updatedAt"] = _now()
            _CACHE[tracking_id] = record
            _write(record)
    except Exception as exc:
        log.warning(
            "jobs_store fail failed trackingId=%s error=%s", tracking_id, repr(exc)
        )


def get(tracking_id: str) -> Optional[dict]:
    """Return the job envelope or None.  Normalises ``tracking_id`` to uppercase.

    Staleness guard: if ``status == "running"`` and the record has not been
    updated for longer than ``JOB_STALE_SECONDS`` (env ``JOB_STALE_SECONDS``,
    default 900), returns a shallow-copied envelope with status/phase/error
    set to indicate a timeout (and best-effort persists that transition).
    """
    tid = _tracking_id(tracking_id)
    if not _valid_tracking_id(tid):
        return None

    with _LOCK:
        record: Optional[dict] = _CACHE.get(tid)
        if record is None:
            record = _load_from_disk(tid)
            if record is not None:
                _CACHE[tid] = record

    if record is None:
        return None

    # Staleness guard (checked outside the write lock to keep lock brief)
    if record.get("status") == "running":
        updated_at = record.get("updatedAt")
        if isinstance(updated_at, (int, float)):
            if _now() - float(updated_at) > JOB_STALE_SECONDS:
                stale = dict(record)
                stale["status"] = "error"
                stale["error"] = "delivery timed out"
                stale["phase"] = "error"
                try:
                    with _LOCK:
                        _CACHE[tid] = stale
                        _write(stale)
                except Exception:
                    pass
                return stale

    return record


def _prune(max_age_seconds: int = 86400, max_files: int = 200) -> None:
    """Best-effort delete stale job files.  Never raises."""
    try:
        jobs_dir = _jobs_dir_path()
        if not jobs_dir.exists():
            return
        files = list(jobs_dir.glob("*.json"))
        now = _now()

        # Delete files older than max_age_seconds by mtime
        surviving: list = []
        for f in files:
            try:
                mtime = f.stat().st_mtime
                if now - mtime > max_age_seconds:
                    f.unlink(missing_ok=True)
                else:
                    surviving.append((mtime, f))
            except Exception:
                continue

        # If still too many, delete oldest by mtime
        if len(surviving) > max_files:
            surviving.sort(key=lambda t: t[0])  # oldest first
            to_delete = surviving[: len(surviving) - max_files]
            for _mtime, f in to_delete:
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass
