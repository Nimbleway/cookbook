"""
Live progress for a run.

The interesting part of this app is the middle: every claim gets its own search and
its own judgment, and they resolve at different speeds. A summary at the end hides
that, and a line per event scrolls it out of view. So the claim list is drawn once
and rewritten in place.

Falls back to append-only lines when stdout is not a terminal, so piping to a file
or a CI log stays readable.
"""

from __future__ import annotations

import sys
import threading

# mark, label
_STATES: dict[str, tuple[str, str]] = {
    "queued": ("·", "queued"),
    "searching": ("◐", "searching"),
    "judging": ("◑", "judging"),
    "supported": ("✓", "supported"),
    "contradicted": ("✗", "contradicted"),
    "unverifiable": ("?", "unverifiable"),
    "failed": ("!", "failed"),
}

_TERMINAL = {"supported", "contradicted", "unverifiable", "failed"}


class ClaimBoard:
    """One line per claim, updated in place as each one moves through the pipeline."""

    def __init__(self, claims, width: int = 56, stream=None) -> None:
        self._stream = stream or sys.stdout
        self._tty = bool(getattr(self._stream, "isatty", lambda: False)())
        self._width = width
        self._order = [c.id for c in claims]
        self._text = {c.id: c.text for c in claims}
        self._state = {c.id: "queued" for c in claims}
        # Updates arrive from the event loop and from adjudication threads.
        self._lock = threading.Lock()
        self._drawn = 0

    def _line(self, cid: str) -> str:
        mark, label = _STATES[self._state[cid]]
        text = self._text[cid]
        if len(text) > self._width:
            text = text[: self._width - 1].rstrip() + "…"
        return f"  {mark} {cid}  {label:<13} {text}"

    def start(self) -> None:
        with self._lock:
            if not self._tty:
                return
            for cid in self._order:
                self._stream.write(self._line(cid) + "\n")
            self._drawn = len(self._order)
            self._stream.flush()

    def set(self, cid: str, state: str) -> None:
        if cid not in self._state:
            return
        with self._lock:
            self._state[cid] = state
            if self._tty:
                self._redraw()
            elif state in _TERMINAL:
                # No cursor control available: emit each claim once, when it settles.
                self._stream.write(self._line(cid) + "\n")
                self._stream.flush()

    def set_all(self, state: str) -> None:
        with self._lock:
            for cid in self._order:
                self._state[cid] = state
            if self._tty:
                self._redraw()

    def _redraw(self) -> None:
        if self._drawn:
            self._stream.write(f"\033[{self._drawn}A")  # up N lines
        for cid in self._order:
            self._stream.write("\033[2K" + self._line(cid) + "\n")  # clear, rewrite
        self._drawn = len(self._order)
        self._stream.flush()
