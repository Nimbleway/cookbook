#!/usr/bin/env python3
"""T8/T9 acceptance: the OpenRouter brain finds a gap + brandable names.

T8: find_gap_and_names(recon) -> non-empty gap + 5 NameCandidates (name + domain).
T9: more_names(recon, exclude) -> 5 fresh names, none overlapping `exclude`.

Uses a fixed in-memory ReconResult so the check is reproducible and isolates the
LLM (no Nimble quota burned). Requires OPENROUTER_API_KEY in .env.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.clients import _openrouter, llm
from agent.clients.llm import LLMError
from agent.schemas import Competitor, NameCandidate, ReconResult

_DOMAIN_RE = re.compile(r"^[a-z0-9-]+\.[a-z0-9]+$")


def _sample_recon() -> ReconResult:
    return ReconResult(
        idea="an app that books last-minute dog groomers",
        competitors=[
            Competitor(
                name="MoeGo",
                url="https://www.moego.pet/",
                positioning="All-in-one grooming business software: scheduling, "
                "online booking, and client management for salons.",
                pricing="$49/mo",
                source_url="https://www.moego.pet/",
            ),
            Competitor(
                name="Rover",
                url="https://www.rover.com/",
                positioning="Marketplace for dog walking and boarding; grooming is "
                "a secondary, non-urgent offering.",
                pricing=None,
                source_url="https://www.rover.com/",
            ),
            Competitor(
                name="Petco Grooming",
                url="https://www.petco.com/grooming",
                positioning="In-store grooming appointments booked days in advance "
                "at big-box retail locations.",
                pricing="$40+",
                source_url="https://www.petco.com/grooming",
            ),
        ],
        market_summary=(
            "The space is dominated by salon-management SaaS (MoeGo) and broad pet "
            "marketplaces (Rover) where grooming is scheduled days out. No incumbent "
            "owns the on-demand, same-day grooming use case."
        ),
        positioning_gap=None,
    )


def _check_candidates(names: list[NameCandidate], label: str) -> list[str]:
    problems: list[str] = []
    if len(names) < 5:
        problems.append(f"{label}: expected >= 5 names, got {len(names)}")
    for c in names:
        if not c.name.strip():
            problems.append(f"{label}: a candidate has an empty name")
        if not _DOMAIN_RE.match(c.domain or ""):
            problems.append(f"{label}: bad domain shape {c.domain!r} for {c.name!r}")
    return problems


def main() -> int:
    print("=== T8/T9 OpenRouter brain verify ===")
    print(f"  model: {_openrouter.default_model()}")
    recon = _sample_recon()

    # ---- T8 ---------------------------------------------------------------
    try:
        gap, names = llm.find_gap_and_names(recon)
    except LLMError as e:
        print(f"  T8 find_gap_and_names: FAIL — {e}")
        return 1

    problems = _check_candidates(names, "T8")
    if not gap.strip():
        problems.append("T8: positioning_gap is empty")
    if problems:
        for p in problems:
            print(f"  {p}")
        return 1

    print(f"  T8 gap: {gap.strip()[:120]}{'...' if len(gap.strip()) > 120 else ''}")
    print(f"  T8 names ({len(names)}):")
    for c in names:
        print(f"    {c.domain:<26} {c.name}")
    print("  T8: PASS")

    # ---- T9 ---------------------------------------------------------------
    try:
        fresh = llm.more_names(recon, exclude=names)
    except LLMError as e:
        print(f"  T9 more_names: FAIL — {e}")
        return 1

    problems = _check_candidates(fresh, "T9")
    excluded_names = {c.name.strip().lower() for c in names}
    excluded_domains = {c.domain.strip().lower() for c in names}
    overlap = [
        c for c in fresh
        if c.name.strip().lower() in excluded_names
        or c.domain.strip().lower() in excluded_domains
    ]
    if overlap:
        problems.append(
            "T9: overlaps excluded set -> "
            + ", ".join(f"{c.name} ({c.domain})" for c in overlap)
        )
    if problems:
        for p in problems:
            print(f"  {p}")
        return 1

    print(f"  T9 fresh names ({len(fresh)}, none in T8 set):")
    for c in fresh:
        print(f"    {c.domain:<26} {c.name}")
    print("  T9: PASS")

    print("\nT8/T9: PASS — the brain is wired. Ready for T10 (end-to-end run).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
