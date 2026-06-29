"""Supabase persistence for comps runs.

persist() writes one comps_runs row plus one comps_metrics row per company.
recent_runs() / get_run() back the dashboard's history sidebar and replay.
"""
from __future__ import annotations

from typing import Optional

from supabase import Client, create_client

import config
from schema import Catalyst, CompanyMetrics, ComparableSet

_client: Optional[Client] = None

# Columns mirrored from comps_metrics (and CompanyMetrics fields).
_METRIC_COLS = [
    "ticker", "name", "is_target", "market_cap_b", "pe", "forward_pe", "ps",
    "ev_ebitda", "peg", "rev_growth", "gross_margin", "op_margin",
    "profit_margin", "roe", "price_target", "analyst_recom", "source_url",
]


def _sb() -> Client:
    global _client
    if _client is None:
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY missing from comps-agent/.env")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def persist(comps: ComparableSet, model: Optional[str] = None) -> str:
    """Write a comps run + its per-company metrics. Returns the new run id."""
    sb = _sb()
    run = sb.table("comps_runs").insert({
        "target_ticker": comps.target_ticker,
        "target_name": comps.target_name,
        "verdict": comps.verdict,
        "catalysts": [c.model_dump() for c in comps.catalysts],
        "model": model,
    }).execute()
    run_id = run.data[0]["id"]

    rows = []
    for c in comps.companies:
        row = {col: getattr(c, col) for col in _METRIC_COLS}
        row["run_id"] = run_id
        rows.append(row)
    if rows:
        sb.table("comps_metrics").insert(rows).execute()
    return run_id


def recent_runs(limit: int = 20) -> list:
    """Most recent runs, newest first — for the dashboard history sidebar."""
    return (
        _sb().table("comps_runs")
        .select("id,created_at,target_ticker,target_name,verdict")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def get_run(run_id: str) -> ComparableSet:
    """Reload a saved run as a ComparableSet (for replay in the dashboard)."""
    sb = _sb()
    run = sb.table("comps_runs").select("*").eq("id", run_id).single().execute().data
    metrics = sb.table("comps_metrics").select("*").eq("run_id", run_id).execute().data
    companies = [CompanyMetrics(**{k: m.get(k) for k in _METRIC_COLS}) for m in metrics]
    catalysts = [Catalyst(**c) for c in (run.get("catalysts") or [])]
    return ComparableSet(
        target_ticker=run["target_ticker"],
        target_name=run.get("target_name"),
        companies=companies,
        catalysts=catalysts,
        verdict=run.get("verdict") or "",
    )


def delete_run(run_id: str) -> None:
    """Delete a run (comps_metrics cascade via FK)."""
    _sb().table("comps_runs").delete().eq("id", run_id).execute()
