"""CLI entrypoint: analyze consumer sentiment for a brand.

    python run.py "Chipotle"
    python run.py "Chipotle" --window-days 90 --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from agent import analyze
from dashboard import open_dashboard, write_dashboard
from schema import SentimentResult


def _print_result(r: SentimentResult) -> None:
    print(f"\n{'=' * 70}\nSENTIMENT: {r.brand}  (as of {r.as_of_date}, {r.window_days}-day windows)\n{'=' * 70}")
    print(f"Items considered: {r.total_items_considered}  after dedupe: {r.total_items_after_dedupe}\n")

    print(f"TRIAGE LIST ({len(r.triage_list)} escalated theme(s)):")
    for row in r.triage_list:
        pct = f"{row.change_pct:+.0f}%" if row.change_pct is not None else "n/a"
        print(f"\n  [{row.direction.upper()}] {row.theme}  negative volume {pct} vs prior window")
        print(f"    current: {row.current_volume} items ({row.current_negative} negative), sample_size={row.sample_size}")
        print(f"    prior:   {row.prior_volume} items ({row.prior_negative} negative)")
        print(f"    source mix: {row.source_mix}")
        for q in row.representative_quotes:
            print(f'    - "{q["text"]}" ({q["url"]}, {q["date"]})')

    non_escalated = [row for row in r.theme_table if not row.escalated]
    if non_escalated:
        print(f"\nFULL THEME TABLE (not escalated, {len(non_escalated)}):")
        for row in non_escalated:
            pct = f"{row.change_pct:+.0f}%" if row.change_pct is not None else "n/a"
            print(f"  {row.theme}: {row.current_volume} items, {pct} vs prior, sample_size={row.sample_size}")

    if r.insufficient_volume:
        print(f"\nINSUFFICIENT VOLUME (dropped, below minimum sample size):")
        for t in r.insufficient_volume:
            print(f"  - {t}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brand", help="Brand to analyze")
    parser.add_argument("--window-days", type=int, default=90, help="Size of the current/prior comparison window")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--json", metavar="PATH", default=None)
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()

    result = analyze(args.brand, model=args.model, window_days=args.window_days)
    _print_result(result)

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w") as fh:
            json.dump(result.model_dump(), fh, indent=2)
        print(f"\nWrote {args.json}")

    if not args.no_dashboard:
        dashboard_path = write_dashboard(result, args.out_dir)
        print(f"Wrote {dashboard_path}")
        open_dashboard(dashboard_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
