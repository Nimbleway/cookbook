"""Re-research stale facts and record what moved.

Only the volatile half normally comes back: overlays expire in 7 days, base rates in
90. That asymmetry is the point — a refresh is cheap because most of the corpus does
not need re-asking.

  ./.venv/bin/python refresh.py                    # dry run: what is stale
  USE_LIVE=true ./.venv/bin/python refresh.py --go
  USE_LIVE=true ./.venv/bin/python refresh.py --go --lane "8507.60.00|Vietnam|United States"
  USE_LIVE=true ./.venv/bin/python refresh.py --go --kind overlay --force

The previous version of every refreshed record is kept under data/history/, which is
what lets the demo show a real before/after instead of a staged one.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

MAX_CONCURRENT_REFRESH = 4

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk import ingest  # noqa: E402
from desk.delta import diff_content, summarize  # noqa: E402
from desk.freshness import assess  # noqa: E402
from desk.research import Lane, cached_path, research, use_live  # noqa: E402

HISTORY_DIR = HERE / "data" / "history"
CHANGES_LOG = HERE / "data" / "changes.jsonl"


def lane_from_record(record: dict) -> Lane:
    lane = record.get("lane") or {}
    return Lane(
        hts_code=lane.get("hts_code", ""),
        origin=lane.get("origin", ""),
        destination=lane.get("destination", "United States"),
        product=lane.get("product", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", action="store_true", help="actually re-research")
    parser.add_argument("--lane", help="limit to one lane key")
    parser.add_argument("--kind", choices=["rate", "overlay"], help="limit to one fact class")
    parser.add_argument("--force", action="store_true", help="refresh even if fresh")
    args = parser.parse_args()

    records = ingest.load_records()
    if not records:
        print("no corpus on disk — run prewarm.py first", file=sys.stderr)
        return 2

    candidates = []
    for record in records:
        if args.kind and record.get("kind") != args.kind:
            continue
        if args.lane and record.get("lane_key") != args.lane:
            continue
        verdict = assess({"kind": record.get("kind"),
                          "researched_at": record.get("researched_at")})
        if verdict.stale or args.force:
            candidates.append((record, verdict))

    doc_label = lambda r: f"{r.get('doc_key') or r.get('lane_key')} [{r.get('kind')}]"  # noqa: E731

    if not candidates:
        print(f"nothing to refresh — {len(records)} record(s), all inside TTL")
        print("(use --force to refresh anyway)")
        return 0

    print(f"{len(candidates)} record(s) to refresh:")
    for record, verdict in candidates:
        print(f"  {doc_label(record):58} {verdict.describe()}")

    if not args.go:
        print("\ndry run — pass --go to re-research")
        return 0
    if not use_live():
        print("\nUSE_LIVE is false — refresh needs live runs", file=sys.stderr)
        return 2

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    all_changes: list[dict] = []
    io_lock = threading.Lock()

    def refresh_one(record: dict) -> dict | None:
        kind = record["kind"]
        lane = lane_from_record(record)
        before = ingest.parsed_content(record)

        # Keep the old version: this is what makes a real before/after possible.
        current = cached_path(lane, kind)
        if current.exists():
            with io_lock:
                shutil.copy2(current, HISTORY_DIR / f"{lane.slug(kind)}.{stamp}.json")

        started = time.monotonic()
        try:
            fresh = research(lane, kind, force=True)
        except Exception as exc:  # noqa: BLE001
            with io_lock:
                print(f"  FAILED {doc_label(record)} — {type(exc).__name__}: {exc}", flush=True)
            return None

        after = ingest.parsed_content(fresh)
        changes = diff_content(kind, before, after)
        line = summarize(kind, record.get("doc_key") or record.get("lane_key"), changes)
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "doc_key": record.get("doc_key") or record.get("lane_key"),
            "lane_key": record.get("lane_key"),
            "kind": kind,
            "previous_researched_at": record.get("researched_at"),
            "researched_at": fresh.get("researched_at"),
            "run_id": (fresh.get("metadata") or {}).get("run_id"),
            "confidence": (fresh.get("metadata") or {}).get("confidence"),
            "changes": changes,
            "summary": line,
        }
        with io_lock:
            print(f"  {time.monotonic() - started:.0f}s — {line[:150]}", flush=True)
            with CHANGES_LOG.open("a") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
        return entry

    # Concurrent, like prewarm. Sequential refresh made a 50-lane watchlist an
    # hour-long wait; research() also caps in-flight runs by semaphore.
    print(f"\nrefreshing {len(candidates)} record(s), {MAX_CONCURRENT_REFRESH} at a time")
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REFRESH) as pool:
        futures = [pool.submit(refresh_one, record) for record, _ in candidates]
        for fut in as_completed(futures):
            entry = fut.result()
            if entry:
                all_changes.append(entry)

    moved = [e for e in all_changes if e["changes"]]
    print(f"\n{len(all_changes)} refreshed, {len(moved)} with material changes")
    if not moved and all_changes:
        print("nothing moved — that is a valid result, not an empty run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
