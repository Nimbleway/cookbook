"""Reading persisted state off disk, once, for everything that does it.

Every module here reads JSON the app itself wrote, and a file the app wrote can
still be unreadable: a process killed mid-write leaves it truncated, a sync tool
can leave it locked, permissions can change. None of that should surface as a
traceback in the middle of a question.

This module exists because the guard was written three separate times and got it
right once. `research.py` had a version that caught both JSONDecodeError and
OSError; `ingest.load_records` caught only the first; `classify` and
`recover_runs` caught neither. One implementation, imported everywhere.

Deliberately dependency-free so any module can import it without cycles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# How much of a log file to keep when tailing. Generous for a demo corpus and
# bounded for one that has been refreshing on a schedule for a year.
TAIL_BYTES = 256 * 1024


def read_json(path: Path) -> dict[str, Any] | None:
    """Parse a JSON file, or None if it is missing, truncated or unreadable.

    Returns None rather than raising: a corrupt cache entry should cost the reader
    that one fact, not the page they were looking at.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def read_json_lines(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Parse a JSONL file newest-last, reading at most the tail of it.

    The change log grows by one line per refreshed fact forever. Reading the whole
    file to show the last handful of entries is fine at demo size and wasteful at
    any real size, so only the tail is read. Unparseable lines are skipped, which
    includes the partial first line a tail read can produce.
    """
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()          # discard the partial line the seek landed in
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    lines = raw.splitlines()
    if limit is not None:
        lines = lines[-(limit * 4):]   # room for unparseable lines before slicing
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries
