"""CLI entrypoint: research a company, sector, or topic.

    python run.py "NVIDIA"
    python run.py "semiconductor export controls" --model anthropic:claude-sonnet-5 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys

from agent import research


def _print_brief(brief) -> None:
    print(f"\n{'=' * 70}\nREGULATORY BRIEF: {brief.entity}  (as of {brief.as_of_date})\n{'=' * 70}")
    print(f"\n{brief.overall_assessment}\n")
    for i, d in enumerate(brief.developments, 1):
        print(f"[{i}] {d.title}")
        print(f"    type={d.type}  date={d.date}  issuer={d.issuing_body}")
        print(f"    materiality={d.materiality}  confidence={d.confidence}")
        print(f"    {d.summary}")
        print(f"    why it matters: {d.why_it_matters}")
        for u in d.source_urls:
            print(f"      - {u}")
        print()
    print("SOURCES:")
    for u in brief.sources:
        print(f"  - {u}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("subject", help="Company, sector, or topic to research")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL, e.g. openai:gpt-4o or anthropic:claude-sonnet-5")
    parser.add_argument("--json", metavar="PATH", default=None, help="Also write the brief as JSON")
    args = parser.parse_args()

    brief = research(args.subject, model=args.model)
    _print_brief(brief)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(brief.model_dump(), fh, indent=2)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
