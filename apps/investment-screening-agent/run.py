"""CLI entrypoint: turn an investment thesis into a ranked shortlist.

    python run.py "US private companies building AI software for insurance carriers"
    python run.py "Seed-stage LLM underwriting tools" --count 15 --model anthropic:claude-sonnet-5
"""

from __future__ import annotations

import argparse
import json
import sys

from agent import screen


def _print_result(r) -> None:
    print(f"\n{'=' * 70}\nSCREENING: {r.thesis}\n(as of {r.as_of_date})\n{'=' * 70}")
    print("\nInclusion criteria:")
    for c in r.inclusion_criteria:
        print(f"  - {c}")
    print(f"\nRanked shortlist ({len(r.ranked_shortlist)}):")
    for i, name in enumerate(r.ranked_shortlist, 1):
        print(f"  {i}. {name}")
    print("\nCandidates:")
    by_name = {c.company_name: c for c in r.candidates}
    ordered = [by_name[n] for n in r.ranked_shortlist if n in by_name]
    ordered += [c for c in r.candidates if c.company_name not in r.ranked_shortlist]
    for c in ordered:
        print(f"\n  {c.company_name}  [{c.fit_score}]")
        print(f"    HQ: {c.headquarters}")
        print(f"    Product: {c.product_focus}")
        print(f"    Customer: {c.target_customer}")
        print(f"    Funding: {c.funding_total}  Investors: {', '.join(c.major_investors)}")
        print(f"    Fit: {c.fit_rationale}")
        for u in c.evidence_urls:
            print(f"      - {u}")
    if r.excluded:
        print("\nExcluded / near-misses:")
        for e in r.excluded:
            print(f"  - {e.company_name}: {e.reason}")
    print("\nSources:")
    for u in r.sources:
        print(f"  - {u}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("thesis", help="Short investment thesis")
    parser.add_argument("--count", type=int, default=None, help="Target number of companies (default 25)")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--json", metavar="PATH", default=None, help="Also write the result as JSON")
    args = parser.parse_args()

    result = screen(args.thesis, model=args.model, target_count=args.count)
    _print_result(result)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result.model_dump(), fh, indent=2)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
