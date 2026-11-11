"""Pattern B: delegate pricing extraction to a Nimble Web Search Agent.

Where ``agent.py`` runs a LangChain agent that calls Nimble only for search, this script
hands Nimble one research objective covering all vendors and lets its Web Search Agent
plan, search, navigate, and extract. The output shape is the same VendorExtractionBatch
either way, so the downstream cost model (pricing_model.build_cost_ranking) and artifact
writer are identical between Pattern A and Pattern B: only the retrieval step changes.

    python agent_api_v2.py "Datadog,New Relic,Grafana Labs" --hosts 200 --gb-ingested 2000
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL
from dashboard import open_dashboard, write_dashboard
from pricing_model import build_cost_ranking
from run import _print_result, _write_artifacts
from schema import PriceTier, PricingComparisonResult, VendorPricing

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

_TIER_SCHEMA = {
    "type": "object",
    "properties": {
        "tier_name": {"type": "string"},
        "billing_unit": {"type": "string", "enum": ["host", "gb_ingested_monthly", "seat", "event_monthly", "other"]},
        "tier_type": {
            "type": "string",
            "enum": ["flat_all_inclusive", "base_plus_overage", "pure_per_unit", "unpublished"],
        },
        "base_fee_monthly": {"type": "number"},
        "included_quantity": {"type": "number"},
        "overage_rate_per_unit": {"type": "number"},
        "flat_rate_per_unit": {"type": "number"},
        "source_url": {"type": "string"},
    },
    "required": ["tier_name", "billing_unit", "tier_type", "source_url"],
}

PRICING_SCHEMA = {
    "type": "object",
    "properties": {
        "vendors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vendor": {"type": "string"},
                    "tiers": {"type": "array", "items": _TIER_SCHEMA},
                    "packaging_changes_last_90_days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "description": {"type": "string"},
                                "source_url": {"type": "string"},
                            },
                        },
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["vendor", "tiers", "sources"],
            },
        }
    },
    "required": ["vendors"],
}


def run_research(vendors: list[str], effort: str = "high", poll_interval: int = 15, timeout: int = 1800) -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Research how {', '.join(vendors)} currently price and package their product. "
        f"For each, return plan tiers, list prices with their billing unit, included "
        f"usage allowances, overage rates, and any packaging change announced in the "
        f"last 90 days with its date. Cite the page each value came from, and mark any "
        f"value not published publicly as unavailable (tier_type: unpublished) rather "
        f"than estimating it."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="pricing-comparison",
        use_case="research",
        skill=SKILL,
        effort=effort,
        output_schema=PRICING_SCHEMA,
    )
    agent_id = started.web_search_agent_id
    run_id = started.id
    print(f"started run {run_id} on agent {agent_id} (effort={effort})", flush=True)

    deadline = time.time() + timeout
    while True:
        status = client.agents.runs.get(run_id, agent_id=agent_id)
        state = (getattr(status, "status", "") or "").lower()
        print(f"  status: {state}", flush=True)
        if state in TERMINAL:
            break
        if time.time() > deadline:
            raise TimeoutError(f"run {run_id} did not finish within {timeout}s")
        time.sleep(poll_interval)

    if state != "completed":
        raise RuntimeError(f"run ended as {state}")

    result = client.agents.runs.result(run_id, agent_id=agent_id)
    return result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)


def to_comparison_result(raw: dict, buyer_profile: dict, as_of_date: str) -> PricingComparisonResult:
    output = raw.get("output", {})
    content = output.get("content", output) if isinstance(output, dict) else output
    vendors = [
        VendorPricing(
            vendor=v["vendor"],
            tiers=[PriceTier(**t) for t in v.get("tiers", [])],
            packaging_changes_last_90_days=v.get("packaging_changes_last_90_days", []) or [],
            sources=v.get("sources", []) or [],
        )
        for v in content.get("vendors", [])
    ]
    ranking, quote_required = build_cost_ranking(vendors, buyer_profile)
    return PricingComparisonResult(
        buyer_profile=buyer_profile,
        as_of_date=as_of_date,
        vendors=vendors,
        cost_ranking=ranking,
        quote_required=quote_required,
    )


def main() -> int:
    import datetime as dt

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vendors", help="Comma-separated vendor names")
    parser.add_argument("--hosts", type=float, default=None)
    parser.add_argument("--gb-ingested", type=float, default=None, dest="gb_ingested")
    parser.add_argument("--seats", type=float, default=None)
    parser.add_argument("--events", type=float, default=None)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--json", metavar="PATH", default=None)
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()

    buyer_profile = {
        k: v
        for k, v in {"host": args.hosts, "gb_ingested_monthly": args.gb_ingested, "seat": args.seats, "event_monthly": args.events}.items()
        if v is not None
    }
    if not buyer_profile:
        parser.error("supply at least one of --hosts, --gb-ingested, --seats, --events")

    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]
    raw = run_research(vendors, effort=args.effort, poll_interval=args.poll_interval)
    result = to_comparison_result(raw, buyer_profile, dt.date.today().isoformat())
    _print_result(result)
    _write_artifacts(result, args.out_dir)
    if not args.no_dashboard:
        dashboard_path = write_dashboard(result, args.out_dir)
        print(f"Wrote {dashboard_path}")
        open_dashboard(dashboard_path)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(raw, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
