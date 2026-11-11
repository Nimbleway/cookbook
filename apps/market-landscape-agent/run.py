"""CLI entrypoint: map a market category and size it bottom-up.

    python run.py "LLM observability and evaluation platforms" \\
        --criteria "dedicated LLM observability or evaluation product" \\
        --criteria "not a general-purpose APM vendor without an LLM-specific product"

Writes three artifacts to --out-dir (default ./output): landscape_table.md,
exclusions.md, reconciliation.md, plus a timestamped JSON snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from agent import map_landscape
from dashboard import open_dashboard, write_dashboard
from schema import LandscapeResult


def _write_artifacts(result: LandscapeResult, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "landscape_table.md"), "w") as f:
        f.write(f"# {result.category} landscape ({result.as_of_date})\n\n")
        f.write("Inclusion criteria:\n")
        for c in result.inclusion_criteria:
            f.write(f"- {c}\n")
        f.write(f"\n{len(result.included)} included vendors:\n\n")
        f.write("| Company | HQ | Product focus | Deployment | Pricing | Segment | Funding | ARR | Evidence |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for v in result.included:
            f.write(
                f"| {v.company_name} | {v.headquarters or '-'} | {v.product_focus} | "
                f"{v.deployment_model or '-'} | {v.pricing_model or '-'} | {v.target_segment or '-'} | "
                f"{v.funding_total or '-'} | {v.disclosed_arr or '-'} | {v.evidence_urls[0] if v.evidence_urls else '-'} |\n"
            )

    with open(os.path.join(out_dir, "exclusions.md"), "w") as f:
        f.write(f"# Excluded candidates ({result.as_of_date})\n\n")
        for v in result.excluded:
            f.write(f"- **{v.company_name}**: {v.exclusion_reason}\n")

    with open(os.path.join(out_dir, "reconciliation.md"), "w") as f:
        f.write(f"# Market sizing reconciliation ({result.as_of_date})\n\n")
        b = result.bottom_up
        f.write(f"**Bottom-up estimate: ${b.low:,.0f} to ${b.high:,.0f}** (confidence: {b.confidence})\n\n")
        for a in b.assumptions:
            f.write(f"- {a}\n")
        f.write("\n**Published estimates:**\n\n")
        for flag in result.reconciliation:
            marker = "FLAGGED - disagrees" if flag.flagged else "consistent"
            f.write(f"- {flag.published_source}: \"{flag.published_figure}\" — {marker}: {flag.note}\n")

    snapshot_path = os.path.join(out_dir, f"snapshot_{result.as_of_date}.json")
    with open(snapshot_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)


def _print_result(result: LandscapeResult) -> None:
    print(f"\n{'=' * 70}\n{result.category.upper()} LANDSCAPE  (as of {result.as_of_date})\n{'=' * 70}")
    print(f"Included: {len(result.included)}  Excluded: {len(result.excluded)}\n")
    for v in result.included:
        print(f"  + {v.company_name} ({v.headquarters or 'HQ unknown'}) - {v.product_focus}")
    print("\nExcluded (sample):")
    for v in result.excluded[:8]:
        print(f"  - {v.company_name}: {v.exclusion_reason}")

    b = result.bottom_up
    print(f"\nBottom-up estimate: ${b.low:,.0f} to ${b.high:,.0f}  (confidence: {b.confidence})")
    for a in b.assumptions:
        print(f"  - {a}")

    print("\nReconciliation vs published estimates:")
    for flag in result.reconciliation:
        marker = "FLAGGED" if flag.flagged else "ok"
        print(f"  [{marker}] {flag.published_source}: \"{flag.published_figure}\" - {flag.note}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("category", help="Category definition")
    parser.add_argument("--criteria", action="append", default=[], help="Repeatable: one inclusion criterion per flag")
    parser.add_argument("--count", type=int, default=None, help="Target number of candidates (default 30)")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()

    if not args.criteria:
        parser.error("supply at least one --criteria")

    from agent import DEFAULT_TARGET_COUNT

    result = map_landscape(args.category, args.criteria, model=args.model, target_count=args.count or DEFAULT_TARGET_COUNT)
    _print_result(result)
    _write_artifacts(result, args.out_dir)
    print(f"\nWrote {args.out_dir}/landscape_table.md, exclusions.md, reconciliation.md")

    if not args.no_dashboard:
        dashboard_path = write_dashboard(result, args.out_dir)
        print(f"Wrote {dashboard_path}")
        open_dashboard(dashboard_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
