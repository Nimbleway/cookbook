"""
GTM Account Discovery Agent
===========================

Starts from an ICP and finds the companies that match it, with the evidence for each
criterion and every rejection with the criterion it failed. Built two ways on Nimble:

  Pattern A  Search API, your code owns the workflow
             broaden   6 lite discovery searches limited to the funding window
             extract   Claude pulls candidate companies out of titles and snippets;
                       dedupe() merges them in code
             narrow    one firmographic search per candidate -> LLM judge (HQ, product,
                       size; latest round extracted, stage decided in code) -> a hiring
                       search on ATS boards only for survivors -> LLM judge. Pass/fail is
                       decided in code from the judges' grades.

  Pattern B  Web Search Agent, Nimble owns the research
             nimble.agents.create(...) with the ICP rules as goals and required
             evidence fields in the output_schema (reused if it already exists),
             then runs.create -> poll -> result. A headcount gate checks every
             row's employee_count in code: the agent's own figure plus one Search
             API call, each figure dated and compared with the 50-500 range.

Setup:
  pip install -r requirements.txt
  cp .env.example .env   # NIMBLE_API_KEY (both), ANTHROPIC_API_KEY (both: Pattern B's gate)

Run:
  python agent.py                # Pattern A, then Pattern B
  python agent.py --pattern A
  python agent.py --pattern B
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from nimble_python import APIError, ConflictError, Nimble

load_dotenv()  # before config, which reads AS_OF_DATE at import

import config
from schema import (CandidateList, CriterionCheck, FirmographicVerdict, HeadcountEvidence,
                    HeadcountFigure, HiringVerdict, LatestRound)

MODEL = "claude-sonnet-4-6"  # Claude model for extraction and judging
OUTPUT_DIR = Path("artifacts")
SLUG = "legal_ai_discovery"


# --- shared helpers ----------------------------------------------------------

def _llm(schema):
    llm = ChatAnthropic(model=MODEL, max_tokens=8000, timeout=600, max_retries=2)
    return llm.with_structured_output(schema)


def _icp_text() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in config.ICP_CRITERIA.items())


def _format_results(results) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        text = (getattr(r, "content", None) or getattr(r, "description", None) or "")
        lines.append(f"[{i}] {r.title}\nURL: {r.url}\n{text[: config.EVIDENCE_CHARS]}")
    return "\n\n".join(lines) or "(no results)"


def _search(client: Nimble, log: list, step: str, **params):
    try:
        resp = client.search(**params)
    except APIError as exc:
        log.append({"step": step, "params": params, "error": str(exc)})
        print(f"  [{step}] search failed: {exc}")
        return []
    log.append({"step": step, "params": params, "result_count": len(resp.results)})
    return resp.results


# ===========================================================================
# Pattern A: broaden -> extract + dedupe -> narrow (firmographics, then hiring)
# ===========================================================================

def broaden(client: Nimble, log: list) -> list:
    pages = []
    for p in config.DISCOVERY:
        pages += _search(client, log, "discovery", **p, **config.DISCOVERY_PARAMS)
    print(f"  broaden: {len(config.DISCOVERY)} searches, {len(pages)} results")
    return pages


def extract_companies(pages) -> list[dict]:
    system = (
        "You read search results about legal technology funding and news, and list the "
        "companies they are about: the company raising, launching or hiring, not its "
        "investors, customers or the law firms quoted. If a result explicitly states that "
        "the company is headquartered outside the US, or that it is itself a law firm or "
        "legal services provider, set early_rejection (criterion hq or product) with that "
        "fact. Do not reject on funding stage or on missing information; those are checked "
        f"later.\n\nICP:\n{_icp_text()}"
    )
    out = _llm(CandidateList).invoke([("system", system), ("user", _format_results(pages))])
    return [c.model_dump() for c in out.candidates]


_SUFFIX = re.compile(r"\b(inc|incorporated|llc|ltd|corp|co|technologies|labs|ai)\b\.?", re.I)


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _SUFFIX.sub("", name.lower()))


def dedupe(candidates: list[dict]) -> list[dict]:
    """One entry per company, keyed on domain when known, else on a normalized name."""
    merged: dict[str, dict] = {}
    by_name: dict[str, str] = {}
    for c in candidates:
        nk = _name_key(c["name"]) or c["name"].lower()
        key = (c.get("domain") or "").lower() or by_name.get(nk) or nk
        by_name.setdefault(nk, key)
        if key not in merged:
            merged[key] = {**c, "evidence_urls": [c["evidence_url"]]}
            continue
        m = merged[key]
        m["domain"] = m.get("domain") or c.get("domain")
        m["early_rejection"] = m.get("early_rejection") or c.get("early_rejection")
        if c["evidence_url"] not in m["evidence_urls"]:
            m["evidence_urls"].append(c["evidence_url"])
    return list(merged.values())


def judge_firmographics(c: dict, results) -> FirmographicVerdict:
    system = (
        "Grade one company against the hq, product and size ICP criteria using only the "
        "search results. met / not_met need explicit evidence in a result; otherwise "
        "unclear. Check that each result is about this company and not another with a "
        "similar name. For size, use a dated headcount figure; never infer it from funding. "
        "Do not grade funding stage: fill latest_round with the series and close date of "
        "the most recent priced round exactly as the results state them.\n\n"
        f"ICP:\n{_icp_text()}\n\nToday's date is {config.AS_OF}."
    )
    user = f"Company: {c['name']} ({c.get('domain') or 'domain unknown'})\n\n{_format_results(results)}"
    return _llm(FirmographicVerdict).invoke([("system", system), ("user", user)])


def judge_hiring(c: dict, results) -> HiringVerdict:
    system = (
        "Decide whether this company has an open, US-located, quota-carrying sales role "
        "(Account Executive, SDR/BDR or sales leadership) using only the search results. "
        "met needs a posting for this company on its careers page or an ATS board; give its "
        "URL. Customer success, solutions engineering and marketing roles do not count."
    )
    user = f"Company: {c['name']} ({c.get('domain') or 'domain unknown'})\n\n{_format_results(results)}"
    return _llm(HiringVerdict).invoke([("system", system), ("user", user)])


def stage_check(r: LatestRound) -> CriterionCheck:
    """The stage criterion, decided in code: Series A, B or C closed on or after ROUND_WINDOW_START."""
    start = date.fromisoformat(config.ROUND_WINDOW_START)
    if r.series in ("series_a", "series_b", "series_c"):
        closed = _parse_date(r.close_date)
        if closed is None:
            return CriterionCheck(status="unclear", evidence=f"{r.evidence} (no close date)", source_url=r.source_url)
        status = "met" if closed >= start else "not_met"
        return CriterionCheck(status=status, evidence=f"{r.evidence} (closed {r.close_date})", source_url=r.source_url)
    if r.series in ("unknown", "other"):
        return CriterionCheck(status="unclear", evidence=r.evidence, source_url=r.source_url)
    return CriterionCheck(status="not_met", evidence=r.evidence, source_url=r.source_url)


def firmographic_decision(v: FirmographicVerdict) -> tuple[str, str] | None:
    """Hard constraints: anything not explicitly met fails. Returns (criterion, reason) or None."""
    for name in config.FIRMOGRAPHIC_CRITERIA:
        check = stage_check(v.latest_round) if name == "stage" else getattr(v, name)
        if check.status != "met":
            prefix = "Unverified: " if check.status == "unclear" else ""
            return name, f"{prefix}{check.evidence}"
    return None


def hiring_decision(v: HiringVerdict) -> tuple[str, str] | None:
    if v.status == "met" and v.posting_url:
        return None
    prefix = "Unverified: " if v.status != "not_met" else ""
    return "sales_hiring", f"{prefix}{v.evidence}"


def verify(client: Nimble, c: dict, log: list) -> dict:
    firmo_q = dict(config.FIRMOGRAPHIC_SEARCH)
    firmo_q["query"] = " ".join(firmo_q["query"].format(name=c["name"], domain=c.get("domain") or "").split())
    firmo = judge_firmographics(c, _search(client, log, f"firmographics:{c['name']}", **firmo_q))
    c["domain"] = c.get("domain") or firmo.domain
    record = {"company": c["name"], "domain": c.get("domain"), "evidence_urls": c["evidence_urls"],
              "firmographics": {**firmo.model_dump(), "stage": stage_check(firmo.latest_round).model_dump()}}
    failed = firmographic_decision(firmo)
    if failed:
        return {**record, "pass": False, "stage": "firmographics",
                "failed_criterion": failed[0], "reason": failed[1]}

    hiring_q = dict(config.HIRING_SEARCH)
    hiring_q["query"] = hiring_q["query"].format(name=c["name"])
    hiring_q["include_domains"] = config.ATS + ([c["domain"]] if c.get("domain") else [])
    hiring = judge_hiring(c, _search(client, log, f"hiring:{c['name']}", **hiring_q))
    record["hiring"] = hiring.model_dump()
    failed = hiring_decision(hiring)
    if failed:
        return {**record, "pass": False, "stage": "hiring",
                "failed_criterion": failed[0], "reason": failed[1]}
    return {**record, "pass": True}


def run_search_api() -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY
    log: list[dict] = []
    print("[Pattern A] broaden -> extract -> narrow")

    pages = broaden(client, log)
    candidates = dedupe(extract_companies(pages))
    early = [c for c in candidates if c.get("early_rejection")]
    to_verify = [c for c in candidates if not c.get("early_rejection")]
    print(f"  extract: {len(candidates)} unique companies, {len(early)} rejected from discovery evidence")

    results = [verify(client, c, log) for c in to_verify]
    qualified = [r for r in results if r["pass"]]
    rejected = [
        {"company": c["name"], "domain": c.get("domain"), "stage": "discovery",
         "failed_criterion": c["early_rejection"]["criterion"],
         "reason": c["early_rejection"]["reason"], "evidence_urls": c["evidence_urls"]}
        for c in early
    ] + [r for r in results if not r["pass"]]

    by_reason: dict[str, int] = {}
    for r in rejected:
        by_reason[r["failed_criterion"]] = by_reason.get(r["failed_criterion"], 0) + 1

    payload = {
        "as_of": config.AS_OF,
        "model": MODEL,
        "icp": config.ICP_CRITERIA,
        "counts": {"searches": len(log), "discovery_results": len(pages),
                   "unique_candidates": len(candidates), "researched": len(to_verify),
                   "qualified": len(qualified), "rejected": len(rejected),
                   "rejected_by_criterion": by_reason},
        "qualified": qualified,
        "rejected": rejected,
        "searches": log,
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{SLUG}__pattern_A.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print(f"  qualified ({len(qualified)}): {', '.join(q['company'] for q in qualified) or 'none'}")
    print(f"  rejected ({len(rejected)}) by criterion: {by_reason}")
    print(f"saved {out}")
    return payload


# ===========================================================================
# Pattern B: Web Search Agent + headcount gate on every row
# ===========================================================================

def get_or_create_agent(client: Nimble) -> str:
    """Reuse the agent if one with AGENT_NAME exists, else create it. Returns its id.

    A reused agent keeps the goals, sources and schema it was created with. After
    editing them in config.py, change AGENT_NAME or update the agent.
    """
    def find() -> str | None:
        offset = 0
        while True:
            page = client.agents.list(limit=100, offset=offset)
            for item in page.items:
                if item.agent_name == config.AGENT_NAME:
                    return item.id
            offset += len(page.items)
            if not page.items or offset >= page.total:
                return None

    agent_id = find()
    if agent_id:
        print(f"  reusing agent {config.AGENT_NAME} ({agent_id})")
        return agent_id
    try:
        agent = client.agents.create(
            agent_name=config.AGENT_NAME,
            display_name=config.AGENT_DISPLAY_NAME,
            description=config.AGENT_DESCRIPTION,
            use_case=config.USE_CASE,
            effort=config.EFFORT,
            goals=config.GOALS,
            sources=config.SOURCES,
            output_schema=config.OUTPUT_SCHEMA,
        )
    except ConflictError:  # created elsewhere between list and create
        agent_id = find()
        if not agent_id:
            raise
        return agent_id
    print(f"  created agent {config.AGENT_NAME} ({agent.id})")
    return agent.id


def judge_headcount(row: dict, results) -> HeadcountEvidence:
    system = (
        "List every employee headcount figure the evidence gives for this company: the Web "
        "Search Agent's own claim and the search results. Use only figures about this "
        "company. Record the source and the date the source gives for the figure; leave "
        "as_of null when the evidence does not date it. Do not estimate headcount from "
        "funding or job counts."
    )
    claim = row.get("employee_count") or "(none)"
    user = (f"Company: {row.get('company')} ({row.get('domain')})\n\n"
            f"[agent] Web Search Agent's employee_count claim: {claim}\n\n{_format_results(results)}")
    return _llm(HeadcountEvidence).invoke([("system", system), ("user", user)])


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            return datetime.strptime(s.strip()[:n], fmt).date()
        except ValueError:
            continue
    return None


def headcount_gate(figures: list[HeadcountFigure]) -> tuple[str, str]:
    """Your rule for the employee_count criterion. Returns (status, reason).

    Only dated figures from the last HEADCOUNT_MAX_AGE_DAYS count.
      pass    every recent figure falls inside MIN..MAX
      fail    no recent dated figure, or none inside MIN..MAX
      review  recent figures disagree about the band
    """
    cutoff = date.fromisoformat(config.AS_OF) - timedelta(days=config.HEADCOUNT_MAX_AGE_DAYS)
    recent = [f for f in figures if (d := _parse_date(f.as_of)) and d >= cutoff]
    if not recent:
        return "fail", "Unverified: no dated headcount figure found"
    desc = "; ".join(f"{f.low if f.low == f.high else f'{f.low}-{f.high}'} ({f.source}, {f.as_of})" for f in recent)
    inside = [config.MIN_EMPLOYEES <= f.low and f.high <= config.MAX_EMPLOYEES for f in recent]
    if all(inside):
        return "pass", desc
    if not any(inside):
        return "fail", desc
    return "review", desc


def run_agent_api(poll_every: int = 30, timeout: int = 2700) -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY
    print(f"[Pattern B] agent {config.AGENT_NAME} (use_case={config.USE_CASE}, effort={config.EFFORT})")
    agent_id = get_or_create_agent(client)

    run = client.agents.runs.create(agent_id, input=config.agent_input())
    print(f"  run {run.id} started; polling every {poll_every}s ...")
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
    rows = payload["output"]["content"]["companies"]
    claims = payload["output"]["trust"]["claims"]
    print(f"  {len(rows)} companies, {len(payload['output']['content']['near_misses'])} near-misses; "
          f"trust: {payload['output']['trust']['confidence']}")

    # Headcount gate: the size criterion is decided in code for every row, whether or not
    # the agent cited its figure. The agent's own claim and one Search API call supply
    # the figures; headcount_gate() keeps the recent dated ones and checks the range.
    confidence = {c["path"]: c["confidence"] for c in claims}
    log: list[dict] = []
    gate = []
    for i, row in enumerate(rows):
        # Drop a parenthetical legal name ("GC AI (General Counsel AI, Inc.)") from the query.
        name = re.sub(r"\s*\(.*?\)", "", row["company"]).strip()
        q = dict(config.HEADCOUNT_SEARCH)
        q["query"] = q["query"].format(company=name, domain=row.get("domain", ""))
        found = judge_headcount(row, _search(client, log, f"headcount:{row['company']}", **q))
        status, reason = headcount_gate(found.figures)
        gate.append({"company": row["company"], "agent_claim": row.get("employee_count"),
                     "agent_claim_confidence": confidence.get(f"$.companies[{i}].employee_count"),
                     "query": q["query"], "status": status, "reason": reason,
                     "figures": [f.model_dump() for f in found.figures]})
        print(f"  gate {row['company']}: {status} ({reason})")

    payload["trust_gate"] = gate
    payload["verified_companies"] = [r["company"] for r, g in zip(rows, gate) if g["status"] == "pass"]
    payload["gate_searches"] = log

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{SLUG}__pattern_B.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  verified: {', '.join(payload['verified_companies']) or 'none'}")
    print(f"saved {out}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GTM account discovery (Pattern A and/or B)")
    parser.add_argument("--pattern", choices=["A", "B", "both"], default="both")
    args = parser.parse_args()

    print(f"== GTM Account Discovery (as of {config.AS_OF}) ==")
    if args.pattern in ("A", "both"):
        run_search_api()
    if args.pattern in ("B", "both"):
        run_agent_api()
