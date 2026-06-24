#!/usr/bin/env python3
"""T13 acceptance: generate a grounded static landing-page artifact."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.clients import llm
from agent.landing import publish_landing_page
from agent.schemas import Competitor, NameCandidate, ReconResult


def _sample_recon() -> ReconResult:
    return ReconResult(
        idea="an app that books last-minute dog groomers",
        competitors=[
            Competitor(
                name="MoeGo",
                url="https://www.moego.pet/",
                positioning="All-in-one grooming business software for scheduling and client management.",
                pricing="$49/mo",
                source_url="https://www.moego.pet/",
            ),
            Competitor(
                name="Tuft",
                url="https://tuftapp.com/",
                positioning="Free booking app for groomers with deposits, pet profiles, and reminders.",
                pricing=None,
                source_url="https://tuftapp.com/",
            ),
            Competitor(
                name="Petco Grooming",
                url="https://www.petco.com/grooming",
                positioning="In-store grooming appointments booked in advance at retail locations.",
                pricing="$40+",
                source_url="https://www.petco.com/grooming",
            ),
        ],
        market_summary="Live recon shows groomer-first scheduling tools and advance-booking retail grooming.",
        positioning_gap=(
            "No listed competitor owns the consumer-first, same-day grooming use case: "
            "finding available groomers now across real-time open capacity."
        ),
    )


def main() -> int:
    print("=== T13 landing-page verify ===")
    pick = NameCandidate(name="Groom Now", domain="groomnow.com", available=True, price_usd=12.99)
    recon = _sample_recon()
    html = llm.write_landing_page(pick, recon)
    url = publish_landing_page(pick.domain, html)

    problems: list[str] = []
    if "<script" in html.lower():
        problems.append("HTML must not contain scripts")
    if "Content-Security-Policy" not in html:
        problems.append("HTML must include a CSP meta tag")
    for expected in (pick.name, pick.domain, "https://www.moego.pet/", "https://tuftapp.com/"):
        if expected not in html:
            problems.append(f"missing expected grounded content: {expected}")
    if not url:
        problems.append("publish_landing_page returned an empty URL")

    # If we returned a frontend-relative URL, confirm the matching public file exists.
    if url.startswith("/deliveries/"):
        artifact = ROOT / "web" / "public" / url.strip("/") / "index.html"
    else:
        artifact = Path(url.replace("file://", "")) if url.startswith("file://") else None
    if artifact is not None and not artifact.exists():
        problems.append(f"landing artifact not found: {artifact}")

    if problems:
        for problem in problems:
            print(f"  FAIL: {problem}")
        return 1

    print(f"  url: {url}")
    print(f"  bytes: {len(html.encode('utf-8'))}")
    print("\nT13: PASS — grounded landing page artifact generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
