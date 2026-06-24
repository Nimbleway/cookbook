"""Disk cache for paid API responses (Nimble, name.com)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar


def _default_cache_dir() -> Path:
    """Where to keep the paid-API cache.

    Priority:
      1. CACHE_DIR env (explicit override).
      2. Next to the deliveries log when it's on a persistent volume (Fly mounts
         /data, and the Dockerfile sets DELIVERIES_LOG=/data/deliveries.jsonl), so
         the Nimble / name.com cache SURVIVES machine restarts instead of being
         wiped from the ephemeral container FS — which would silently re-burn the
         small free quotas on every cold start.
      3. agent/.cache for local dev.
    """
    explicit = os.getenv("CACHE_DIR")
    if explicit:
        return Path(explicit)
    log = os.getenv("DELIVERIES_LOG")
    if log:
        return Path(log).resolve().parent / ".cache"
    return Path(__file__).resolve().parent.parent / ".cache"


CACHE_DIR = _default_cache_dir()
T = TypeVar("T")


def _path(key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{digest}.json"


# Envelope marker. Fresh writes wrap the payload as
# ``{"__cache__": 1, "fetched_at": <epoch_seconds>, "value": <data>}`` so we can
# tell HONEST freshness (when the data was actually fetched) without trusting the
# file mtime — which a volume copy/restore can rewrite. Legacy cache files (a bare
# JSON value, no envelope) are still read transparently; their age falls back to
# the file mtime so nothing pre-existing breaks.
_ENVELOPE_MARK = "__cache__"


@dataclass(frozen=True)
class CacheResult(Generic[T]):
    """A cached read with HONEST provenance for the freshness UI.

    - value:      the cached/fetched payload.
    - from_cache: True if served from a still-valid disk entry, False if fetched live.
    - fetched_at: epoch seconds when the payload was ACTUALLY fetched (the original
                  fetch time on a cache hit, ``now`` on a live fetch); None if unknown
                  (e.g. a legacy file with an unreadable mtime).
    """

    value: T
    from_cache: bool
    fetched_at: float | None


def _read_entry(path: Path) -> tuple[Any, float | None]:
    """Read a cache file -> (value, fetched_at_epoch).

    Handles BOTH the enveloped format (preferred) and a legacy bare value, whose
    fetch time falls back to the file mtime. Raises on corrupt/truncated JSON so
    the caller treats it as a miss.
    """
    raw = json.loads(path.read_text())  # may raise json.JSONDecodeError
    if isinstance(raw, dict) and raw.get(_ENVELOPE_MARK):
        fetched_at = raw.get("fetched_at")
        return raw.get("value"), (float(fetched_at) if isinstance(fetched_at, (int, float)) else None)
    # Legacy bare value: age it by the file's mtime (best-effort).
    try:
        return raw, path.stat().st_mtime
    except OSError:
        return raw, None


def _write_entry(path: Path, data: Any, fetched_at: float) -> None:
    """Atomically write the enveloped payload (temp file + os.replace)."""
    envelope = {_ENVELOPE_MARK: 1, "fetched_at": fetched_at, "value": data}
    # Write atomically so an interrupted write never leaves a half-written file.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(envelope, indent=2))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def cached_json_meta(
    key: str,
    fetch: Callable[[], T],
    *,
    force: bool = False,
    max_age_seconds: float | None = None,
) -> CacheResult[T]:
    """Like :func:`cached_json` but also reports HONEST freshness provenance.

    A cached entry is treated as a MISS (and re-fetched) when any of these hold:
      - ``force`` is True (the live-check / "Refresh" path),
      - the file is missing,
      - the file is corrupt/truncated (unreadable JSON), or
      - ``max_age_seconds`` is set AND the entry's age exceeds it.

    Default (``max_age_seconds=None``) preserves the original behavior exactly:
    any readable file is a hit regardless of age. The atomic temp-file + os.replace
    write, the /data-volume cache dir, and the corrupt-file-as-miss path are intact.
    """
    path = _path(key)
    if path.exists() and not force:
        try:
            value, fetched_at = _read_entry(path)
        except (json.JSONDecodeError, OSError):
            value = None
            fetched_at = None
            stale = True  # truncated/corrupt cache -> treat as a miss and recompute
        else:
            if max_age_seconds is None or fetched_at is None:
                # No TTL requested (unchanged behavior), or we can't date the entry
                # -> serve it. (An undatable entry is rare: only a legacy bare file
                # whose mtime is unreadable; re-fetching it on every call would be
                # the worse failure mode for a quota-sensitive API.)
                stale = False
            else:
                stale = (time.time() - fetched_at) > max_age_seconds
            if not stale:
                return CacheResult(value=value, from_cache=True, fetched_at=fetched_at)

    now = time.time()
    data = fetch()
    _write_entry(path, data, now)
    return CacheResult(value=data, from_cache=False, fetched_at=now)


def cached_json(
    key: str,
    fetch: Callable[[], T],
    *,
    force: bool = False,
    max_age_seconds: float | None = None,
) -> T:
    """Return cached JSON for key, or call fetch(), store, and return.

    ``max_age_seconds`` (optional) expires an entry older than the TTL, re-fetching
    it. Omitting it preserves the original behavior: a readable file is always a hit.
    """
    return cached_json_meta(
        key, fetch, force=force, max_age_seconds=max_age_seconds
    ).value
