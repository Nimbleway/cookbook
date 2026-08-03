#!/usr/bin/env python3
"""LangChain Gap Filler — fill the blanks in a CSV, and say where every answer came from.

One process, three tiers:

  1. already in your file  — free, never re-fetched
  2. Nimble Search         — seconds, via the LangChain agent's own tool choice
  3. Web Search Agent run  — minutes, cited, only for what tier 2 could not resolve

Every filled cell carries <col>__source, <col>__confidence and <col>__tier.

Usage
-----
  .venv/bin/python fill_gaps.py                          # cached demo, no API calls
  USE_LIVE=true .venv/bin/python fill_gaps.py            # live
  USE_LIVE=true .venv/bin/python fill_gaps.py --input my.csv --key-column company
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
RUNS = DATA / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

BASE = "https://sdk.nimbleway.com/v1"
KEY = os.getenv("NIMBLE_API_KEY", "")
H = {"Authorization": f"Bearer {KEY}"}
PH = {**H, "Content-Type": "application/json-patch+json"}
USE_LIVE = os.getenv("USE_LIVE", "false").lower() == "true"

# Nimble's own templates only exercise high/max; low/medium look under-used.
EFFORT = "high"
MODEL = "claude-sonnet-4-6"          # not opus: opus rejects temperature, and sonnet is enough here
POLL_SECONDS = 15
STATE = DATA / "run_state.json"      # resumable: chunk -> run_id

DOMAIN_EXPERTISE = """You are a company-data analyst filling gaps in an existing dataset.
Inputs may be a company name, a domain, a ticker, or a partially-filled row - accept all four.
Prefer the company's own website, newsroom, investor-relations pages and official filings; use
directories and press only when the primary source is silent. If a value cannot be confirmed from a
source you actually retrieved, return null - never infer, never estimate, and never carry a value
over from a similarly-named company. Distinguish "not found" from "confirmed absent" in notes.
"""

GOALS = [
    "Skips re-fetching any field already populated in the input row",
    "Returns one row per input entity, in input order, even when nothing could be filled",
    "Populates source_url and data_as_of_date for every non-null value",
    "Returns null rather than an inferred or estimated value",
    "Matches the exact entity requested - never a similarly-named company",
]

# Empty `domains` = category hint, not a host restriction. This is what stops the agent being
# boxed into a whitelist that cannot answer the question (see the lead-enrichment template).
SOURCES = {
    "allow": [
        {"title": "Company official website, newsroom and investor relations",
         "domains": [], "order": 0},
        {"title": "SEC EDGAR", "domains": ["sec.gov", "www.sec.gov"], "order": 1},
        {"title": "Crunchbase", "domains": ["crunchbase.com", "www.crunchbase.com"], "order": 2},
        {"title": "LinkedIn", "domains": ["linkedin.com", "www.linkedin.com"], "order": 3},
    ],
    "block": [],
}


def log(msg: str) -> None:
    print(msg, flush=True)


def tier_line(entity: str, col: str, tier: str, elapsed: float, conf: str | None) -> None:
    """The transcript IS the artifact — no dashboard. Make the escalation legible."""
    badge = {"file": "1 file ", "search": "2 search", "agent": "3 agent"}[tier]
    log(f"  {entity[:18]:<18} {col:<16} tier {badge}  {elapsed:5.1f}s  {conf or '-'}")


# ---------------------------------------------------------------- schema from the user's header
def build_schema(columns: list[str], key_column: str) -> dict:
    """Column names go through verbatim — renaming breaks the join back to the user's file."""
    props = {c: {"type": ["string", "null"]} for c in columns}
    props[key_column] = {"type": "string"}
    props |= {
        "source_url": {"type": ["string", "null"]},
        "data_as_of_date": {"type": ["string", "null"]},
        "notes": {"type": ["string", "null"]},
    }
    return {
        "type": "array",
        "items": {"type": "object", "required": [key_column], "properties": props,
                  "additionalProperties": True},
    }


# ---------------------------------------------------------------- agent lifecycle
def ensure_agent(initial_schema: dict) -> str:
    """Create the custom enrichment agent, or reuse the one recorded locally.

    NOT a template clone: `lead-enrichment` is hardcoded to one company (Acme United), so cloning
    it inherits a whitelist that cannot answer questions about anything else.

    `output_schema` is REQUIRED at create time when use_case is enrichment (HTTP 422
    web_search_agent_output_schema_required otherwise). It is only a baseline — each run overrides
    it with the schema derived from that file's header.
    """
    marker = DATA / "agent.json"
    if marker.exists():
        aid = json.loads(marker.read_text())["id"]
        log(f"reusing agent {aid}")
        return aid

    body = {
        "display_name": "LangChain Gap Filler",
        "description": "Fills missing fields in an existing company list, with provenance.",
        "use_case": "enrichment",
        "effort": EFFORT,                 # explicit: the spec default is a buggy use_case value
        "domain_expertise": DOMAIN_EXPERTISE,
        "goals": GOALS,
        "sources": SOURCES,
        "output_schema": initial_schema,   # required for enrichment; per-run override still applies
    }
    r = requests.post(f"{BASE}/task-agents", headers=H, timeout=60, json=body)
    r.raise_for_status()
    agent = r.json()
    aid = agent["id"]

    # Creating with an inline body may still not persist goals/sources (cf. Quirk 6 on clones).
    # Verify, and PATCH if the server dropped them.
    got = requests.get(f"{BASE}/task-agents/{aid}", headers=H, timeout=60).json()
    if not got.get("goals") or not (got.get("sources") or {}).get("allow"):
        log("  goals/sources absent after create — PATCHing (Quirk 6)")
        requests.patch(f"{BASE}/task-agents/{aid}", headers=PH, timeout=60, json=[
            {"op": "replace", "path": "/goals", "value": GOALS},
            {"op": "replace", "path": "/sources", "value": SOURCES},
        ]).raise_for_status()
        got = requests.get(f"{BASE}/task-agents/{aid}", headers=H, timeout=60).json()

    assert got.get("goals"), "goals did not persist"
    assert (got.get("sources") or {}).get("allow"), "sources did not persist"
    marker.write_text(json.dumps(got, indent=1))
    log(f"created agent {aid} (goals={len(got['goals'])}, "
        f"source groups={len(got['sources']['allow'])})")
    return aid


def start_run(aid: str, prompt: str, schema: dict) -> str:
    r = requests.post(f"{BASE}/task-agents/{aid}/runs", headers=H, timeout=60,
                      json={"input": prompt, "output_schema": schema})
    r.raise_for_status()
    return r.json()["id"]


def collect_run(aid: str, rid: str) -> dict | None:
    """Poll to terminal state, then fetch. 408 means still active — never an error."""
    t0 = time.time()
    while True:
        run = requests.get(f"{BASE}/task-agents/{aid}/runs/{rid}", headers=H, timeout=60).json()
        if not run["is_active"]:
            break
        if time.time() - t0 > 1800:
            log(f"  run {rid} exceeded 30 min — cancelling")
            requests.post(f"{BASE}/task-agents/{aid}/runs/{rid}/cancel", headers=H, timeout=60)
            return None
        time.sleep(POLL_SECONDS)

    res = requests.get(f"{BASE}/task-agents/{aid}/runs/{rid}/result", headers=H, timeout=60)
    (RUNS / f"{rid}.json").write_text(json.dumps(res.json(), indent=1))   # raw BEFORE transform
    if run["status"] != "completed":
        log(f"  run {rid} {run['status']}: {(run.get('error') or {}).get('message', '')[:80]}")
        return None
    return res.json()


# ---------------------------------------------------------------- trust -> cells
def index_trust(trust: dict) -> dict[tuple[int, str], dict]:
    """Map trust.claims[].path ($[3].employee_count) -> {confidence, url, excerpt}."""
    out: dict[tuple[int, str], dict] = {}
    for c in trust.get("claims") or []:
        p = c.get("path") or ""
        if not (p.startswith("$[") and "]." in p):
            continue
        try:
            idx = int(p[2:p.index("]")])
        except ValueError:
            continue
        col = p.split(".")[-1]
        cite = (c.get("citations") or [{}])[0]
        out[(idx, col)] = {
            "confidence": c.get("confidence"),
            "url": cite.get("url"),
            "excerpt": (cite.get("excerpts") or [""])[0][:200],
        }
    return out


# ---------------------------------------------------------------- tier 2 (model-routed)
def tier2_fill(rows: list[dict], blanks: dict[str, list[str]], key_column: str,
               governed: set[str]) -> dict:
    """Let the LangChain agent try cheap lookups first. It chooses whether to call nimble_search.

    Deliberately NOT using create_agent's response_format — it triggers a prefill error. The agent
    returns prose; a separate structured call normalises it.
    """
    from langchain.agents import create_agent
    from langchain_anthropic import ChatAnthropic
    from langchain_nimble import NimbleToolkit

    # include_web_search_agents stays False here: tier 2 is search-only by construction.
    # nimble_api_key is a required field on the toolkit — not picked up implicitly.
    toolkit = NimbleToolkit(nimble_api_key=KEY, include_search=True, include_extract=False)
    model = ChatAnthropic(model=MODEL)          # no temperature: some models reject it
    agent = create_agent(model=model, tools=toolkit.get_tools(), system_prompt=(
        "You fill gaps in a company dataset. For each company you are given the fields already "
        "known and the fields missing. Use nimble_search for facts you can confirm in one or two "
        "quick lookups (website, headquarters). Do NOT guess employee counts, funding stages or "
        "amounts raised unless a search result states them plainly — leave those for deeper "
        "research. Never re-state a field that was already provided. Report only what you "
        "confirmed, and name the source URL for each."))

    filled: dict = {}
    for i, row in enumerate(rows):
        # Governed columns are withheld from tier 2 in CODE, not asked for in the prompt.
        # nimble_search accepts no domain filter, so tier-2 sources cannot be restricted to the
        # agent's allow list — and the model demonstrably ignores "do not fill X" instructions.
        missing = [c for c in blanks[row[key_column]] if c not in governed]
        if not missing:
            continue
        known = {k: v for k, v in row.items() if v}
        t0 = time.time()
        try:
            msg = agent.invoke({"messages": [{"role": "user", "content": (
                f"Company: {row[key_column]}\nAlready known (do not re-fetch): "
                f"{json.dumps(known)}\nMissing: {', '.join(missing)}")}]})
            text = msg["messages"][-1].content
            if isinstance(text, list):
                text = " ".join(b.get("text", "") for b in text if isinstance(b, dict))
        except Exception as e:                                    # noqa: BLE001
            log(f"  {row[key_column]}: tier 2 failed ({type(e).__name__}) — escalating all")
            continue

        norm = _normalise(text, row[key_column], missing)
        src = norm.get("__source")
        for col, val in norm.items():
            if col.startswith("__") or not val:
                continue
            # Tier 2 has NO graded trust data — nimble_search returns results, not per-claim
            # confidence. Calling it "medium" would invent a signal the design promises is real.
            # Label it honestly; only tier 3 confidence comes from trust.claims.
            filled[(i, col)] = {"value": val, "tier": "search", "source": src,
                                "confidence": "unverified"}
            tier_line(row[key_column], col, "search", time.time() - t0, "unverified")
    return filled


def _normalise(text: str, entity: str, missing: list[str]) -> dict:
    """Structured output on a plain model (safe) rather than on the agent (prefill error)."""
    from langchain_anthropic import ChatAnthropic
    schema = {"title": "Findings", "type": "object", "properties": {
        **{c: {"type": ["string", "null"]} for c in missing},
        "__source": {"type": ["string", "null"]}}}
    try:
        m = ChatAnthropic(model=MODEL).with_structured_output(schema)
        return m.invoke(f"Extract only values explicitly confirmed for {entity}. "
                        f"Use null for anything uncertain.\n\n{text}") or {}
    except Exception:                                             # noqa: BLE001
        return {}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DATA / "sample_accounts.csv"))
    ap.add_argument("--output", default=str(DATA / "filled.csv"))
    ap.add_argument("--key-column", default="company")
    ap.add_argument("--chunk", type=int, default=10)
    ap.add_argument("--governed", default="employee_count,funding_stage,total_raised",
                    help="Columns that MUST come from a cited tier-3 run, never tier-2 search. "
                         "nimble_search has no domain filter, so tier-2 sources are ungoverned.")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input, newline="", encoding="utf-8")))
    if not rows:
        log("empty input"); return 1
    columns = list(rows[0].keys())
    key = args.key_column
    blanks = {r[key]: [c for c in columns if c != key and not (r.get(c) or "").strip()]
              for r in rows}

    governed = {c.strip() for c in args.governed.split(",") if c.strip()} & set(columns)
    total_blanks = sum(len(v) for v in blanks.values())
    log(f"{len(rows)} rows, {total_blanks} blank cells, {len(columns) - 1} fillable columns")
    if governed:
        log(f"governed (tier 3 only): {', '.join(sorted(governed))}")
    log(f"mode: {'LIVE' if USE_LIVE else 'CACHED (set USE_LIVE=true for live)'}")
    if os.getenv("LANGSMITH_API_KEY"):
        log("LangSmith tracing: on")
    log("")

    if not USE_LIVE:
        cached = DATA / "sample_filled.json"
        if not cached.exists():
            log("no cached fixture yet — run once with USE_LIVE=true to create it")
            return 1
        payload = json.loads(cached.read_text())
        _write(payload["rows"], payload["columns"], payload["meta"], args.output, key)
        log(f"replayed cached result -> {args.output}")
        return 0

    if not KEY:
        log("NIMBLE_API_KEY not set"); return 1

    aid = ensure_agent(build_schema(columns, key))
    log("")
    # Tier 2 needs a model provider to do the routing. Without one, degrade cleanly rather than
    # crashing: every blank escalates to tier 3, which needs only NIMBLE_API_KEY.
    if os.getenv("ANTHROPIC_API_KEY"):
        log(f"TIER 2 — cheap lookups (model chooses; {len(governed)} governed columns withheld)")
        filled = tier2_fill(rows, blanks, key, governed)
    else:
        log("TIER 2 — SKIPPED: no ANTHROPIC_API_KEY. Every blank escalates to tier 3.")
        log("         (set it to enable cheap search-first routing and cut tier-3 spend)")
        filled = {}

    # Anything tier 2 did not resolve escalates. Deterministic, so nothing is silently dropped.
    remaining = {r[key]: [c for c in blanks[r[key]]
                          if (i, c) not in filled]
                 for i, r in enumerate(rows)}
    esc = {k: v for k, v in remaining.items() if v}
    log("")
    log(f"TIER 3 — deep research for {sum(len(v) for v in esc.values())} cells "
        f"across {len(esc)} companies")
    if esc:
        schema = build_schema(columns, key)
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        names = list(esc)
        for start in range(0, len(names), args.chunk):
            chunk = names[start:start + args.chunk]
            ck = ",".join(chunk)
            rid = state.get(ck)
            if rid:
                log(f"  resuming chunk {start // args.chunk} run {rid}")
            else:
                prompt = ("Fill the missing fields for each company below. Only the listed missing "
                          "fields are needed.\n" + "\n".join(
                              f"- {n}: missing {', '.join(esc[n])}" for n in chunk))
                rid = start_run(aid, prompt, schema)
                state[ck] = rid
                STATE.write_text(json.dumps(state, indent=1))
                log(f"  chunk {start // args.chunk} run {rid} started "
                    f"({len(chunk)} companies) — this takes minutes")
            t0 = time.time()
            res = collect_run(aid, rid)
            if not res:
                continue
            out = res.get("output") or {}
            content = out.get("content")
            tindex = index_trust(out.get("trust") or {})
            if not isinstance(content, list):
                log("  unexpected non-list output; raw saved, skipping merge")
                continue
            by_name = {str(o.get(key, "")).strip().lower(): (n, o)
                       for n, o in enumerate(content) if isinstance(o, dict)}
            for name in chunk:
                hit = by_name.get(name.strip().lower())      # join on INPUT key, not returned name
                if not hit:
                    log(f"  {name}: absent from run output")
                    continue
                oi, obj = hit
                ri = next(i for i, r in enumerate(rows) if r[key] == name)
                for col in esc[name]:
                    val = obj.get(col)
                    meta = tindex.get((oi, col), {})
                    conf = meta.get("confidence")
                    if val in (None, "", "Unknown"):
                        continue
                    if conf == "low":
                        # Output is a file someone will treat as clean data. Leave the hole.
                        log(f"  {name[:18]:<18} {col:<16} LOW confidence — left blank, flagged")
                        filled[(ri, col)] = {"value": "", "tier": "agent",
                                             "source": meta.get("url"), "confidence": "low"}
                        continue
                    filled[(ri, col)] = {"value": val, "tier": "agent",
                                         "source": meta.get("url") or obj.get("source_url"),
                                         "confidence": conf}
                    tier_line(name, col, "agent", time.time() - t0, conf)

    meta = {k: v for k, v in
            ((f"{i}|{c}", d) for (i, c), d in filled.items())}
    # Tier 1: values the user already supplied. Mark them explicitly — a blank provenance column
    # reads as a failure, when in fact nothing was fetched because nothing needed fetching.
    for i, r in enumerate(rows):
        for c in columns:
            if c == key or f"{i}|{c}" in meta:
                continue
            if (r.get(c) or "").strip():
                meta[f"{i}|{c}"] = {"value": r[c], "tier": "file",
                                    "source": "(supplied in input)", "confidence": "given"}
    out_rows = [dict(r) for r in rows]
    for (i, c), d in filled.items():
        out_rows[i][c] = d["value"]
    (DATA / "sample_filled.json").write_text(json.dumps(
        {"rows": out_rows, "columns": columns, "meta": meta,
         "generated_at": datetime.now(timezone.utc).isoformat()}, indent=1))
    _write(out_rows, columns, meta, args.output, key)

    log("")
    counts = {"file": total_blanks - len(filled), "search": 0, "agent": 0}
    for d in filled.values():
        counts[d["tier"]] += 1
    log(f"filled {len(filled)}/{total_blanks} blanks — "
        f"tier2 search={counts['search']}, tier3 agent={counts['agent']}, "
        f"unresolved={counts['file']}")
    log(f"wrote {args.output}")
    return 0


def _write(out_rows, columns, meta, path, key) -> None:
    side = [f"{c}__{s}" for c in columns if c != key for s in ("source", "confidence", "tier")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns + side)
        w.writeheader()
        for i, r in enumerate(out_rows):
            row = dict(r)
            for c in columns:
                if c == key:
                    continue
                d = meta.get(f"{i}|{c}")
                if d:
                    row[f"{c}__source"] = d.get("source") or ""
                    row[f"{c}__confidence"] = d.get("confidence") or ""
                    row[f"{c}__tier"] = d.get("tier") or ""
            w.writerow(row)


if __name__ == "__main__":
    sys.exit(main())
