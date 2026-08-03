#!/usr/bin/env python3
"""Hermes Account Monitor — a standing "who moved" digest built on the Nimble Hermes plugin.

You give it a list of businesses you care about. Each cycle it researches them, diffs against the
previous cycle, and reports ONLY what changed — with a citation per change.

Why businesses and not products: a Web Search Agent earns its cost when the sources are unknown per
entity. Checking a known price on a known retailer is deterministic extraction — that is what
Extraction Templates are for. Open-web company signals are the opposite: few entities, unknown
sources, real research. That also suits the measured coverage limit (see BATCH_SIZE).

Calls the plugin's own tools so the cookbook demonstrates the integration rather than bypassing it.

Usage
-----
  .venv/bin/python monitor.py                        # cached digest, no API calls
  USE_LIVE=true .venv/bin/python monitor.py --setup  # one-time: create + configure the agent
  USE_LIVE=true .venv/bin/python monitor.py          # run a cycle, then diff against the previous one
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
RUNS = DATA / "runs"
RUNS.mkdir(parents=True, exist_ok=True)
DB = DATA / "signals.db"

BASE = "https://sdk.nimbleway.com/v1"
KEY = os.getenv("NIMBLE_API_KEY", "")
H = {"Authorization": f"Bearer {KEY}"}
PH = {**H, "Content-Type": "application/json-patch+json"}
USE_LIVE = os.getenv("USE_LIVE", "false").lower() == "true"

EFFORT = "high"
POLL = 20

# Batch size is set by COVERAGE, not speed. Measured rows returned vs the full grid:
#   3 entities -> 100%   |   8 entities -> 62%   |   12 entities -> 10% (and claimed `high` confidence)
# Large batches silently return partial grids. A missing row is a change you never hear about, so
# completeness wins. Small batches run concurrently, so wall-clock stays ~one run.
BATCH_SIZE = 3

# The fields we diff. Each is a short factual string or null — never a number type, since sources
# yield ranges and approximations.
# 5 signals, not 6. Two reasons, both measured:
#   - the run API caps output schema at 20 COLUMNS (422 run_input_limit_exceeded). With value+key+
#     date per signal, 6 signals = 22 columns. 5 signals = 19.
#   - `pricing_change` was the one to drop: systematically uncitable at 3 high vs 8 low, because
#     private companies do not publish pricing history.
SIGNALS = ["headline_development", "leadership_change", "funding_status",
           "headcount_signal", "product_launch"]

SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["business", "observed_at"],
        "properties": {
            "business": {"type": "string"},
            **{s: {"type": ["string", "null"]} for s in SIGNALS},
            # Canonical key: a short stable label for the event, used only for dedup.
            **{f"{s}_key": {"type": ["string", "null"]} for s in SIGNALS},
            # WHEN THE EVENT HAPPENED — the load-bearing field. Snapshot diffing cannot work
            # (four attempts, 49/37/49/19 false positives on an 8-minute interval) because a fact
            # absent from the previous run may have been missed rather than new. The event's own
            # date settles it deterministically, with no judgement call.
            **{f"{s}_date": {"type": ["string", "null"]} for s in SIGNALS},
            "source_url": {"type": ["string", "null"]},
            "observed_at": {"type": "string"},
            "notes": {"type": ["string", "null"]},
        },
        "additionalProperties": True,
    },
}

DOMAIN_EXPERTISE = """You are an analyst tracking a watchlist of businesses for a go-to-market team.
For each business, report only developments that a salesperson or account manager would act on:
leadership changes, funding events, headcount movement and product launches.
Prefer the company's own website, newsroom, blog, careers page and investor relations; use
reputable press only when the primary source is silent. If a signal cannot be confirmed from a
source you actually retrieved, return null — never infer, never estimate, and never carry a
development over from a similarly-named company. Keep each signal to one factual sentence, and set
`observed_at` to the date you accessed the source, not the date of the event.

For every signal you also return a `<signal>_key`: the bare fact in at most six lowercase words,
no dates unless the date IS the fact, no adjectives, no source names. It must be identical across
runs whenever the underlying fact has not changed. Examples:
  funding_status      -> "series f" | "acquired by capital one" | "none"
  leadership_change   -> "cfo john mccauley" | "none"
  headcount_signal    -> "237 layoffs" | "1965 employees" | "none"
  product_launch      -> "ai governance" | "none"
If a signal is null, its key must be "none".

For every signal you also return a `<signal>_date`: the date the EVENT happened, as YYYY-MM-DD
(use YYYY-MM if only the month is known, YYYY if only the year). This is the date of the event
itself, never the date you accessed the source. If you cannot establish when it happened, return
"unknown" — do not guess.
"""

GOALS = [
    "Returns one row per business in the input, in input order, even when nothing was found",
    "Returns null for any signal not confirmed by a source actually retrieved",
    "Populates source_url for every non-null signal",
    "Keeps each signal to a single factual sentence, not a summary paragraph",
    "Returns a <signal>_key for every signal: the bare fact in <=6 lowercase words, or 'none'",
    "Returns a <signal>_date for every signal: when the EVENT happened (YYYY-MM-DD), or 'unknown'",
    "Matches the exact business requested - never a similarly-named company",
]

# Empty `domains` = category hint, not a host restriction. Company newsrooms live on thousands of
# hosts, so whitelisting specific domains would box the agent out of the primary source.
SOURCES = {
    "allow": [
        {"title": "Company website, newsroom, blog, careers and investor relations",
         "domains": [], "order": 0},
        {"title": "Reputable business and tech press", "domains": [], "order": 1},
        {"title": "Crunchbase", "domains": ["crunchbase.com", "www.crunchbase.com"], "order": 2},
        {"title": "LinkedIn", "domains": ["linkedin.com", "www.linkedin.com"], "order": 3},
    ],
    "block": [],
}

WATCHLIST = [
    "Ramp", "Vanta", "Deel", "Linear", "Retool",
    "Airtable", "Notion", "Figma", "Databricks", "Snowflake",
    "Stripe", "Plaid", "Brex", "Rippling", "Anthropic",
]


def log(m: str) -> None:
    print(m, flush=True)


def db() -> sqlite3.Connection:
    """Confidence is stored PER SIGNAL, not per row.

    Trust claims are field-scoped ($[0].pricing_change), and a row typically carries ~25 high
    claims alongside 4-6 low ones on fields the agent could not cite. Collapsing that to one
    row-level value (weakest wins) discarded every good signal because an unrelated field was
    unverified. Per-field is the only honest granularity.
    """
    c = sqlite3.connect(DB)
    cols = ", ".join(f"{s} TEXT, {s}_key TEXT, {s}_conf TEXT, {s}_cite TEXT" for s in SIGNALS)
    c.execute(f"""CREATE TABLE IF NOT EXISTS signals(
        cycle_at TEXT, business TEXT, {cols},
        source_url TEXT, run_id TEXT,
        PRIMARY KEY (cycle_at, business))""")
    # The ledger is the actual product. It ACCUMULATES across every cycle, so "have we seen this
    # before" replaces "does today differ from yesterday" — the question that was unanswerable.
    # Dedup key is (business, signal, event_date) — NO prose. Including the label let rephrasing
    # create duplicates: the same Vanta headcount fact appeared twice in one digest because two
    # runs worded it differently. A business rarely has two distinct events of the same type on the
    # same date, and merging them beats showing the same news twice.
    # Key on MONTH, not full date: the same fact arrives at different precision between runs
    # ("as of 2026-08-03" vs "as of August 2026"), which produced visible duplicates in the digest.
    # event_date keeps full precision for filtering; event_month is only the dedup key.
    c.execute("""CREATE TABLE IF NOT EXISTS ledger(
        business TEXT, signal TEXT, event_month TEXT, event_date TEXT, label TEXT,
        description TEXT, confidence TEXT, citation TEXT,
        first_seen_cycle TEXT,
        PRIMARY KEY (business, signal, event_month))""")
    return c


def field_trust(trust: dict) -> dict[tuple[int, str], tuple[str | None, str | None]]:
    """(row_index, field) -> (confidence, citation_url) from trust.claims[].path.

    The row's own `source_url` must NOT be reused per signal: one URL per business was being
    printed under every signal, so a single LinkedIn post appeared to source a leadership change,
    a layoff and a product launch. Each claim carries its own citation — use it.
    """
    out: dict[tuple[int, str], tuple[str | None, str | None]] = {}
    for c in trust.get("claims") or []:
        p = c.get("path") or ""
        if not (p.startswith("$[") and "]." in p):
            continue
        try:
            i = int(p[2:p.index("]")])
        except ValueError:
            continue
        cite = (c.get("citations") or [{}])[0].get("url")
        out[(i, p.split(".")[-1])] = (c.get("confidence"), cite)
    return out


# --------------------------------------------------------------- change detection
_MONEY = re.compile(r"\$\s?\d[\d,.]*\s?(?:billion|million|bn|m|b|k)?", re.I)
_PCT = re.compile(r"\d+(?:\.\d+)?\s?%")
_NUM = re.compile(r"\b\d[\d,]{2,}\b")
_YEAR = re.compile(r"\b20\d{2}\b")
_ROUND = re.compile(r"\b(?:series\s+[a-k]|seed|pre-seed|ipo|tender offer)\b", re.I)
_NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b")
_ROLE = re.compile(r"\b(?:CEO|CFO|CTO|COO|CRO|CMO|Chair(?:man)?|President|VP)\b")


def salient(text: str) -> frozenset[str]:
    """The load-bearing facts in a signal sentence, normalised.

    Signals are free text, so string equality is useless for change detection: two cycles 11
    minutes apart produced 49 "changes" across 13 of 15 businesses purely from rephrasing. Compare
    the facts instead — amounts, percentages, headcounts, years, round labels, names and roles.
    """
    if not text:
        return frozenset()
    s = text.replace(",", "")
    facts: set[str] = set()
    for rx in (_MONEY, _PCT, _NUM, _YEAR, _ROUND, _ROLE):
        facts |= {m.group(0).lower().replace(" ", "") for m in rx.finditer(s)}
    facts |= {m.group(0).lower() for m in _NAME.finditer(text)}
    return frozenset(facts)


def norm_date(d: str | None) -> str:
    """Normalise an event date to YYYY-MM-DD / YYYY-MM / YYYY, or 'unknown'."""
    if not d:
        return "unknown"
    s = str(d).strip().lower()
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", s)
    if not m:
        return "unknown"
    y, mo, day = m.group(1), m.group(2), m.group(3)
    return f"{y}-{mo}-{day}" if day else (f"{y}-{mo}" if mo else y)


def norm_key(k: str | None) -> str:
    """Canonicalise the agent's key so trivial variation cannot masquerade as change."""
    if not k:
        return "none"
    s = re.sub(r"[^a-z0-9 ]", " ", str(k).lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s or "none"


def key_changed(before: str | None, after: str | None) -> bool:
    b, a = norm_key(before), norm_key(after)
    if b == a:
        return False
    if a == "none":
        return False          # losing a signal is coverage, not movement
    return True


def is_real_change(before: str | None, after: str | None) -> bool:
    """True only when the underlying facts moved, not when the wording did."""
    a, b = salient(before or ""), salient(after or "")
    if not (before or "").strip():
        return bool((after or "").strip())          # nothing -> something is a real change
    if not a and not b:
        return False                                # no extractable facts either side: assume rewording
    inter, union = len(a & b), len(a | b)
    return (inter / union if union else 1.0) < 0.6


def ingest(res: dict, batch: list[str], cycle_at: str, rid: str) -> int:
    """Store one run's rows. Shared by the live path and --reingest, so replays cost nothing."""
    rows, trust = _extract(res)
    ftrust = field_trust(trust)
    conn = db()
    n = 0
    placeholders = ",".join("?" * (2 + len(SIGNALS) * 4 + 2))
    for oi, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        key = match_key(r.get("business", ""), batch)
        if not key:
            continue
        vals: list = [cycle_at, key]
        for s in SIGNALS:
            c, cite = ftrust.get((oi, s), (None, None))
            vals += [r.get(s), norm_key(r.get(f"{s}_key")), c, cite]
        vals += [r.get("source_url"), rid]
        conn.execute(f"INSERT OR REPLACE INTO signals VALUES ({placeholders})", vals)
        for s in SIGNALS:
            desc = (r.get(s) or "").strip()
            label = norm_key(r.get(f"{s}_key"))
            date = norm_date(r.get(f"{s}_date"))
            if not desc or label == "none":
                continue
            c, cite = ftrust.get((oi, s), (None, None))
            # INSERT OR IGNORE: first sighting wins, so re-finding an event never re-reports it.
            conn.execute("INSERT OR IGNORE INTO ledger VALUES (?,?,?,?,?,?,?,?,?)",
                         (key, s, date[:7], date, label, desc, c, cite, cycle_at))
        n += 1
    conn.commit()
    conn.close()
    return n


def match_key(name: str, keys: list[str]) -> str | None:
    """Map a returned business name back to the watchlist string. Never key on the returned name:
    "Stripe" may come back as "Stripe, Inc." and token overlap survives that."""
    n = (name or "").lower()
    if not n:
        return None

    def score(k: str) -> float:
        toks = [w for w in k.lower().split() if len(w) > 2]
        return sum(1 for w in toks if w in n) / max(len(toks), 1)

    best = max(keys, key=score)
    return best if score(best) >= 0.5 else None


def setup_agent() -> str:
    """Custom agent, not a template clone.

    No gallery template fits: `lead-enrichment` is hardcoded to one company (Acme United),
    `financial-intelligence` assumes public tickers, `hiring-intelligence` is careers-only.
    A from-scratch create DOES persist goals/sources (unlike template clones — see Quirk 6), and
    `output_schema` is REQUIRED for enrichment (422 otherwise).
    """
    body = {
        "display_name": "Hermes Account Monitor",
        "description": "Daily what-moved signals for a watchlist of businesses.",
        "use_case": "enrichment",
        "effort": EFFORT,                 # explicit: the spec default is a buggy use_case value
        "domain_expertise": DOMAIN_EXPERTISE,
        "goals": GOALS,
        "sources": SOURCES,
        "output_schema": SCHEMA,
    }
    r = requests.post(f"{BASE}/task-agents", headers=H, timeout=60, json=body)
    if not r.ok:
        raise SystemExit(f"create failed {r.status_code}: {r.text[:300]}")
    aid = r.json()["id"]
    got = requests.get(f"{BASE}/task-agents/{aid}", headers=H, timeout=60).json()
    assert got.get("goals") and (got.get("sources") or {}).get("allow"), "config did not persist"
    (DATA / "monitor_agent.json").write_text(json.dumps(got, indent=1))
    log(f"created agent {aid} — goals={len(got['goals'])} "
        f"sources={len(got['sources']['allow'])} schema_fields={len(SIGNALS) + 4}")
    return aid


def _extract(res: dict) -> tuple[list, dict]:
    """Accept the plugin's envelope or the raw API shape."""
    for path in (("output", "content"), ("result", "output", "content"), ("content",)):
        cur = res
        for k in path:
            cur = (cur or {}).get(k) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return cur, (res.get("output", {}).get("trust") or res.get("trust") or {})
    return [], {}


def run_cycle(aid: str, businesses: list[str], cycle_at: str) -> int:
    from hermes_nimble_agent import tools

    batches = [businesses[i:i + BATCH_SIZE] for i in range(0, len(businesses), BATCH_SIZE)]
    log(f"cycle {cycle_at[:19]}: {len(businesses)} businesses in {len(batches)} concurrent batches")
    stored = [0]
    lock = threading.Lock()

    def work(idx: int, batch: list[str]) -> None:
        task = ("For each business below, report what has changed recently that a go-to-market team "
                "should act on — leadership changes, funding, headcount movement, product launches, "
                "pricing changes. One factual sentence per signal, null if unconfirmed.\n- "
                + "\n- ".join(batch))
        started = json.loads(tools.nimble_agent_run_start(
            {"agent_id": aid, "task": task, "effort": EFFORT}))
        rid = started.get("run_id") or (started.get("run") or {}).get("run_id")
        if not rid:
            log(f"  batch{idx}: start failed {str(started)[:160]}")
            return
        log(f"  batch{idx}: {rid} ({', '.join(batch)})")

        t0 = time.time()
        while True:
            time.sleep(POLL)
            st = json.loads(tools.nimble_agent_run_status({"agent_id": aid, "run_id": rid}))
            if st.get("is_active", st.get("run", {}).get("is_active")) is False:
                break
            if time.time() - t0 > 2400:
                log(f"  batch{idx}: timeout")
                return

        res = json.loads(tools.nimble_agent_run_result({"agent_id": aid, "run_id": rid}))
        (RUNS / f"{rid}.json").write_text(json.dumps(res, indent=1))   # raw BEFORE transform
        rows, trust = _extract(res)
        log(f"  batch{idx}: {len(rows)}/{len(batch)} rows in {int(time.time()-t0)}s")

        with lock:
            stored[0] += ingest(res, batch, cycle_at, rid)

    ths = [threading.Thread(target=work, args=(i, b)) for i, b in enumerate(batches)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return stored[0]


# Must not match a RANGE: "lists 1,001-5,000 employees" would otherwise yield 5,000 as the count
# and a bogus 61% drop. Reject when the number is the tail of a dash-range.
_HEADCOUNT = re.compile(r"(?<![-\u2013\u2014\d,])(\d[\d,]{2,})\s+employees\b", re.I)


def headcount_of(text: str) -> int | None:
    """Specific employee count, or None. The regex lookbehind already rejects the tail of a
    dash-range ("1,001-5,000 employees"), so do NOT also reject on the word "range" — a real line
    reads "2,666 employees on LinkedIn (1,001-5,000 range)" and must still parse as 2,666."""
    if not text:
        return None
    m = _HEADCOUNT.search(text)
    return int(m.group(1).replace(",", "")) if m else None


def headcount_moved(business: str, description: str, event_month: str,
                    conn: sqlite3.Connection) -> bool:
    """`headcount_signal` reports current state ("1,965 employees today"), not a dated event, so it
    would otherwise surface every single month. Only report a MATERIAL move (>5%) against the most
    recent earlier reading for that business."""
    now = headcount_of(description)
    if now is None:
        return False
    prev_rows = conn.execute(
        "SELECT description FROM ledger WHERE business=? AND signal='headcount_signal' "
        "AND event_month < ? ORDER BY event_month DESC LIMIT 3", (business, event_month)).fetchall()
    for (d,) in prev_rows:
        old = headcount_of(d)
        if old is None:
            continue
        if old and abs(now - old) / old > 0.05:
            return True
        return False        # a prior reading exists and barely moved -> not news
    return False            # no prior reading -> a first observation is not a change


def new_since(cutoff: str, cycle_at: str) -> list[dict]:
    """Ledger entries whose EVENT happened after `cutoff`.

    No prose comparison anywhere. An event found late (Vanta's CFO joined in June, noticed in
    August) enters the ledger dated June and simply never appears in a daily digest. Events with an
    unknown date are recorded but never surfaced — we cannot prove they are new, and a monitor that
    cries wolf is worse than one that stays quiet.
    """
    conn = db()
    rows = conn.execute(
        "SELECT business, signal, event_date, description, confidence, citation, first_seen_cycle, "
        "event_month FROM ledger WHERE event_date != 'unknown' AND event_date > ? "
        "ORDER BY event_date DESC", (cutoff[:10],)).fetchall()
    out = []
    for r in rows:
        item = {"business": r[0], "kind": r[1], "event_date": r[2], "after": r[3],
                "confidence": r[4], "source": r[5], "first_seen": r[6]}
        if r[1] == "headcount_signal":
            if not headcount_moved(r[0], r[3], r[7], conn):
                continue
            prior = conn.execute(
                "SELECT description FROM ledger WHERE business=? AND signal='headcount_signal' "
                "AND event_month < ? ORDER BY event_month DESC LIMIT 3", (r[0], r[7])).fetchall()
            for (d,) in prior:
                old = headcount_of(d)
                if old is not None:
                    item["moved_from"], item["moved_to"] = old, headcount_of(r[3])
                    break
        out.append(item)
    conn.close()
    return out


def write_memory(cycle_at: str) -> pathlib.Path:
    """Mirror the ledger into Hermes' own memory file.

    Hermes keeps a markdown memory it curates and reads back on every session. Putting the event
    ledger there means the agent shares one accumulating record with the app — and it is the
    cookbook's most showable artifact: a company event ledger visibly growing cycle by cycle.
    """
    home = pathlib.Path(os.getenv("HERMES_HOME", HERE / ".hermes_home"))
    home.mkdir(parents=True, exist_ok=True)
    conn = db()
    rows = conn.execute(
        "SELECT business, signal, event_date, description, citation FROM ledger "
        "WHERE event_date != 'unknown' ORDER BY business, event_date DESC").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    conn.close()

    lines = ["# Account Monitor — known events", "",
             f"Maintained by monitor.py. {len(rows)} dated events "
             f"({total} total incl. undated). Last cycle {cycle_at[:19]}.",
             "An event listed here has already been reported and will not be reported again.", ""]
    current = None
    for b, sig, date, desc, cite in rows:
        if b != current:
            lines += [f"## {b}", ""]
            current = b
        lines.append(f"- **{date}** ({sig.replace('_', ' ')}) {desc}")
        if cite:
            lines.append(f"  - source: {cite}")
    path = home / "MEMORY.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def digest(deltas: list[dict], prev: str, now: str) -> str:
    real = [d for d in deltas if d["kind"] != "coverage_changed"]
    cov = len(deltas) - len(real)
    if not real:
        return (f"*Account Monitor* — nothing moved since {prev[:16]}. Staying quiet."
                + (f"\n_({cov} not resolved this cycle — coverage, not movement.)_" if cov else ""))

    icon = {"headline_development": "📌", "leadership_change": "👤", "funding_status": "💰",
            "headcount_signal": "📈", "product_launch": "🚀"}
    by_biz: dict[str, list[dict]] = {}
    for d in real:
        by_biz.setdefault(d["business"], []).append(d)

    lines = [f"*Account Monitor* — {len(real)} change(s) across {len(by_biz)} account(s) "
             f"since {prev[:16]}", ""]
    for biz, ds in by_biz.items():
        lines.append(f"*{biz}*")
        for d in ds:
            label = d["kind"].replace("_", " ")
            if d["kind"] == "headcount_signal" and d.get("moved_from"):
                label = f"headcount {d['moved_from']:,} -> {d['moved_to']:,}"
            lines.append(f"  {icon.get(d['kind'], '•')} {label}: "
                         f"{d['after']}  [{d.get('confidence') or '-'}]")
            if d.get("source"):
                lines.append(f"      ↳ {d['source']}")
        lines.append("")
    if cov:
        lines.append(f"_{cov} account(s) not resolved this cycle — coverage, not movement._")
    return "\n".join(lines)


def deliver(text: str, target: str) -> None:
    """Hand the digest to Hermes for delivery. `hermes send` reuses the gateway's platform
    credentials and needs no running gateway for bot-token platforms (Slack/Telegram/Discord)."""
    env = dict(os.environ)
    env.setdefault("HERMES_HOME", str(HERE / ".hermes_home"))
    p = subprocess.run([str(HERE / ".venv" / "bin" / "hermes"), "send", "-t", target, text],
                       capture_output=True, text=True, env=env, timeout=120)
    if p.returncode == 0:
        log(f"delivered to {target}")
    else:
        log(f"delivery to {target} skipped: {(p.stderr or p.stdout or '').strip()[:160]}")
        log("  (configure a platform with `hermes setup`; the digest above is unaffected)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--deliver", metavar="TARGET",
                    help="send the digest via `hermes send` (e.g. slack, telegram)")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N businesses")
    ap.add_argument("--reingest", metavar="CYCLE_AT",
                    help="rebuild a cycle from saved raw runs (no API calls)")
    args = ap.parse_args()

    cfg_path = DATA / "monitor_config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}

    if args.setup:
        if not USE_LIVE:
            log("--setup requires USE_LIVE=true"); return 1
        cfg = {"agent_id": setup_agent(), "businesses": WATCHLIST,
               "created_at": datetime.now(timezone.utc).isoformat()}
        cfg_path.write_text(json.dumps(cfg, indent=1))
        return 0

    if not USE_LIVE:
        f = DATA / "sample_digest.txt"
        if not f.exists():
            log("no cached digest yet — run once with USE_LIVE=true"); return 1
        text = f.read_text()
        log(text)
        if args.deliver:
            deliver(text, args.deliver)
        return 0

    aid = cfg.get("agent_id")
    if not aid:
        log("no agent — run with --setup first"); return 1
    businesses = cfg.get("businesses", WATCHLIST)
    if args.limit:
        businesses = businesses[:args.limit]

    conn = db()
    prior = [r[0] for r in conn.execute(
        "SELECT DISTINCT cycle_at FROM signals ORDER BY cycle_at DESC")]
    conn.close()

    now = datetime.now(timezone.utc).isoformat()
    n = run_cycle(aid, businesses, now)
    log(f"stored {n} business rows")

    if not prior:
        mem = write_memory(now)
        conn = db()
        led = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        dated = conn.execute(
            "SELECT COUNT(*) FROM ledger WHERE event_date != 'unknown'").fetchone()[0]
        conn.close()
        log(f"\nfirst cycle — ledger seeded with {led} events ({dated} dated). Mirrored to {mem}.")
        log("Nothing to report: every event predates this cycle. Run again tomorrow.")
        return 0

    deltas = new_since(prior[0], now)
    mem = write_memory(now)
    log(f"ledger mirrored to {mem}")
    text = digest(deltas, prior[0], now)
    (DATA / "sample_digest.txt").write_text(text)
    (DATA / "sample_deltas.json").write_text(json.dumps(deltas, indent=1))
    log("")
    log(text)
    if args.deliver:
        deliver(text, args.deliver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
