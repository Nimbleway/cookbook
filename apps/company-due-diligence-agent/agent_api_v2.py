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
import re
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import DIMENSIONS, SKILL

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

# Nimble's Agent API validates output_schema and rejects open objects and $ref/$defs,
# so this is a self-contained mirror of schema.DiligenceProfile — including the fields
# the prompt asks for: as_of_date, funding.last_round_valuation, and a
# confidence-per-dimension list.
#
# Two things matter here and are easy to get wrong:
#   1. `required` must be repeated on every nested object (leadership items, funding,
#      scorecard, confidence_by_dimension items). Without it the API legitimately
#      returns an empty `confidence_by_dimension` and leadership entries with no
#      `background` — dropping the per-dimension grades this profile exists to provide.
#   2. Every `description` from schema.py has to be restated here. Those descriptions
#      are what keep `funding.total_raised` a short phrase and `sources` full URLs; a
#      bare {"type": "string"} carries none of that instruction.
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
                    "name": {"type": "string", "description": "Full name"},
                    "role": {"type": "string", "description": "Current title at the company"},
                    "background": {
                        "type": "string",
                        "description": "Prior roles / notable history — required, not optional",
                    },
                },
                "required": ["name", "role", "background"],
            },
        },
        "funding": {
            "type": "object",
            "properties": {
                "total_raised": {
                    "type": "string",
                    "description": (
                        "Short phrase only, e.g. '$1.9B'. Never a paragraph, never inline "
                        "URLs, and never a list of conflicting figures per database — pick "
                        "the best-supported number."
                    ),
                },
                "last_round": {
                    "type": "string",
                    "description": "Short phrase, e.g. 'Series F, $750M' — the round name and size",
                },
                "last_round_date": {"type": "string", "description": "e.g. 'Jun 2026'"},
                "last_round_valuation": {"type": "string", "description": "e.g. '$44B post-money'"},
                "key_investors": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "total_raised", "last_round", "last_round_date",
                "last_round_valuation", "key_investors",
            ],
        },
        "partnerships": {"type": "array", "items": {"type": "string"}},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "regulatory_notes": {"type": "string"},
        # Nested to mirror schema.Scorecard, so a Pattern B result parses with
        # schema.DiligenceProfile. Previously these three were flat at the top level,
        # which made the two patterns return incompatible shapes for the same task.
        "scorecard": {
            "type": "object",
            "properties": {
                "strengths": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "insufficient_evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dimensions where public evidence was thin or conflicting",
                },
            },
            "required": ["strengths", "risks", "insufficient_evidence"],
        },
        "confidence_by_dimension": {
            "type": "array",
            "description": (
                "One entry per diligence dimension — business model, products and services, "
                "leadership, funding and investors, partnerships, competitors, regulatory "
                "and legal. All seven must be present."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string"},
                    "grade": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["dimension", "grade"],
            },
        },
        "sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Supporting URLs as full https:// URLs — not bare hostnames like "
                "'ramp.com/about-us' and not prose references."
            ),
        },
    },
    "required": [
        "company", "as_of_date", "business_model", "products_services", "leadership",
        "funding", "partnerships", "competitors", "regulatory_notes", "scorecard",
        "confidence_by_dimension", "sources",
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



_SCHEMELESS = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#]|$)", re.I)


def _normalize_url(value: str) -> str:
    """Prepend https:// to a scheme-less citation like 'sec.gov/Archives/...'.

    The agent frequently returns citations without a scheme, which are not clickable
    and not fetchable. Anything that does not look like a bare host+path is returned
    unchanged, so prose references are left alone for the caller to notice.
    """
    v = (value or "").strip()
    if not v or v.startswith(("http://", "https://")):
        return v
    return f"https://{v}" if _SCHEMELESS.match(v) else v


def _normalize_urls(urls) -> list[str]:
    out: list[str] = []
    for u in urls or []:
        n = _normalize_url(str(u))
        if n and n not in out:
            out.append(n)
    return out

def _validate_and_backfill(output: dict) -> list[str]:
    """Recover `sources` from `trust` and report fields that came back empty.

    `required` in an output_schema is a strong hint, not a guarantee — runs still come
    back missing fields, so check rather than trust.
    """
    warnings: list[str] = []
    content = output.get("content")
    if not isinstance(content, dict):
        return ["no structured content in the result"]
    trust = output.get("trust") if isinstance(output.get("trust"), dict) else {}

    if content.get("sources"):
        content["sources"] = _normalize_urls(content["sources"])
    srcs = content.get("sources") or []
    if not any(str(s).startswith("http") for s in srcs):
        recovered = [s.get("url") for s in (trust.get("sources") or []) if s.get("url")]
        if recovered:
            content["sources"] = recovered
            warnings.append(f"sources held no full URLs; recovered {len(recovered)} from trust.sources")
        elif srcs:
            warnings.append("sources are bare hostnames or prose, not full URLs")
        else:
            warnings.append("no sources returned")

    grades = content.get("confidence_by_dimension") or []
    if not grades:
        warnings.append(f"confidence_by_dimension is empty (expected {len(DIMENSIONS)} entries)")
    elif len(grades) < len(DIMENSIONS):
        got = {str(g.get("dimension", "")).lower() for g in grades if isinstance(g, dict)}
        absent = [d for d in DIMENSIONS if d.lower() not in got]
        warnings.append(f"confidence_by_dimension has {len(grades)}/{len(DIMENSIONS)}; missing: {', '.join(absent)}")

    for f in ("company", "as_of_date", "business_model", "products_services", "competitors", "scorecard"):
        if not content.get(f):
            warnings.append(f"missing required field {f!r}")

    no_bg = [p.get("name", "?") for p in (content.get("leadership") or []) if isinstance(p, dict) and not p.get("background")]
    if no_bg:
        warnings.append(f"leadership entries with no background: {', '.join(no_bg)}")

    total = str((content.get("funding") or {}).get("total_raised") or "")
    if len(total) > 40 or "http" in total:
        warnings.append(f"funding.total_raised is not a short phrase: {total[:70]!r}")
    return warnings

def _print_result(result: dict) -> None:
    output = result.get("output", {})
    warnings = _validate_and_backfill(output) if isinstance(output, dict) else []
    print(f"\n{'=' * 70}\nNIMBLE WEB SEARCH AGENT RESULT\n{'=' * 70}")
    if isinstance(output, dict) and output.get("type") == "json":
        print(json.dumps(output.get("content", output), indent=2, default=str))
    elif isinstance(output, dict) and output.get("type") == "text":
        print(output.get("content", ""))
    else:
        print(json.dumps(output or result, indent=2, default=str))
    if warnings:
        print(f"\n--- incomplete output ({len(warnings)}) ---")
        for w in warnings:
            print(f"  ! {w}")
        print("  (the run still succeeded; these fields came back empty or malformed)")
    # trust / citations live under output, not at the top level
    trust = output.get("trust") if isinstance(output, dict) else None
    if trust:
        print(f"\n--- trust / citations ---\n{json.dumps(trust, indent=2, default=str)[:4000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("company")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "5x-high", "max"])
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
