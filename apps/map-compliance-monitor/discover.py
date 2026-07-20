"""Resumable, concurrent seller-discovery over the SKU list.

One WSA run per SKU. Saves raw AgentRunResult to data/raw/<sku_id>.json the
moment it lands. Resumable at TWO levels:
  - SKU level: completed SKUs are skipped.
  - RUN level: a SKU whose last run is still `running`/`timeout` is RE-ATTACHED to
    that existing run_id and polled to completion — never a wasted new run.

Usage:
  python discover.py                     # all SKUs not yet completed (resumes in-flight)
  python discover.py --limit 3           # first 3 outstanding SKUs (small-batch test)
  python discover.py --skus OLA-002,KER-003
  python discover.py --skus OLA-002 --effort max --force   # permission-gated re-run
"""
import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

import config as C
from agent_config import run_input


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_skus() -> list:
    with open(C.SKUS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def agent_id() -> str:
    if not C.AGENTS_FILE.exists():
        sys.exit("agents.json missing — run setup_agent.py first")
    return json.loads(C.AGENTS_FILE.read_text())["seller_discovery"]


def raw_state(sid: str):
    """Return (status, run_id) from a saved raw file, or (None, None)."""
    p = C.RAW / f"{sid}.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text())
    return d.get("status"), d.get("run_id")


def safe_request(method: str, url: str, tries: int = 4, **kw):
    """HTTP that tolerates transient non-JSON / 5xx by retrying; returns dict or None."""
    last = None
    for _ in range(tries):
        try:
            r = requests.request(method, url, headers=C.HEADERS, timeout=90, **kw)
            if r.status_code in (200, 201, 202) and r.text.strip():
                return r.json()
            last = f"HTTP {r.status_code} body[:80]={r.text[:80]!r}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(5)
    print(f"    (transient after {tries}: {last})")
    return None


def _save(sid, payload, effort, run_id, elapsed, n=0) -> dict:
    payload = {"sku_id": sid, "effort": effort, "elapsed_s": elapsed, "fetched_at": now(),
               "run_id": run_id, **payload}
    (C.RAW / f"{sid}.json").write_text(json.dumps(payload, indent=2))
    print(f"  [{sid}] {payload.get('status')}  sellers={n}  {elapsed}s")
    return {"sku_id": sid, "status": payload.get("status"), "sellers": n}


def poll_and_save(aid, sid, run_id, effort, t0) -> dict:
    run = {"is_active": True}
    while True:
        run = safe_request("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{run_id}") or run
        if run and not run.get("is_active"):
            break
        if time.time() - t0 > C.RUN_TIMEOUT_S:
            return _save(sid, {"status": "timeout"}, effort, run_id, int(time.time() - t0))
        time.sleep(C.POLL_SECONDS)
    elapsed = int(time.time() - t0)
    status = run.get("status")
    result = safe_request("GET", f"{C.BASE_URL}/task-agents/{aid}/runs/{run_id}/result") or {}
    n = len(result.get("output", {}).get("content") or []) if status == "completed" else 0
    return _save(sid, {"status": status, "result": result}, effort, run_id, elapsed, n)


def discover_one(aid, sku, effort, resume_run_id=None) -> dict:
    sid = sku["sku_id"]
    if resume_run_id:
        print(f"  [{sid}] resuming in-flight run {resume_run_id[:20]}…")
        return poll_and_save(aid, sid, resume_run_id, effort, time.time())
    body = {"input": run_input(sku["brand"], sku["product_name"], sku.get("size", "")), "effort": effort}
    started = safe_request("POST", f"{C.BASE_URL}/task-agents/{aid}/runs", json=body)
    if not started or "id" not in started:
        return _save(sid, {"status": "submit_failed"}, effort, None, 0)
    return poll_and_save(aid, sid, started["id"], effort, time.time())


def build_worklist(skus, force):
    """Return list of (sku, resume_run_id|None); skip already-completed SKUs."""
    work = []
    for s in skus:
        st, rid = raw_state(s["sku_id"])
        if force:
            work.append((s, None))
        elif st == "completed":
            continue
        elif st in ("running", "timeout") and rid:
            work.append((s, rid))          # re-attach to in-flight run
        else:                               # None / submit_failed / other → fresh
            work.append((s, None))
    return work


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skus", type=str, default=None)
    ap.add_argument("--effort", type=str, default=C.DEFAULT_EFFORT,
                    choices=["high", "max", "medium", "low", "x-high"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not C.NIMBLE_API_KEY:
        sys.exit("NIMBLE_API_KEY not set")

    aid = agent_id()
    skus = load_skus()
    if args.skus:
        want = {s.strip() for s in args.skus.split(",")}
        skus = [s for s in skus if s["sku_id"] in want]
    work = build_worklist(skus, args.force)
    if args.limit:
        work = work[: args.limit]
    if not work:
        print("nothing to do — all requested SKUs already completed (use --force to re-run)")
        return

    resumes = sum(1 for _, rid in work if rid)
    print(f"[{now()}] {len(work)} SKUs @ effort={args.effort}, concurrency={C.CONCURRENCY} "
          f"({resumes} resumed in-flight, {len(work)-resumes} new)")
    t0 = time.time()
    done = []
    with ThreadPoolExecutor(max_workers=C.CONCURRENCY) as ex:
        futs = {ex.submit(discover_one, aid, s, args.effort, rid): s["sku_id"] for s, rid in work}
        for fut in as_completed(futs):
            try:
                done.append(fut.result())
            except Exception as e:  # noqa: BLE001
                print(f"  [{futs[fut]}] worker error: {e!r}")
    ok = sum(1 for d in done if d["status"] == "completed")
    thin = [d["sku_id"] for d in done if d["status"] == "completed" and d["sellers"] < C.MIN_SELLERS]
    print(f"\n[{now()}] done: {ok}/{len(done)} completed in {int(time.time()-t0)}s")
    if thin:
        print(f"THIN SKUs (<{C.MIN_SELLERS} sellers) — permission-gated max re-run candidates: {thin}")


if __name__ == "__main__":
    main()
