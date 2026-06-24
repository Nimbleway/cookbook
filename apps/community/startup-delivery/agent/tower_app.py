"""Tower entrypoints — wraps the agent as a serverless app + lakehouse table.

T11: run the agent, then upsert each DeliveryPackage into the Tower-managed
Iceberg `deliveries` table keyed by domain.
"""
from __future__ import annotations

import pyarrow as pa
import tower

from .orchestrator import deliver_startup
from .schemas import DeliveryPackage


_DELIVERIES_SCHEMA = pa.schema(
    [
        pa.field("idea", pa.string(), nullable=False),
        pa.field("brand", pa.string(), nullable=False),
        pa.field("domain", pa.string(), nullable=False),
        pa.field("price_usd", pa.float64()),
        pa.field("positioning_gap", pa.string(), nullable=False),
        pa.field(
            "competitors",
            pa.list_(
                pa.struct(
                    [
                        pa.field("name", pa.string(), nullable=False),
                        pa.field("url", pa.string(), nullable=False),
                        pa.field("positioning", pa.string(), nullable=False),
                        pa.field("pricing", pa.string()),
                        pa.field("source_url", pa.string(), nullable=False),
                    ]
                )
            ),
            nullable=False,
        ),
        pa.field("landing_url", pa.string()),
        # Widened so the lakehouse captures the full delivery, queryable for the
        # dock + analytics. All nullable/additive — safe Iceberg schema evolution.
        pa.field("tracking_id", pa.string()),
        pa.field("recon_at", pa.string()),
        pa.field("verdict_call", pa.string()),
        pa.field("verdict_score", pa.int64()),
        pa.field("competitor_count", pa.int64()),
        pa.field("crowded", pa.bool_()),
        pa.field("tld_open_count", pa.int64()),
    ]
)


def _to_arrow(package: DeliveryPackage) -> pa.Table:
    row = {
        "idea": package.idea,
        "brand": package.brand,
        "domain": package.domain,
        "price_usd": package.price_usd,
        "positioning_gap": package.positioning_gap,
        "competitors": [c.model_dump(mode="json") for c in package.competitors],
        "landing_url": package.landing_url,
        "tracking_id": package.tracking_id,
        "recon_at": package.recon_at,
        "verdict_call": package.verdict.call if package.verdict else None,
        "verdict_score": package.verdict.score if package.verdict else None,
        "competitor_count": (
            package.market_heat.competitor_count if package.market_heat else len(package.competitors)
        ),
        "crowded": package.market_heat.crowded if package.market_heat else None,
        "tld_open_count": sum(1 for o in package.domain_options if o.available),
    }
    return pa.Table.from_pylist([row], schema=_DELIVERIES_SCHEMA)


def upsert_delivery(package: DeliveryPackage) -> DeliveryPackage:
    table = tower.tables("deliveries").create_if_not_exists(_DELIVERIES_SCHEMA)
    table.upsert(_to_arrow(package), join_cols=["domain"])
    return package


def run(idea: str, *, build_landing: bool = False) -> DeliveryPackage:
    """Tower app entrypoint: deliver the startup, persist it, return it."""
    return upsert_delivery(deliver_startup(idea, build_landing=build_landing))
