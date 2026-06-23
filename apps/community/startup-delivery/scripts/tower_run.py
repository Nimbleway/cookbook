#!/usr/bin/env python3
"""Tower script entrypoint for the Startup.Delivery orchestrator app."""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import tower

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.saturated_niches import crowded_market_note, refresh_saturated_niches
from agent.schemas import DeliveryPackage
from agent.tower_app import run, upsert_delivery


DEFAULT_IDEA = "an app that books last-minute dog groomers"


def _refresh_saturated_niches() -> int:
    rows = refresh_saturated_niches()
    print(f"Refreshed saturated_niches rows: {len(rows)}")
    for row in rows:
        print(f"- {row['niche']}: {row['competitor_count']} competitors ({row['source']})")

    if tower.parameter("verify_readback", "0") == "1":
        count = tower.tables("saturated_niches").load().read().height
        print(f"Readback saturated_niches rows: {count}")
        note = crowded_market_note("an app that books last-minute dog groomers")
        print(f"Recon saturated note: {note or 'none'}")

    return 0


def _deliver() -> int:
    idea = tower.parameter("idea", DEFAULT_IDEA).strip() or DEFAULT_IDEA
    build_landing = tower.parameter("build_landing", "0") == "1"
    package = run(idea, build_landing=build_landing)
    print(package.model_dump_json(indent=2))

    if tower.parameter("verify_readback", "0") == "1":
        rows = (
            tower.tables("deliveries")
            .load()
            .to_polars()
            .filter(pl.col("domain") == package.domain)
            .collect()
        )
        print(f"Readback rows for {package.domain}: {rows.height}")

    return 0


def _persist() -> int:
    """Upsert a precomputed package (from the web bridge) into the lakehouse.

    The bridge already ran the pipeline and streamed it to the user; this just
    writes the exact same package on Tower, so the table never diverges from
    what was shown on screen and the expensive pipeline isn't run twice."""
    raw = tower.parameter("package_json", "").strip()
    if not raw:
        raise SystemExit("persist mode requires a package_json parameter")
    package = DeliveryPackage.model_validate_json(raw)
    upsert_delivery(package)
    print(f"Upserted delivery: {package.domain}")
    return 0


def main() -> int:
    mode = tower.parameter("mode", "deliver")
    if mode == "refresh_saturated_niches":
        return _refresh_saturated_niches()
    if mode == "persist":
        return _persist()
    return _deliver()


if __name__ == "__main__":
    raise SystemExit(main())
