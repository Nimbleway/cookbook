"""Pattern B: delegate vendor discovery and sizing to a Nimble Web Search Agent.

Hands Nimble one dataset-building objective (find N vendors, rule each in or out,
collect published size estimates) and lets its Web Search Agent do the discovery and
research. The output is the same LandscapeExtractionBatch shape Pattern A produces, so
landscape_model.build_result (dedupe, enforcement, bottom-up sizing, reconciliation) is
identical downstream. Only the retrieval step changes.

    python agent_api_v2.py "LLM observability and evaluation platforms" \\
        --criteria "dedicated LLM observability or evaluation product" --count 30
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL
from dashboard import open_dashboard, write_dashboard
from landscape_model import build_result
from schema import PublishedEstimate, VendorCandidate

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

LANDSCAPE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "inclusion_criteria": {"type": "array", "items": {"type": "string"}},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "headquarters": {"type": "string"},
                    "product_focus": {"type": "string"},
                    "deployment_model": {"type": "string"},
                    "pricing_model": {"type": "string"},
                    "target_segment": {"type": "string"},
                    "funding_total": {"type": "string"},
                    "disclosed_arr": {"type": "string"},
                    "major_investors": {"type": "array", "items": {"type": "string"}},
                    "evidence_urls": {"type": "array", "items": {"type": "string"}},
                    "include": {"type": "boolean"},
                    "exclusion_reason": {"type": "string"},
                },
                "required": ["company_name", "product_focus", "evidence_urls", "include"],
            },
        },
        "published_estimates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "figure": {"type": "string"},
                    "methodology": {"type": "string"},
                    "url": {"type": "string"},
                    "published_date": {"type": "string"},
                },
                "required": ["source", "figure", "url"],
            },
        },
    },
    "required": ["category", "inclusion_criteria", "candidates", "published_estimates"],
}


def run_research(category: str, inclusion_criteria: list[str], count: int, effort: str = "high", poll_interval: int = 20, timeout: int = 2400) -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Find about {count} vendors in the category: {category}. Inclusion criteria: "
        f"{'; '.join(inclusion_criteria)}. Use exactly these criteria, do not add "
        f"further requirements of your own beyond what is listed here, an invented "
        f"stricter bar is why past runs on this exact prompt have come back with zero "
        f"included vendors despite the category being well populated. For each vendor, "
        f"return headquarters, product focus, deployment model, pricing model, target "
        f"segment, funding, major investors, and disclosed revenue/ARR if publicly "
        f"stated, with supporting evidence. Deduplicate, rule every candidate include "
        f"or exclude against ONLY the stated criteria with a reason for each exclusion, "
        f"and list near-misses. If you are uncertain whether a real, well-known vendor "
        f"in this category meets the stated criteria, include it with a lower "
        f"confidence note rather than excluding it outright. Separately, find published "
        f"size or growth estimates for this category with their source and methodology."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="market-landscape",
        use_case="dataset_building",
        skill=SKILL,
        effort=effort,
        output_schema=LANDSCAPE_SCHEMA,
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


def main() -> int:
    from run import _print_result, _write_artifacts

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("category")
    parser.add_argument("--criteria", action="append", default=[])
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--json", metavar="PATH", default=None)
    parser.add_argument("--no-dashboard", action="store_true", help="Skip writing/opening the HTML dashboard")
    args = parser.parse_args()
    if not args.criteria:
        parser.error("supply at least one --criteria")

    raw = run_research(args.category, args.criteria, args.count, effort=args.effort, poll_interval=args.poll_interval)
    output = raw.get("output", {})
    content = output.get("content", output) if isinstance(output, dict) else output

    candidates = [VendorCandidate(**c) for c in content.get("candidates", [])]
    published = [PublishedEstimate(**p) for p in content.get("published_estimates", [])]
    result = build_result(
        content.get("category", args.category),
        content.get("inclusion_criteria", args.criteria),
        candidates,
        published,
        dt.date.today().isoformat(),
    )
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
