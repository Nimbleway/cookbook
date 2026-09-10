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
import re
import sys
import time

from dotenv import load_dotenv
from nimble_python import Nimble

from config import SKILL

load_dotenv()

TERMINAL = {"completed", "failed", "cancelled", "error"}

# Flat, self-contained mirror of schema.ScreeningResult (Nimble's Agent API rejects
# $ref/$defs and open objects).
#
# Two things matter here and are easy to get wrong:
#   1. `required` must be repeated on the nested `candidates` / `excluded` item objects.
#      Without it the API legitimately returns candidates with no evidence_urls, and an
#      empty ranked_shortlist — the shortlist this agent exists to produce.
#   2. Every `description` from schema.py has to be restated here; a bare
#      {"type": "string"} carries none of that instruction.
SCREENING_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "thesis": {"type": "string"},
        "as_of_date": {"type": "string"},
        "inclusion_criteria": {"type": "array", "items": {"type": "string"}},
        "candidates": {
            "type": "array",
            "description": "One entry per distinct company that passes the inclusion criteria",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": (
                            "The company's own name only. Never an editorial note such as "
                            "'(duplicate of X)' or 'placeholder'."
                        ),
                    },
                    "headquarters": {"type": "string", "description": "City, region/country"},
                    "product_focus": {"type": "string", "description": "What the company builds, in one line"},
                    "target_customer": {"type": "string", "description": "Who it sells to"},
                    "funding_total": {"type": "string", "description": "e.g. '$27M' or 'undisclosed'"},
                    "major_investors": {"type": "array", "items": {"type": "string"}},
                    "fit_rationale": {
                        "type": "string",
                        "description": "One line: why this company matches the thesis",
                    },
                    "fit_score": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "evidence_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Full https:// URLs supporting this company. At least one must "
                            "be something other than a personal LinkedIn profile."
                        ),
                    },
                },
                "required": [
                    "company_name", "headquarters", "product_focus", "target_customer",
                    "funding_total", "major_investors", "fit_rationale", "fit_score",
                    "evidence_urls",
                ],
            },
        },
        "ranked_shortlist": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Company names, best fit first. Must contain every name in `candidates`."
            ),
        },
        "excluded": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "reason": {"type": "string", "description": "One line on why it failed a criterion"},
                },
                "required": ["company_name", "reason"],
            },
        },
        "sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": "All evidence URLs cited, as full https:// URLs",
        },
    },
    "required": ["thesis", "as_of_date", "inclusion_criteria", "candidates", "ranked_shortlist", "sources"],
}


# The Agent API rejects `use_case="dataset_building"` below "medium" effort.
MIN_EFFORT = "medium"
_EFFORT_ORDER = ("low", "medium", "high", "x-high", "5x-high", "max")


def run_research(thesis: str, count: int = 25, effort: str = "high", poll_interval: int = 20, timeout: int = 2400) -> dict:
    """Start a Web Search Agent run and block until it finishes, then return the result."""
    if effort in _EFFORT_ORDER and _EFFORT_ORDER.index(effort) < _EFFORT_ORDER.index(MIN_EFFORT):
        raise ValueError(
            f"effort={effort!r} is not supported for a dataset_building run; "
            f"use {MIN_EFFORT!r} or higher."
        )
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

def _validate_and_clean(output: dict, count: int) -> list[str]:
    """Report thin fields, recover `sources`, and apply Pattern A's row hygiene.

    `_clean` in agent.py drops editorial rows, LinkedIn-only evidence and duplicate
    companies. That logic is just as necessary here, so a Pattern B result is coerced
    into a ScreeningResult and run through it. `required` in an output_schema is a
    strong hint rather than a guarantee, so everything is checked rather than trusted.
    """
    warnings: list[str] = []
    content = output.get("content")
    if not isinstance(content, dict):
        return ["no structured content in the result"]
    trust = output.get("trust") if isinstance(output.get("trust"), dict) else {}

    for f in ("thesis", "as_of_date", "inclusion_criteria"):
        if not content.get(f):
            warnings.append(f"missing required field {f!r}")

    cands = content.get("candidates") or []
    for c in cands:
        if isinstance(c, dict) and c.get("evidence_urls"):
            c["evidence_urls"] = _normalize_urls(c["evidence_urls"])
    if not cands:
        warnings.append("no candidates returned")
    elif len(cands) < count / 2:
        warnings.append(
            f"only {len(cands)} candidate{'' if len(cands) == 1 else 's'} for a request "
            f"of ~{count} — likely a degraded run"
        )

    if not content.get("ranked_shortlist"):
        content["ranked_shortlist"] = [
            c.get("company_name") for c in cands if isinstance(c, dict) and c.get("company_name")
        ]
        if content["ranked_shortlist"]:
            warnings.append("ranked_shortlist was empty; rebuilt it from candidates")

    if not any(str(u).startswith("http") for u in (content.get("sources") or [])):
        recovered = [s.get("url") for s in (trust.get("sources") or []) if s.get("url")]
        if recovered:
            content["sources"] = recovered
            warnings.append(f"sources held no URLs; recovered {len(recovered)} from trust.sources")

    # Run Pattern A's hygiene over the rows, tolerating partial candidates.
    try:
        from agent import _clean  # imported lazily: Pattern B needs no LLM provider
        from schema import ScreeningResult

        coerced = dict(content)
        coerced.setdefault("thesis", "")
        coerced.setdefault("as_of_date", "")
        coerced.setdefault("inclusion_criteria", [])
        coerced.setdefault("sources", [])
        rows = []
        for c in cands:
            if not isinstance(c, dict) or not c.get("company_name"):
                continue
            row = dict(c)
            row.setdefault("product_focus", "")
            row.setdefault("target_customer", "")
            row.setdefault("fit_rationale", "")
            if row.get("fit_score") not in ("strong", "moderate", "weak"):
                row["fit_score"] = "moderate"
            row.setdefault("evidence_urls", [])
            rows.append(row)
        coerced["candidates"] = rows
        before = len(rows)
        cleaned = _clean(ScreeningResult.model_validate(coerced))
        content["candidates"] = [c.model_dump() for c in cleaned.candidates]
        content["ranked_shortlist"] = cleaned.ranked_shortlist
        content["excluded"] = [e.model_dump() for e in cleaned.excluded]
        content["sources"] = cleaned.sources
        if len(cleaned.candidates) != before:
            warnings.append(
                f"row hygiene dropped {before - len(cleaned.candidates)} candidate(s) — see `excluded`"
            )
    except Exception as exc:  # never fail a completed run over post-processing
        warnings.append(f"could not apply row hygiene: {type(exc).__name__}: {exc}")
    return warnings

def _print_result(result: dict, count: int = 25) -> None:
    output = result.get("output", {})
    warnings = _validate_and_clean(output, count) if isinstance(output, dict) else []
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
        print("  (the run still succeeded; these fields came back empty or were repaired)")
    trust = output.get("trust") if isinstance(output, dict) else None
    if trust:
        print(f"\n--- trust / citations ---\n{json.dumps(trust, indent=2, default=str)[:4000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("thesis")
    parser.add_argument("--count", type=int, default=25)
    # `use_case="dataset_building"` is rejected by the API below "medium", so "low" is
    # not offered here — passing it always returned a 422.
    parser.add_argument(
        "--effort", default="high",
        choices=["medium", "high", "x-high", "5x-high", "max"],
    )
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--json", metavar="PATH", default=None)
    args = parser.parse_args()

    result = run_research(args.thesis, count=args.count, effort=args.effort, poll_interval=args.poll_interval)
    _print_result(result, count=args.count)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
