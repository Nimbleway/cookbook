"""CLI entrypoint: run preliminary due diligence on a company.

    python run.py "Ramp"
    python run.py "Brex" --model anthropic:claude-sonnet-5 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys

from agent import diligence


def _print_profile(p) -> None:
    print(f"\n{'=' * 70}\nDUE DILIGENCE: {p.company}  (as of {p.as_of_date})\n{'=' * 70}")
    print(f"\nBusiness model:\n  {p.business_model}\n")
    print("Products & services:")
    for x in p.products_services:
        print(f"  - {x}")
    print("\nLeadership:")
    for person in p.leadership:
        bg = f" - {person.background}" if person.background else ""
        print(f"  - {person.name}, {person.role}{bg}")
    f = p.funding
    print("\nFunding:")
    print(f"  total_raised={f.total_raised}  last_round={f.last_round} ({f.last_round_date})")
    print(f"  last_round_valuation={f.last_round_valuation}")
    print(f"  key_investors={', '.join(f.key_investors)}")
    print("\nPartnerships:")
    for x in p.partnerships:
        print(f"  - {x}")
    print("\nCompetitors:")
    for x in p.competitors:
        print(f"  - {x}")
    if p.regulatory_notes:
        print(f"\nRegulatory / legal:\n  {p.regulatory_notes}")
    print("\nScorecard")
    print("  Strengths:")
    for x in p.scorecard.strengths:
        print(f"    + {x}")
    print("  Risks:")
    for x in p.scorecard.risks:
        print(f"    - {x}")
    print("  Insufficient evidence:")
    for x in p.scorecard.insufficient_evidence:
        print(f"    ? {x}")
    print("\nConfidence by dimension:")
    for entry in p.confidence_by_dimension:
        k, v = entry.dimension, entry.grade
        print(f"  {k}: {v}")
    print("\nSources:")
    for u in p.sources:
        print(f"  - {u}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("company", help="Company name to run diligence on")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--json", metavar="PATH", default=None, help="Also write the profile as JSON")
    args = parser.parse_args()

    profile = diligence(args.company, model=args.model)
    _print_profile(profile)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(profile.model_dump(), fh, indent=2)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
