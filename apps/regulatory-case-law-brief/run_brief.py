"""Run the legal-brief agent over a list of topics (resumable), then render briefs.

  python run_brief.py                 # all topics in data/topics.txt not yet fetched
  python run_brief.py --topic "..."   # one ad-hoc topic
  python run_brief.py --render-only   # rebuild briefs from cached raw (no API calls)

Raw agent results -> data/raw/<slug>.json (cache). Rendered -> briefs/<slug>.md + data/briefs.json.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

import config as C


def slugify(s: str) -> str:
    # short hash suffix so truncation can't collide two different topics onto one slug
    base = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]
    return f"{base}-{hashlib.sha1(s.encode()).hexdigest()[:6]}"


def agent_id() -> str:
    if not C.AGENTS_FILE.exists():
        sys.exit("agents.json missing — run setup_agent.py first")
    return json.loads(C.AGENTS_FILE.read_text())["legal_brief"]


def safe(method, url, tries=4, **kw):
    last = None
    for _ in range(tries):
        try:
            r = requests.request(method, url, headers=C.HEADERS, timeout=90, **kw)
            if r.status_code in (200, 201, 202) and r.text.strip():
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:120]!r}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(5)
    print(f"    request failed after {tries} tries: {method} .../{url.rsplit('/', 1)[-1]} — {last}")
    return None


def run_topic(aid: str, topic: str) -> dict:
    slug = slugify(topic)
    started = safe("POST", f"{C.BASE_URL}/task-agents/{aid}/runs", json={"input": topic, "effort": C.EFFORT})
    if not started or "id" not in started:
        return {"topic": topic, "slug": slug, "status": "submit_failed"}
    rid = started["id"]
    t0 = time.time()
    run = started
    while True:
        run = safe("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{rid}") or run
        if run and not run.get("is_active"):
            break
        if time.time() - t0 > C.RUN_TIMEOUT_S:
            return {"topic": topic, "slug": slug, "status": "timeout", "run_id": rid}
        time.sleep(C.POLL_SECONDS)
    res = safe("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{rid}/result") or {}
    payload = {"topic": topic, "slug": slug, "status": run.get("status"), "run_id": rid,
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": res}
    (C.RAW / f"{slug}.json").write_text(json.dumps(payload, indent=2))
    n = len((res.get("output", {}).get("content") or {}).get("applicable_regulations") or []) if run.get("status") == "completed" else 0
    print(f"  [{slug}] {run.get('status')}  regs={n}  {int(time.time()-t0)}s")
    return {"topic": topic, "slug": slug, "status": run.get("status")}


def _public(url):
    """Keep only real public http(s) URLs; drop Nimble internal /pages/ cache paths."""
    return url if isinstance(url, str) and url.startswith("http") else None


def _claim_url_map(trust: dict) -> dict:
    """JSON-path -> first real citation URL, from trust.claims."""
    m = {}
    for c in trust.get("claims", []) or []:
        p, cites = c.get("path"), (c.get("citations") or [])
        if p and cites and _public(cites[0].get("url")):
            m[p] = cites[0]["url"]
    return m


def structured_brief(output: dict) -> dict:
    """Normalize one agent result into a clean brief record with real public URLs baked in."""
    content = output.get("content", {}) or {}
    trust = output.get("trust", {}) or {}
    claim_urls = _claim_url_map(trust)

    def real_url(prefix, fallback):
        for p, u in claim_urls.items():
            if p.startswith(prefix):
                return u
        return _public(fallback)

    regs = [{"name": r.get("name", ""), "jurisdiction": r.get("jurisdiction"),
             "requirement": r.get("requirement"),
             "url": real_url(f"$.applicable_regulations[{i}]", r.get("citation_url"))}
            for i, r in enumerate(content.get("applicable_regulations") or [])]
    cases = [{"case_name": c.get("case_name", ""), "court": c.get("court"), "date": c.get("date"),
              "holding": c.get("holding"), "url": real_url(f"$.key_cases[{i}]", c.get("citation_url"))}
             for i, c in enumerate(content.get("key_cases") or [])]
    changes = [{"change": c.get("change", ""), "date": c.get("date"),
                "url": real_url(f"$.recent_changes[{i}]", c.get("source_url"))}
               for i, c in enumerate(content.get("recent_changes") or [])]
    src_urls = []
    for s in (trust.get("sources") or []):
        u = _public(s.get("url"))
        if u and u not in src_urls:
            src_urls.append(u)
    return {"subject": content.get("subject", ""), "jurisdiction": content.get("jurisdiction", ""),
            "summary": content.get("summary", ""), "regulations": regs, "cases": cases,
            "changes": changes, "sources": src_urls}


def render_markdown(sb: dict) -> str:
    def block(items, fmt):
        return "\n".join(fmt(x) for x in items) or "_None found._"
    regs = block(sb["regulations"], lambda r: f"- **{r['name']}**"
                 + (f" ({r['jurisdiction']})" if r.get("jurisdiction") else "")
                 + (f" — {r['requirement']}" if r.get("requirement") else "")
                 + (f"  [source]({r['url']})" if r.get("url") else ""))
    cases = block(sb["cases"], lambda c: f"- **{c['case_name']}**"
                  + (f" ({c.get('court','')}{', ' + c['date'] if c.get('date') else ''})" if c.get("court") or c.get("date") else "")
                  + (f" — {c['holding']}" if c.get("holding") else "")
                  + (f"  [source]({c['url']})" if c.get("url") else ""))
    changes = block(sb["changes"], lambda c: f"- {c['change']}"
                    + (f" ({c['date']})" if c.get("date") else "")
                    + (f"  [source]({c['url']})" if c.get("url") else ""))
    sources = "\n".join(f"- {u}" for u in sb["sources"]) or "_None._"
    return (f"# Compliance Brief — {sb['subject']}\n\n**Jurisdiction:** {sb['jurisdiction']}\n"
            f"_Research summary, not legal advice._\n\n## Summary\n{sb['summary']}\n\n"
            f"## Applicable regulations\n{regs}\n\n## Key case law\n{cases}\n\n"
            f"## Recent changes\n{changes}\n\n## Sources\n{sources}\n")


def render_all():
    index = []
    for f in sorted(C.RAW.glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("status") != "completed":
            continue
        output = (d.get("result") or {}).get("output", {})
        content = output.get("content")
        if not isinstance(content, dict):
            continue
        sb = structured_brief(output)
        (C.BRIEFS / f"{d['slug']}.md").write_text(render_markdown(sb))
        index.append({"slug": d["slug"], "topic": d["topic"], **sb})
    (C.DATA / "briefs.json").write_text(json.dumps(index, indent=2))
    print(f"rendered {len(index)} briefs -> briefs/*.md + data/briefs.json (structured)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", type=str, default=None)
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    if args.render_only:
        render_all(); return
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")
    aid = agent_id()
    topics = [args.topic] if args.topic else [
        t.strip() for t in C.TOPICS_FILE.read_text().splitlines() if t.strip() and not t.startswith("#")]
    todo = [t for t in topics if not (C.RAW / f"{slugify(t)}.json").exists()]
    if todo:
        print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] running {len(todo)} topics @ concurrency {C.CONCURRENCY}")
        with ThreadPoolExecutor(max_workers=C.CONCURRENCY) as ex:
            futs = [ex.submit(run_topic, aid, t) for t in todo]
            for _ in as_completed(futs):
                pass
    else:
        print("all topics already cached")
    render_all()


if __name__ == "__main__":
    main()
