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
import re
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

# Nimble's Agent API validates output_schema and rejects open objects and $ref/$defs,
# so this is a flat, self-contained mirror of schema.RegulatoryBrief.
#
# Two things matter here and are easy to get wrong:
#   1. `required` must be repeated on the nested `developments` item object. Without it
#      the API legitimately returns developments carrying only title/summary/
#      why_it_matters — no date, materiality, confidence or source_urls — which silently
#      strips exactly the grades and citations this brief exists to provide.
#   2. Every `description` from schema.RegulatoryBrief has to be restated here. The
#      Pydantic descriptions are what tell the agent to emit a URL rather than a prose
#      reference like "SEC EDGAR 10-Q for the period ended July 26, 2026"; a bare
#      {"type": "string"} carries none of that instruction.
BRIEF_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "entity": {"type": "string", "description": "The company, sector, or topic researched"},
        "as_of_date": {"type": "string", "description": "Date the research was run (YYYY-MM-DD)"},
        "developments": {
            "type": "array",
            "description": "3-6 material regulatory developments, each read from a primary document",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short headline for the development"},
                    "type": {
                        "type": "string",
                        "enum": ["filing", "enforcement", "investigation", "policy", "guidance", "other"],
                        "description": "Kind of development",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of the development (YYYY-MM-DD or as reported)",
                    },
                    "issuing_body": {
                        "type": "string",
                        "description": "Regulator, court, or company that issued it",
                    },
                    "summary": {"type": "string", "description": "What changed, in 1-3 sentences"},
                    "materiality": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "How material this is to the company or sector",
                    },
                    "why_it_matters": {
                        "type": "string",
                        "description": "Why this could affect the company or sector",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Low unless confirmed from a primary source",
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Full https:// URLs of the primary documents supporting this "
                            "development. Must be actual URLs, not prose descriptions of a "
                            "filing, and must point at the document itself rather than a "
                            "summary of it."
                        ),
                    },
                },
                "required": [
                    "title", "type", "date", "issuing_body", "summary",
                    "materiality", "why_it_matters", "confidence", "source_urls",
                ],
            },
        },
        "overall_assessment": {
            "type": "string",
            "description": "2-4 sentences on the net regulatory picture for the subject",
        },
        "sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "All primary source URLs cited in the brief, as full https:// URLs — "
                "not prose references to a filing."
            ),
        },
    },
    "required": ["entity", "as_of_date", "developments", "overall_assessment", "sources"],
}


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


_CLAIM_PATH = re.compile(r"^\$\.developments\[(\d+)\]")


def _trust_urls_by_development(trust: dict) -> dict[int, list[str]]:
    """Group the citation URLs in `trust.claims` by which development they back.

    The Agent API reports per-claim citations under ``trust.claims[].path`` (e.g.
    ``$.developments[2].summary``). Those citations are the real primary-document URLs
    even when the model leaves ``source_urls`` empty, so they can be folded back into
    the brief rather than lost.
    """
    by_dev: dict[int, list[str]] = {}
    for claim in (trust or {}).get("claims") or []:
        m = _CLAIM_PATH.match(str(claim.get("path") or ""))
        if not m:
            continue
        idx = int(m.group(1))
        for cite in claim.get("citations") or []:
            url = cite.get("url")
            if url and url not in by_dev.setdefault(idx, []):
                by_dev[idx].append(url)
    return by_dev


def _backfill_citations(output: dict) -> list[str]:
    """Fill empty `source_urls` / `sources` from `trust`, and report what is still thin.

    Returns a list of human-readable warnings; mutates ``output["content"]`` in place.
    """
    warnings: list[str] = []
    content = output.get("content")
    if not isinstance(content, dict):
        return warnings
    trust = output.get("trust") if isinstance(output.get("trust"), dict) else {}
    by_dev = _trust_urls_by_development(trust)

    devs = content.get("developments")
    if not isinstance(devs, list) or not devs:
        warnings.append("no developments returned")
        devs = []
    for i, dev in enumerate(devs):
        if not isinstance(dev, dict):
            continue
        missing = [f for f in ("date", "type", "issuing_body", "materiality", "confidence") if not dev.get(f)]
        if not dev.get("source_urls") and by_dev.get(i):
            dev["source_urls"] = list(by_dev[i])
            missing.append("source_urls (recovered from trust.claims)")
        # Citations often come back scheme-less ("sec.gov/Archives/..."); make them
        # clickable and fetchable.
        if dev.get("source_urls"):
            dev["source_urls"] = _normalize_urls(dev["source_urls"])
            if not any(u.startswith("http") for u in dev["source_urls"]):
                missing.append("source_urls are prose, not URLs")
        if missing:
            warnings.append(f"development[{i}] {dev.get('title', '?')!r}: missing {', '.join(missing)}")

    if content.get("sources"):
        content["sources"] = _normalize_urls(content["sources"])
    srcs = content.get("sources") or []
    if not any("http" in str(s) for s in srcs):
        recovered = [s.get("url") for s in (trust.get("sources") or []) if s.get("url")]
        if recovered:
            content["sources"] = recovered
            warnings.append(f"sources held no URLs; recovered {len(recovered)} from trust.sources")
        elif srcs:
            warnings.append("sources contains prose references rather than URLs")
    for f in ("entity", "as_of_date", "overall_assessment"):
        if not content.get(f):
            warnings.append(f"missing required field {f!r}")
    return warnings


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
    warnings = _backfill_citations(output) if isinstance(output, dict) else []
    print(f"\n{'=' * 70}\nNIMBLE WEB SEARCH AGENT RESULT\n{'=' * 70}")
    if isinstance(output, dict) and output.get("type") == "json":
        print(json.dumps(output.get("content", output), indent=2, default=str))
    elif isinstance(output, dict) and output.get("type") == "text":
        print(output.get("content", ""))
    else:
        print(json.dumps(output or result, indent=2, default=str))
    # trust / citations live under output, not at the top level
    if warnings:
        print(f"\n--- incomplete output ({len(warnings)}) ---")
        for w in warnings:
            print(f"  ! {w}")
        print("  (the run still succeeded; these fields came back empty or non-URL)")
    trust = output.get("trust") if isinstance(output, dict) else None
    if trust:
        print(f"\n--- trust / citations ---\n{json.dumps(trust, indent=2, default=str)[:4000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("subject")
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high", "x-high", "5x-high", "max"])
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
