"""Pattern B: delegate the whole diligence workflow to a Nimble Web Search Agent.

Where ``agent.py`` keeps the research loop in LangChain and calls Nimble only for
search, this script hands Nimble one research objective and lets its Web Search Agent
do the planning, searching, browsing, cross-checking, and synthesis. It uses Nimble's
official ``nimble-python`` SDK and the documented start -> poll -> result lifecycle:

    nimble.agents.run(...)                 -> returns a run id + web_search_agent_id
    nimble.agents.runs.get(run_id, ...)    -> poll until status == "completed"
    nimble.agents.runs.result(run_id, ...) -> the finished profile + trust/citations

    python agent_api_v2.py "Ramp"
    python agent_api_v2.py "Brex" --effort x-high --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import DIMENSIONS, SKILL

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

# Nimble's Agent API validates output_schema and rejects open objects and $ref/$defs,
# so this is a flat, self-contained mirror of schema.DiligenceProfile — including the
# fields the prompt asks for: as_of_date, funding.last_round_valuation, and a
# confidence-per-dimension list.
DILIGENCE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "as_of_date": {"type": "string"},
        "business_model": {"type": "string"},
        "products_services": {"type": "array", "items": {"type": "string"}},
        "leadership": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "background": {"type": "string"},
                },
            },
        },
        "funding": {
            "type": "object",
            "properties": {
                "total_raised": {"type": "string"},
                "last_round": {"type": "string"},
                "last_round_date": {"type": "string"},
                "last_round_valuation": {"type": "string"},
                "key_investors": {"type": "array", "items": {"type": "string"}},
            },
        },
        "partnerships": {"type": "array", "items": {"type": "string"}},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "regulatory_notes": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "insufficient_evidence": {"type": "array", "items": {"type": "string"}},
        "confidence_by_dimension": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string"},
                    "grade": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "company", "as_of_date", "business_model", "products_services",
        "competitors", "risks", "confidence_by_dimension",
    ],
}


def run_research(company: str, effort: str = "high", poll_interval: int = 15, timeout: int = 1800) -> dict:
    """Start a Web Search Agent run and block until it finishes, then return the result."""
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Conduct preliminary investment due diligence on {company}. Research its "
        f"business model, products, leadership, funding, major partnerships, competitive "
        f"position, and key risks. Cross-check funding figures against a second source. "
        f"Keep funding.total_raised and funding.last_round terse (e.g. '$1.9B', "
        f"'Series F, $750M at $44B'). Return a confidence grade (high/medium/low) for "
        f"each of these dimensions: {', '.join(DIMENSIONS)}."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="company-due-diligence",
        use_case="research",
        skill=SKILL,
        effort=effort,
        output_schema=DILIGENCE_OUTPUT_SCHEMA,
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
    # trust / citations live under output, not at the top level
    trust = output.get("trust") if isinstance(output, dict) else None
    if trust:
        print(f"\n--- trust / citations ---\n{json.dumps(trust, indent=2, default=str)[:4000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("company")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--json", metavar="PATH", default=None)
    args = parser.parse_args()

    result = run_research(args.company, effort=args.effort, poll_interval=args.poll_interval)
    _print_result(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
