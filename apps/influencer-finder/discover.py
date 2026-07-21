"""Run the influencer agent over a list of queries (resumable), accumulate a deduped
dataset, upsert into Supabase, and write a local cache.

  python discover.py                 # all queries in data/queries.txt not yet fetched
  python discover.py --query "..."   # one ad-hoc query
  python discover.py --build-only    # rebuild dataset + cache from raw (no API calls)

Raw -> data/raw/<slug>.json. Dataset -> Supabase `influencers` (if creds) + data/influencers.json.
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
import supabase_store
from agent_config import run_input


def slugify(s: str) -> str:
    # hash suffix so truncation can't collide two different queries onto one slug
    base = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]
    return f"{base}-{hashlib.sha1(s.encode()).hexdigest()[:6]}"


def category_from_query(q):
    """Clean category label from the query (the canonical grouping), since the agent's
    per-row `niche` is inconsistent free-text and fragments any filter."""
    if not q:
        return None
    s = re.split(r"\bon\b", q, 1)[0]                                   # drop " on <platform>, ..."
    s = re.sub(r"\b(micro-?influencers?|influencers?|creators?|reviewers?|thought leaders?)\b", "", s, flags=re.I)
    return " ".join(s.split()).strip(" ,-").title() or None


_UNIT_MULT = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "mn": 1_000_000, "million": 1_000_000,
              "b": 1_000_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000}


def parse_followers(s):
    if not s:
        return None
    t = str(s).strip().lower().replace(",", "")
    # anchor the unit so "1.2 million" is 1_200_000, not 1 (word or letter suffix)
    m = re.match(r"([\d.]+)\s*(k|m|mn|b|bn|thousand|million|billion)?\b", t)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    return int(n * _UNIT_MULT.get(m.group(2) or "", 1))


_PLATFORM_CANON = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube",
                   "x": "X", "twitter": "X", "linkedin": "LinkedIn", "facebook": "Facebook"}


def canon_platform(p):
    return _PLATFORM_CANON.get((p or "").strip().lower(), (p or "").strip().title())


def fmt_followers(n):
    """Standardize every follower count to compact K/M form from the parsed number."""
    if n is None:
        return None
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def agent_id() -> str:
    if not C.AGENTS_FILE.exists():
        sys.exit("agents.json missing — run setup_agent.py first")
    try:
        return json.loads(C.AGENTS_FILE.read_text())["influencer_finder"]
    except (json.JSONDecodeError, KeyError):
        sys.exit("agents.json is malformed or missing the 'influencer_finder' id — delete it and re-run setup_agent.py")


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


def run_query(aid: str, query: str) -> dict:
    slug = slugify(query)
    started = safe("POST", f"{C.BASE_URL}/task-agents/{aid}/runs",
                   json={"input": run_input(query), "effort": C.EFFORT})
    if not started or "id" not in started:
        return {"query": query, "slug": slug, "status": "submit_failed"}
    rid = started["id"]
    t0 = time.time()
    run = started
    while True:
        run = safe("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{rid}") or run
        # terminal ONLY on an explicit is_active==False; a partial response missing the field
        # must not be read as "done" (that would fetch the result before the run finishes)
        if run and run.get("is_active") is False:
            break
        if time.time() - t0 > C.RUN_TIMEOUT_S:
            return {"query": query, "slug": slug, "status": "timeout", "run_id": rid}
        time.sleep(C.POLL_SECONDS)
    res = safe("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{rid}/result") or {}
    status = run.get("status")
    # don't cache an empty result as completed (result fetch may have exhausted retries)
    if status == "completed" and not (res.get("output", {}) or {}).get("content"):
        status = "result_missing"
    payload = {"query": query, "slug": slug, "status": status, "run_id": rid,
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": res}
    (C.RAW / f"{slug}.json").write_text(json.dumps(payload, indent=2))
    n = len(res.get("output", {}).get("content") or []) if status == "completed" else 0
    print(f"  [{slug[:40]}] {status}  found={n}  {int(time.time()-t0)}s")
    return {"query": query, "slug": slug, "status": status}


def build_dataset() -> list:
    """Parse all cached raw into a deduped list of influencer rows."""
    best = {}  # key -> (recency_tuple, row); on a duplicate creator the freshest observation wins
    for f in C.RAW.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:  # a truncated/corrupt cache file must not abort the build
            print(f"  skipping unreadable cache {f.name}: {e}")
            continue
        if d.get("status") != "completed":
            continue
        content = (d.get("result") or {}).get("output", {}).get("content")
        if not isinstance(content, list):
            continue
        fetched_at = d.get("fetched_at") or ""
        for r in content:
            if not isinstance(r, dict):
                continue
            platform = canon_platform((r.get("platform") or "").strip())  # canonical BEFORE dedup
            handle = (r.get("handle") or "").strip().lstrip("@")
            if not platform or not handle:
                continue
            key = (platform.lower(), handle.lower())
            # prefer the newest observation: observed_at primary, fetched_at as fallback
            recency = (str(r.get("observed_at") or ""), fetched_at)
            if key in best and recency <= best[key][0]:
                continue
            best[key] = (recency, {
                "platform": platform, "handle": handle,
                "category": category_from_query(d.get("query")),
                "profile_url": r.get("profile_url"),
                "follower_count": r.get("follower_count"),
                "follower_count_num": parse_followers(r.get("follower_count")),
                "followers_display": fmt_followers(parse_followers(r.get("follower_count"))),
                "engagement_rate": r.get("engagement_rate"),
                "niche": r.get("niche"), "location": r.get("location"),
                "contact": r.get("contact"), "bio_summary": r.get("bio_summary"),
                "query": d.get("query"), "observed_at": r.get("observed_at"),
            })
    rows = [v[1] for v in best.values()]
    rows.sort(key=lambda x: x.get("follower_count_num") or 0, reverse=True)
    (C.DATA / "influencers.json").write_text(json.dumps(rows, indent=2))
    n_up = supabase_store.upsert(rows)
    print(f"dataset: {len(rows)} distinct influencers -> data/influencers.json"
          + (f"; {n_up} upserted to Supabase" if n_up else "; Supabase skipped (local cache only)"))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", type=str, default=None)
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    if args.build_only:
        build_dataset(); return
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")
    aid = agent_id()
    queries = [args.query] if args.query else [
        q.strip() for q in C.QUERIES_FILE.read_text().splitlines() if q.strip() and not q.startswith("#")]
    queries = list(dict.fromkeys(queries))   # dedup so duplicates don't race on the same cache slug

    def done(query):  # only a COMPLETED cache counts as done; failed/timeout re-runs
        p = C.RAW / f"{slugify(query)}.json"
        if not p.exists():
            return False
        try:
            return json.loads(p.read_text()).get("status") == "completed"
        except Exception:  # noqa: BLE001
            return False
    todo = [q for q in queries if not done(q)]
    if todo:
        print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] running {len(todo)} queries @ concurrency {C.CONCURRENCY}")
        with ThreadPoolExecutor(max_workers=C.CONCURRENCY) as ex:
            futs = [ex.submit(run_query, aid, q) for q in todo]
            for fut in as_completed(futs):
                try:
                    fut.result()   # surface worker exceptions instead of silently dropping them
                except Exception as e:  # noqa: BLE001
                    print(f"  worker error: {e!r}")
    else:
        print("all queries already cached")
    build_dataset()


if __name__ == "__main__":
    main()
