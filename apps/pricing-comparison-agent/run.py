"""CLI entrypoint: compare vendor pricing for a buyer profile.

    python run.py "Datadog,New Relic,Grafana Labs" --hosts 200 --gb-ingested 2000

Writes three artifacts to --out-dir (default ./output): comparison_table.md,
cost_ranking.md, quote_required.md, plus a timestamped JSON snapshot. Pass
--diff-against a previous snapshot to see what changed since that run.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from agent import compare
from dashboard import open_dashboard, write_dashboard
from schema import PricingComparisonResult


def _write_artifacts(result: PricingComparisonResult, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "comparison_table.md"), "w") as f:
        f.write(f"# Pricing comparison ({result.as_of_date})\n\n")
        f.write(f"Buyer profile: {result.buyer_profile}\n\n")
        for v in result.vendors:
            f.write(f"## {v.vendor}\n\n")
            f.write("| Tier | Type | Billing unit | Base fee/mo | Included | Overage rate | Source |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for t in v.tiers:
                f.write(
                    f"| {t.tier_name} | {t.tier_type} | {t.billing_unit} | "
                    f"{t.base_fee_monthly if t.base_fee_monthly is not None else '-'} | "
                    f"{t.included_quantity if t.included_quantity is not None else '-'} | "
                    f"{t.overage_rate_per_unit if t.overage_rate_per_unit is not None else '-'} | "
                    f"{t.source_url} |\n"
                )
            if v.packaging_changes_last_90_days:
                f.write("\nPackaging changes (last 90 days):\n")
                for c in v.packaging_changes_last_90_days:
                    f.write(f"- {c.date}: {c.description} ({c.source_url})\n")
            f.write("\n")

    with open(os.path.join(out_dir, "cost_ranking.md"), "w") as f:
        f.write(f"# Modeled annual cost ranking ({result.as_of_date})\n\n")
        f.write(f"Buyer profile: {result.buyer_profile}\n\n")
        for i, e in enumerate(result.cost_ranking, 1):
            f.write(f"{i}. **{e.vendor}** ({e.tier_used}) — ${e.modeled_annual_cost:,.0f}/yr\n")
            for a in e.assumptions:
                f.write(f"   - {a}\n")
        f.write("\n")

    with open(os.path.join(out_dir, "quote_required.md"), "w") as f:
        f.write(f"# Quote required ({result.as_of_date})\n\n")
        for q in result.quote_required:
            f.write(f"- **{q.vendor}**: {q.missing_input}\n  ({q.reason})\n")

    snapshot_path = os.path.join(out_dir, f"snapshot_{result.as_of_date}.json")
    with open(snapshot_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)


def _print_result(result: PricingComparisonResult) -> None:
    print(f"\n{'=' * 70}\nPRICING COMPARISON  (as of {result.as_of_date})\n{'=' * 70}")
    print(f"Buyer profile: {result.buyer_profile}\n")
    print("Cost ranking (cheapest first):")
    for i, e in enumerate(result.cost_ranking, 1):
        print(f"  {i}. {e.vendor} ({e.tier_used}): ${e.modeled_annual_cost:,.0f}/yr")
        for a in e.assumptions:
            print(f"       - {a}")
    if result.quote_required:
        print("\nQuote required:")
        for q in result.quote_required:
            print(f"  - {q.vendor}: {q.missing_input}")
    for v in result.vendors:
        if v.packaging_changes_last_90_days:
            print(f"\n{v.vendor} packaging changes (last 90 days):")
            for c in v.packaging_changes_last_90_days:
                print(f"  - {c.date}: {c.description}")


def _diff_against(result: PricingComparisonResult, prev_path: str) -> None:
    prev = PricingComparisonResult(**json.load(open(prev_path)))
    prev_cost = {e.vendor: e.modeled_annual_cost for e in prev.cost_ranking}
    print(f"\n--- diff vs {prev_path} ---")
    for e in result.cost_ranking:
        old = prev_cost.get(e.vendor)
        if old is None:
            print(f"  {e.vendor}: newly computable at ${e.modeled_annual_cost:,.0f}/yr")
        elif old != e.modeled_annual_cost:
            print(f"  {e.vendor}: ${old:,.0f}/yr -> ${e.modeled_annual_cost:,.0f}/yr")
    old_vendors = {v.vendor: v for v in prev.vendors}
    for v in result.vendors:
        old = old_vendors.get(v.vendor)
        old_dates = {c.date for c in old.packaging_changes_last_90_days} if old else set()
        for c in v.packaging_changes_last_90_days:
            if c.date not in old_dates:
                print(f"  {v.vendor} new packaging change: {c.date} {c.description}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vendors", help="Comma-separated vendor names")
    parser.add_argument("--hosts", type=float, default=None, help="Buyer profile: number of hosts")
    parser.add_argument("--gb-ingested", type=float, default=None, dest="gb_ingested", help="Buyer profile: GB ingested per month")
    parser.add_argument("--seats", type=float, default=None, help="Buyer profile: number of seats")
    parser.add_argument("--events", type=float, default=None, help="Buyer profile: events per month")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--diff-against", default=None, help="Path to a previous snapshot JSON to diff against")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()

    buyer_profile = {
        k: v
        for k, v in {
            "host": args.hosts,
            "gb_ingested_monthly": args.gb_ingested,
            "seat": args.seats,
            "event_monthly": args.events,
        }.items()
        if v is not None
    }
    if not buyer_profile:
        parser.error("supply at least one of --hosts, --gb-ingested, --seats, --events")

    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]
    result = compare(vendors, buyer_profile, model=args.model)
    _print_result(result)
    _write_artifacts(result, args.out_dir)
    print(f"\nWrote {args.out_dir}/comparison_table.md, cost_ranking.md, quote_required.md")

    if not args.no_dashboard:
        dashboard_path = write_dashboard(result, args.out_dir)
        print(f"Wrote {dashboard_path}")
        open_dashboard(dashboard_path)

    diff_against = args.diff_against
    if diff_against is None:
        snaps = sorted(glob.glob(os.path.join(args.out_dir, "snapshot_*.json")))
        snaps = [s for s in snaps if not s.endswith(f"snapshot_{result.as_of_date}.json")]
        diff_against = snaps[-1] if snaps else None
    if diff_against:
        _diff_against(result, diff_against)

    return 0


if __name__ == "__main__":
    sys.exit(main())
