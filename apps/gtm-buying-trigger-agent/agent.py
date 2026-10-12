"""
GTM Buying Trigger Agent
========================

Monitors a watchlist of accounts for recent company events that signal a buying
trigger (funding, executive hires, expansion, launches, partnerships, acquisitions,
customer wins) and returns dated, typed, cited triggers plus the events it rejected.
Built two ways on Nimble:

  Pattern A  Search API, your code owns the workflow
             Per account: three news searches (one per trigger family) limited to the
             window. Claude turns each account's results into dated, typed triggers in
             the same shape the agent returns.

  Pattern B  Web Search Agent, Nimble owns the research
             agents.create(...) with goals, sources and an output_schema (reused if it
             exists), then runs.create -> poll -> result.

Both patterns end in post_process(), which guarantees the report shape: one entry per
watchlist account with its triggers nested inside, every event dated inside the window,
one trigger per event, and counts that match.

Setup:
  pip install -r requirements.txt
  cp .env.example .env   # NIMBLE_API_KEY (both), ANTHROPIC_API_KEY (Pattern A)

Run:
  python agent.py                       # Pattern A, then Pattern B
  python agent.py --pattern A
  python agent.py --pattern B
  python agent.py --post-process examples/buying_triggers__pattern_B.json
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from nimble_python import APIError, BadRequestError, Nimble, UnprocessableEntityError

import config
from schema import AccountExtraction

load_dotenv()

MODEL = "claude-sonnet-4-6"  # Claude model for the Pattern A extraction step
OUTPUT_DIR = Path("artifacts")
SLUG = "buying_triggers"


# ===========================================================================
# App-side guarantees, shared by both patterns
# ===========================================================================

def _parse(d: str | None) -> date | None:
    try:
        return date.fromisoformat((d or "").strip()[:10])
    except ValueError:
        return None


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _rank(t: dict) -> tuple:
    """Sort key for the strongest trigger: strength first, then the most recent event."""
    strength = config.STRENGTHS.index(t["strength"]) if t.get("strength") in config.STRENGTHS else len(config.STRENGTHS)
    return strength, -(_parse(t.get("event_date")) or date.min).toordinal()


def post_process(content: dict, start: str | None = None, end: str | None = None) -> tuple[dict, dict]:
    """Guarantee the report shape the CRM step expects (config.OUTPUT_SCHEMA).

    Returns (new_content, report); the input is not modified.
      1. One entry per watchlist account, in watchlist order (entries that share a
         domain are combined; watchlist accounts with no entry get trigger_count 0).
      2. Every trigger has an event_date inside start..end; undated or out-of-window
         triggers move to excluded_events.
      3. One trigger per (trigger_type, headline) within an account.
      4. trigger_count matches the triggers; strongest_trigger names one of them
         (kept when it does, otherwise strength then recency); outreach_angle is kept only
         when it was written for that strongest trigger; triggers sorted newest first.
    """
    c = copy.deepcopy(content)
    start = start or c.get("window_start")
    end = end or c.get("window_end")
    lo, hi = _parse(start), _parse(end)
    report: dict = {"window": [start, end], "moved_out_of_window": [], "duplicate_triggers": [],
                    "combined_account_entries": [], "strongest_trigger_set": [],
              "outreach_angle_dropped": []}
    excluded = list(c.get("excluded_events") or [])

    by_domain: dict[str, list[dict]] = {}
    for entry in c.get("accounts") or []:
        by_domain.setdefault(entry.get("domain", "").lower().removeprefix("www."), []).append(entry)

    names = {a["domain"]: a["name"] for a in config.WATCHLIST}
    order = [a["domain"] for a in config.WATCHLIST] + [d for d in by_domain if d not in names]
    accounts = []
    for dom in order:
        entries = by_domain.get(dom, [])
        if len(entries) > 1:
            report["combined_account_entries"].append({"domain": dom, "entries": len(entries)})
        company = entries[0]["company"] if entries else names[dom]

        kept, seen = [], set()
        for t in [t for e in entries for t in (e.get("triggers") or [])]:
            d = _parse(t.get("event_date"))
            if lo and hi and not (d and lo <= d <= hi):
                why = f"outside window ({t['event_date']})" if d else "no event date"
                excluded.append({"company": company, "headline": t["headline"], "reason": why})
                report["moved_out_of_window"].append({"company": company, "headline": t["headline"],
                                                      "event_date": t["event_date"]})
                continue
            key = (t.get("trigger_type"), _norm(t.get("headline", "")))
            if key in seen:
                report["duplicate_triggers"].append({"company": company, "headline": t["headline"]})
                continue
            seen.add(key)
            kept.append(t)
        kept.sort(key=lambda t: _parse(t.get("event_date")) or date.min, reverse=True)

        headlines = {t["headline"] for t in kept}
        strongest = next((e.get("strongest_trigger") for e in entries
                          if e.get("strongest_trigger") in headlines), None)
        if kept and strongest is None:
            strongest = min(kept, key=_rank)["headline"]
            report["strongest_trigger_set"].append({"company": company, "strongest_trigger": strongest})
        # The agent wrote its angle for its own strongest trigger; drop it if that trigger is gone.
        angle = next((e.get("outreach_angle") for e in entries
                      if e.get("outreach_angle") and e.get("strongest_trigger") == strongest), None)
        if kept and angle is None and any(e.get("outreach_angle") for e in entries):
            report["outreach_angle_dropped"].append({"company": company})

        accounts.append({"company": company, "domain": dom, "trigger_count": len(kept),
                         "strongest_trigger": strongest if kept else None,
                         "outreach_angle": angle if kept else None, "triggers": kept})

    c.update({"window_start": start, "window_end": end, "accounts": accounts,
              "excluded_events": excluded})
    return c, report


# ===========================================================================
# Pattern A: Search API per account -> Claude extraction -> app-side checks
# ===========================================================================

def account_queries(account: dict) -> list[str]:
    return [t.format(**account) for t in config.QUERY_TEMPLATES]


def gather(client: Nimble, account: dict, start: str, log: list) -> list[dict]:
    evidence = []
    for q in account_queries(account):
        params = {"query": q, **config.SEARCH_PARAMS, "start_date": start}
        try:
            resp = client.search(**params)
        except APIError as exc:  # one failed search should not lose the account
            log.append({"account": account["domain"], "params": params, "error": str(exc)})
            print(f"  [{account['name']}] search failed: {exc}")
            continue
        log.append({"account": account["domain"], "params": params, "result_count": len(resp.results)})
        for r in resp.results:
            extra = r.additional_data or {}
            evidence.append({
                "query": q, "title": r.title, "url": r.url,
                "text": r.content or r.description,
                "publish_date": extra.get("publish_date") or extra.get("publish_date_raw"),
                "source": extra.get("source"),
            })
    return evidence


def extract_account(account: dict, evidence: list[dict], start: str, end: str) -> AccountExtraction:
    system = (
        f"You find buying triggers for one account in news search results. Context: "
        f"{config.SELLER_CONTEXT} {config.TRIGGER_DEFINITION}\n\n"
        "Rules:\n"
        f"- The monitoring window is {start} to {end}. Use the date the event happened or was "
        "announced, not the article's publish date. An article published in the window about an "
        "older funding round, launch or hire is not a trigger: put it in excluded_events with the "
        "reason (for example 're-covered round from Nov 2025').\n"
        f"- The account is {account['name']} at {account['domain']}. Ignore results about other "
        "companies with a similar name, and list them in excluded_events as a different company.\n"
        "- Market roundups and listicles are not events. Customer case studies are triggers only "
        "for a large, named customer win.\n"
        "- One row per underlying event, even when several results cover it. Prefer the "
        "company's own page as source_url when it is among the results.\n"
        "- strength: High if the event directly changes go-to-market priorities or budget "
        "(funding, revenue leadership hire, major customer win), Medium for expansion, launches "
        "and partnerships, Low for minor items.\n"
        "- outreach_angle: one sentence using only facts from this account's triggers, or null."
    )
    lines = [f"[{i}] {e['title']}\nURL: {e['url']}\nPublished: {e['publish_date'] or 'unknown'}"
             f"  Source: {e['source'] or 'unknown'}\n{(e['text'] or '')[: config.EVIDENCE_CHARS]}"
             for i, e in enumerate(evidence, 1)]
    user = (f"Account: {account['name']} ({account['domain']})\n\n"
            + ("\n\n".join(lines) or "(no results)"))
    llm = ChatAnthropic(model=MODEL, max_tokens=8000, timeout=600, max_retries=2)
    return llm.with_structured_output(AccountExtraction).invoke([("system", system), ("user", user)])


def run_search_api() -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY
    start, end = config.window()
    print(f"[Pattern A] {len(config.WATCHLIST)} accounts, window {start} to {end}")
    log: list[dict] = []
    raw = {"window_start": start, "window_end": end, "accounts": [], "excluded_events": []}
    evidence_by_account = {}
    for account in config.WATCHLIST:
        evidence = gather(client, account, start, log)
        evidence_by_account[account["domain"]] = evidence
        ex = extract_account(account, evidence, start, end)
        triggers = [t.model_dump() for t in ex.triggers]
        raw["accounts"].append({"company": account["name"], "domain": account["domain"],
                                "trigger_count": len(triggers), "strongest_trigger": None,
                                "outreach_angle": ex.outreach_angle, "triggers": triggers})
        raw["excluded_events"] += [{**e.model_dump(), "company": account["name"]}
                                   for e in ex.excluded_events]
        print(f"  [{account['name']}] {len(evidence)} results -> {len(triggers)} triggers, "
              f"{len(ex.excluded_events)} excluded")

    content, report = post_process(raw, start, end)
    payload = {"model": MODEL, "content": content, "post_processing": report,
               "searches": log, "evidence": evidence_by_account}
    _save(payload, f"{SLUG}__pattern_A.json")
    _print_summary(content, report)
    return payload


# ===========================================================================
# Pattern B: Web Search Agent, then the same app-side checks
# ===========================================================================

def get_or_create_agent(client: Nimble) -> str:
    """Reuse the agent named AGENT_NAME if it exists, else create it. Returns its id.

    A reused agent keeps the goals, sources and schema it was created with. After
    editing them in config.py, change AGENT_NAME or update the agent.
    """
    offset = 0
    while True:
        page = client.agents.list(limit=100, offset=offset)
        for item in page.items:
            if item.agent_name == config.AGENT_NAME:
                print(f"  reusing agent {config.AGENT_NAME} ({item.id})")
                return item.id
        offset += len(page.items)
        if not page.items or offset >= page.total:
            break

    common = dict(agent_name=config.AGENT_NAME, display_name=config.AGENT_DISPLAY_NAME,
                  description=config.AGENT_DESCRIPTION, use_case=config.USE_CASE,
                  effort=config.EFFORT, sources=config.SOURCES, output_schema=config.OUTPUT_SCHEMA)
    try:
        agent = client.agents.create(**common, goals=config.GOALS)
    except (BadRequestError, UnprocessableEntityError) as exc:
        # Fallback: fold the goals into the skill text, the form the API stored them in.
        print(f"  create with goals rejected ({exc.status_code}); folding goals into skill")
        agent = client.agents.create(**common, skill=config.skill_with_goals())
    print(f"  created agent {config.AGENT_NAME} ({agent.id})")
    return agent.id


def run_agent_api(poll_every: int = 30, timeout: int = 2700) -> dict:
    client = Nimble()  # reads NIMBLE_API_KEY
    start, end = config.window()
    print(f"[Pattern B] agent {config.AGENT_NAME} (use_case={config.USE_CASE}, effort={config.EFFORT}), "
          f"window {start} to {end}")
    agent_id = get_or_create_agent(client)

    run = client.agents.runs.create(agent_id, input=config.run_prompt())
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

    payload = client.agents.runs.result(run.id, agent_id=agent_id).model_dump(mode="json")
    trust = payload["output"]["trust"]
    print(f"  trust: {trust['confidence']} ({trust['reasoning']}); {len(trust['sources'])} sources")
    content, report = post_process(payload["output"]["content"], start, end)
    payload["post_processed"] = content
    payload["post_processing"] = report
    _save(payload, f"{SLUG}__pattern_B.json")
    _print_summary(content, report)
    return payload


# --- output ----------------------------------------------------------------------

def _save(payload: dict, name: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / name
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"saved {out}")


def _print_summary(content: dict, report: dict) -> None:
    for a in content["accounts"]:
        print(f"  {a['company']:<14} {a['trigger_count']:>2} triggers  strongest: {a['strongest_trigger']}")
    print(f"  {sum(a['trigger_count'] for a in content['accounts'])} triggers, "
          f"{len(content['excluded_events'])} excluded events; post-processing moved "
          f"{len(report['moved_out_of_window'])} out of window, dropped "
          f"{len(report['duplicate_triggers'])} duplicates")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GTM buying triggers (Pattern A and/or B)")
    parser.add_argument("--pattern", choices=["A", "B", "both"], default="both")
    parser.add_argument("--post-process", metavar="JSON",
                        help="Only run post_process() on a saved Pattern B result (no API calls)")
    args = parser.parse_args()

    if args.post_process:
        saved = json.loads(Path(args.post_process).read_text(encoding="utf-8"))
        content, report = post_process(saved["output"]["content"])
        _print_summary(content, report)
        print(json.dumps(report, indent=2))
    else:
        start, end = config.window()
        print(f"== GTM Buying Trigger Agent ({start} to {end}) ==")
        if args.pattern in ("A", "both"):
            run_search_api()
        if args.pattern in ("B", "both"):
            run_agent_api()
