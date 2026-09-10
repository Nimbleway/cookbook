"""Pattern B: delegate the whole deal-sourcing workflow to a Nimble Web Search Agent.

Where ``agent.py`` runs the broaden -> narrow -> dedupe -> rank loop in LangChain and
calls Nimble only for search, this script hands Nimble one dataset-building objective
and lets its Web Search Agent do the discovery, per-company research, qualification,
deduplication, and ranking. It uses Nimble's official ``nimble-python`` SDK and the
documented start -> poll -> result lifecycle.

    python agent_api_v2.py "US private companies building AI software for insurance carriers"
    python agent_api_v2.py "Seed-stage LLM tools for commercial underwriting" --count 15 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

# Flat, self-contained mirror of schema.ScreeningResult (Nimble's Agent API rejects
# $ref/$defs and open objects).
SCREENING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "thesis": {"type": "string"},
        "as_of_date": {"type": "string"},
        "inclusion_criteria": {"type": "array", "items": {"type": "string"}},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "headquarters": {"type": "string"},
                    "product_focus": {"type": "string"},
                    "target_customer": {"type": "string"},
                    "funding_total": {"type": "string"},
                    "major_investors": {"type": "array", "items": {"type": "string"}},
                    "fit_rationale": {"type": "string"},
                    "fit_score": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "evidence_urls": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "ranked_shortlist": {"type": "array", "items": {"type": "string"}},
        "excluded": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["thesis", "as_of_date", "inclusion_criteria", "candidates", "ranked_shortlist", "sources"],
}


def run_research(thesis: str, count: int = 25, effort: str = "high", poll_interval: int = 20, timeout: int = 2400) -> dict:
    """Start a Web Search Agent run and block until it finishes, then return the result."""
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Investment thesis: {thesis}\n\n"
        f"Find about {count} companies that fit this thesis. For each company return "
        f"headquarters, product focus, target customer, total funding, major investors, "
        f"and supporting evidence URLs. Validate that each company genuinely fits before "
        f"including it, deduplicate companies that appear under multiple names, and rank "
        f"the survivors. List near-misses in `excluded` with a one-line reason."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="investment-screening",
        use_case="dataset_building",
        skill=SKILL,
        effort=effort,
        output_schema=SCREENING_OUTPUT_SCHEMA,
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


def _print_result(result: dict) -> None:
    output = result.get("output", {})
    print(f"\n{'=' * 70}\nNIMBLE WEB SEARCH AGENT RESULT\n{'=' * 70}")
    if isinstance(output, dict) and output.get("type") == "json":
        print(json.dumps(output.get("content", output), indent=2, default=str))
    elif isinstance(output, dict) and output.get("type") == "text":
        print(output.get("content", ""))
    else:
        print(json.dumps(output or result, indent=2, default=str))
    trust = output.get("trust") if isinstance(output, dict) else None
    if trust:
        print(f"\n--- trust / citations ---\n{json.dumps(trust, indent=2, default=str)[:4000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("thesis")
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--json", metavar="PATH", default=None)
    args = parser.parse_args()

    result = run_research(args.thesis, count=args.count, effort=args.effort, poll_interval=args.poll_interval)
    _print_result(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
