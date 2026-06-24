"""Tiny env helpers shared across the agent.

Boot resilience: integer env knobs are parsed at IMPORT time. A bare int() on a
fat-fingered value (e.g. a stray "abc" Fly env knob during judging) raises and
bricks the whole bridge — uvicorn can't even load agent.server. env_int keeps
the codebase's best-effort discipline: a missing/blank/non-integer value falls
back to the default instead of crashing import.
"""
from __future__ import annotations

import os


def env_int(name: str, default: int) -> int:
    """Return os.environ[name] as an int, or `default` if unset/blank/non-integer."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError, TypeError):
        return default
