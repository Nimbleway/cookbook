"""Pattern B: delegate the whole workflow to a Nimble Web Search Agent (Agent API).

Where ``agent.py`` keeps the research loop in LangChain and calls Nimble only for
search, this script hands Nimble one research objective and lets its Web Search Agent
do the planning, searching, browsing, cross-checking, and synthesis. It uses Nimble's
official ``nimble-python`` SDK and the documented start -> poll -> result lifecycle:

    nimble.agents.run(...)                 -> returns a run id + web_search_agent_id
    nimble.agents.runs.get(run_id, ...)    -> poll until status == "completed"
    nimble.agents.runs.result(run_id, ...) -> the finished brief + trust/citations

    python agent_api_v2.py "NVIDIA"
    python agent_api_v2.py "semiconductor export controls" --effort x-high --json out.json
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

# Nimble's Agent API validates output_schema and rejects open objects and $ref/$defs,
# so this is a flat, self-contained mirror of schema.RegulatoryBrief.
BRIEF_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "entity": {"type": "string"},
        "as_of_date": {"type": "string"},
        "developments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["filing", "enforcement", "investigation", "policy", "guidance", "other"],
                    },
                    "date": {"type": "string"},
                    "issuing_body": {"type": "string"},
                    "summary": {"type": "string"},
                    "materiality": {"type": "string", "enum": ["high", "medium", "low"]},
                    "why_it_matters": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "overall_assessment": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["entity", "as_of_date", "developments", "overall_assessment", "sources"],
}


def run_research(subject: str, effort: str = "high", poll_interval: int = 15, timeout: int = 1800) -> dict:
    """Start a Web Search Agent run and block until it finishes, then return the result."""
    client = Nimble()  # reads NIMBLE_API_KEY from the environment

    prompt = (
        f"Research recent regulatory and filing developments related to {subject}. "
        f"Identify material SEC disclosures, regulatory actions, investigations, or "
        f"policy developments that could affect the subject. Explain what changed, why "
        f"it matters, and cite the underlying primary documents. Quote figures exactly "
        f"as the filing states them."
    )

    started = client.agents.run(
        input=prompt,
        agent_name="regulatory-intelligence",
        use_case="research",
        skill=SKILL,
        effort=effort,
        output_schema=BRIEF_OUTPUT_SCHEMA,
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
    parser.add_argument("subject")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "max"])
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--json", metavar="PATH", default=None)
    args = parser.parse_args()

    result = run_research(args.subject, effort=args.effort, poll_interval=args.poll_interval)
    _print_result(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
