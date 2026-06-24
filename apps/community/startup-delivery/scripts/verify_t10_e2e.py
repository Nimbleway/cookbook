#!/usr/bin/env python3
"""T10 acceptance: full local agent run returns a usable DeliveryPackage.

Runs the actual pipeline:
  Nimble recon -> OpenRouter gap/names -> name.com availability/price.

Expected on cached provider responses: under the configured local budget, with a
real available priced domain, non-empty positioning gap, and at least 3 cited competitors.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.orchestrator import deliver_startup


def main() -> int:
    idea = " ".join(sys.argv[1:]).strip() or "an app that books last-minute dog groomers"
    print("=== T10 end-to-end local verify ===")
    print(f"  idea: {idea}")

    started = time.perf_counter()
    try:
        package = deliver_startup(idea)
    except Exception as exc:
        print(f"  deliver_startup: FAIL — {exc}")
        return 1
    elapsed = time.perf_counter() - started

    problems: list[str] = []
    if not package.domain.strip():
        problems.append("domain is empty")
    if package.price_usd is None:
        problems.append(f"{package.domain}: missing price_usd")
    if not package.positioning_gap.strip():
        problems.append("positioning_gap is empty")
    cited = [c for c in package.competitors if c.source_url and c.source_url.startswith(("http://", "https://"))]
    if len(cited) < 3:
        problems.append(f"expected >= 3 cited competitors, got {len(cited)}")
    budget = float(os.environ.get("E2E_TIME_BUDGET_SECONDS", "60"))
    if elapsed > budget:
        problems.append(f"run took {elapsed:.1f}s; expected <~{budget:.0f}s for the full local pipeline")

    if problems:
        for problem in problems:
            print(f"  FAIL: {problem}")
        return 1

    print(f"  brand: {package.brand}")
    print(f"  domain: {package.domain} @ ${package.price_usd:.2f}")
    print(f"  competitors: {len(package.competitors)} ({len(cited)} cited)")
    print(f"  elapsed: {elapsed:.1f}s")
    print("\nT10: PASS — local end-to-end pipeline works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
