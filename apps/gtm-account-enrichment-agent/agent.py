"""
GTM Account Enrichment Agent
============================

Turns a CRM account (a company name and a domain) into a current company profile:
product, customers, location, size, funding, leadership, hiring and recent
changes. Built two ways on Nimble:

  Pattern A  Search API, your code owns the workflow
             Five focused nimble.search passes (identity, funding, leadership,
             hiring, signals), each with its own sources and depth. Claude (via
             langchain-anthropic) extracts the evidence into a fixed profile and
             keeps every disagreeing value with its source. resolve_conflicts()
             then applies your precedence rules (config.SOURCE_TIERS).

  Pattern B  Web Search Agent, Nimble owns the research
             nimble.agents.run(use_case="enrichment") with the CRM record as
             input_data and an output_schema. Poll until the run finishes, then
             save the profile plus its per-field trust block.

Setup:
  pip install -r requirements.txt
  cp .env.example .env   # NIMBLE_API_KEY (both), ANTHROPIC_API_KEY (Pattern A)

Run:
  python agent.py                # Pattern A, then Pattern B
  python agent.py --pattern A
  python agent.py --pattern B --effort medium
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from nimble_python import APIError, Nimble

import config
from schema import AccountProfile

load_dotenv()

MODEL = "claude-sonnet-4-6"  # Claude model for the Pattern A extraction step
OUTPUT_DIR = Path("artifacts")
SLUG = config.DOMAIN.replace(".", "_")


# ===========================================================================
# Pattern A: Search API passes -> LLM extraction -> your precedence rules
# ===========================================================================

def gather_evidence(client: Nimble) -> tuple[dict, list]:
    """Run one search per attribute group. Returns (evidence, search_log)."""
    evidence: dict[str, list[dict]] = {}
    search_log: list[dict] = []
    for group, params in config.PASSES.items():
        try:
            resp = client.search(**params)
        except APIError as exc:  # one failed pass should not lose the others
            print(f"  [{group}] search failed: {exc}")
            evidence[group] = []
            search_log.append({"group": group, "params": params, "error": str(exc)})
            continue
        # With search_depth="standard" the page text can come back in `description`
        # while `content` is empty, so read whichever is set.
        evidence[group] = [
            {"url": r.url, "title": r.title, "text": r.content or r.description}
            for r in resp.results
        ]
        search_log.append({"group": group, "params": params, "result_count": len(resp.results)})
        print(f"  [{group}] {len(resp.results)} results")
    return evidence, search_log


def _format_evidence(evidence: dict) -> str:
    blocks = []
    for group, results in evidence.items():
        blocks.append(f"## {group}")
        for i, r in enumerate(results, 1):
            text = (r["text"] or "")[: config.EVIDENCE_CHARS]
            blocks.append(f"[{group}-{i}] {r['title']}\nURL: {r['url']}\n{text}")
    return "\n\n".join(blocks)


EXTRACTION_PROMPT = f"""\
You turn web search evidence about one company into a CRM account profile.

Rules:
- Use only the evidence below. Do not add facts from memory.
- The company is identified by its domain, not its name. Ignore results about other
  companies with a similar name.
- For every field you fill, add a field_sources entry with the URL of the result that
  supports it.
- When two or more results state different values for the same field (for example
  headquarters, employee_count, customer_count, founded_year), do NOT choose one.
  Leave that field null and add a conflicts entry listing every value with its
  source_url and as_of date. The application applies its own precedence rules.
- currently_hiring is "Yes" only if the evidence shows open postings.
- recent_signals: dated announcements (launches, funding, hires, partnerships,
  customer milestones), newest first.
- Leave a field null rather than guess.

Today's date is {date.today().isoformat()}."""


def extract_profile(domain: str, evidence: dict) -> AccountProfile:
    """LLM extraction step: evidence -> AccountProfile (conflicts kept, not resolved)."""
    llm = ChatAnthropic(model=MODEL, max_tokens=8000, timeout=600, max_retries=2)
    extractor = llm.with_structured_output(AccountProfile)
    user = (
        f"Company: {config.COMPANY_NAME}\nDomain: {domain}\n\n"
        f"Evidence, grouped by search pass:\n\n{_format_evidence(evidence)}"
    )
    return extractor.invoke([("system", EXTRACTION_PROMPT), ("user", user)])


def _tier(url: str) -> tuple[int, str]:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    names = [name for name, _ in config.SOURCE_TIERS]
    for rank, (name, domains) in enumerate(config.SOURCE_TIERS):
        if any(host == d or host.endswith("." + d) for d in domains):
            return rank, name
    return names.index("other"), "other"


def _date_key(as_of: str | None) -> str:
    """Sortable date string; unknown dates sort oldest."""
    return (as_of or "").strip()[:10]


def _coerce(field: str, value: str):
    if field == "founded_year":
        m = re.search(r"\b(19|20)\d{2}\b", value)
        return int(m.group(0)) if m else None
    if field == "total_funding_usd":
        m = re.search(r"([\d.,]+)\s*([MBK]?)", value.replace("$", ""), re.I)
        if not m:
            return None
        n = float(m.group(1).replace(",", ""))
        return n * {"K": 1e3, "M": 1e6, "B": 1e9}.get(m.group(2).upper(), 1)
    return value


def resolve_conflicts(profile: AccountProfile) -> AccountProfile:
    """Apply your precedence rules to every recorded conflict.

    FRESHEST_WINS fields: most recent dated value first, source tier breaks ties.
    Every other field: most trusted source tier first, recency breaks ties.
    The losing values stay in `conflicts` so the CRM keeps the full picture.
    """
    for c in profile.conflicts:
        if not c.values or not hasattr(profile, c.field):
            continue
        by_date = lambda v: _date_key(v.as_of)
        by_tier = lambda v: _tier(v.source_url)[0]
        # Two stable sorts: the second key decides, the first breaks ties.
        if c.field in config.FRESHEST_WINS:
            ranked = sorted(sorted(c.values, key=by_tier), key=by_date, reverse=True)
            rule = "most recent dated value, then source tier"
        else:
            ranked = sorted(sorted(c.values, key=by_date, reverse=True), key=by_tier)
            rule = "most trusted source tier, then most recent"
        best = ranked[0]
        value = _coerce(c.field, best.value)
        c.chosen = best.value
        c.rule = f"{rule} ({_tier(best.source_url)[1]}: {best.source_url})"
        if value is not None:
            setattr(profile, c.field, value)
    return profile


def run_search_api() -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY
    print(f"[Pattern A] enriching {config.DOMAIN} with {len(config.PASSES)} search passes")
    evidence, search_log = gather_evidence(client)
    profile = resolve_conflicts(extract_profile(config.DOMAIN, evidence))

    payload = {
        "as_of": date.today().isoformat(),
        "domain": config.DOMAIN,
        "model": MODEL,
        "searches": search_log,
        "profile": profile.model_dump(),
        "evidence": evidence,
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{SLUG}_enrichment__pattern_A.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    for c in profile.conflicts:
        print(f"  conflict on {c.field}: {len(c.values)} values -> {c.chosen!r}")
    print(f"saved {out}")
    return payload


# ===========================================================================
# Pattern B: Web Search Agent (Nimble does the research)
# ===========================================================================

def run_agent_api(effort: str = config.EFFORT, poll_every: int = 15, timeout: int = 1800) -> dict:
    """Start an enrichment run, poll until it finishes, save content + trust."""
    client = Nimble()  # reads NIMBLE_API_KEY

    run = client.agents.run(
        agent_name=config.AGENT_NAME,
        use_case=config.USE_CASE,
        effort=effort,
        input=config.AGENT_INPUT,
        input_data=config.INPUT_DATA,
        output_schema=config.PROFILE_OUTPUT_SCHEMA,
    )
    agent_id = run.web_search_agent_id
    print(f"[Pattern B] run {run.id} on agent {agent_id} (effort={effort}); polling ...")

    deadline = time.time() + timeout
    while True:
        state = client.agents.runs.get(run.id, agent_id=agent_id)
        if not state.is_active:
            break
        if time.time() > deadline:
            raise TimeoutError(f"run {run.id} still {state.status} after {timeout}s")
        time.sleep(poll_every)
    if state.status != "completed":
        raise RuntimeError(f"run {run.id} ended as {state.status}: {state.error}")

    result = client.agents.runs.result(run.id, agent_id=agent_id)
    payload = result.model_dump(mode="json")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{SLUG}_enrichment__pattern_B.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    output = payload.get("output") or {}
    content = output.get("content") or {}
    trust = output.get("trust") or {}
    counts: dict[str, int] = {}
    for claim in trust.get("claims", []):
        counts[claim["confidence"]] = counts.get(claim["confidence"], 0) + 1
    print(f"  overall trust: {trust.get('confidence')} ({trust.get('reasoning')})")
    print(f"  claims by confidence: {counts}; sources: {len(trust.get('sources', []))}")
    for c in content.get("data_conflicts") or []:
        print(f"  conflict on {c['field']}: {c['resolution']}")
    print(f"saved {out}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GTM account enrichment (Pattern A and/or B)")
    parser.add_argument("--pattern", choices=["A", "B", "both"], default="both")
    parser.add_argument("--effort", default=config.EFFORT,
                        choices=["low", "medium", "high", "x-high", "max"],
                        help="Web Search Agent effort for Pattern B")
    args = parser.parse_args()

    print(f"== GTM Account Enrichment: {config.DOMAIN} ==")
    if args.pattern in ("A", "both"):
        run_search_api()
    if args.pattern in ("B", "both"):
        run_agent_api(effort=args.effort)
