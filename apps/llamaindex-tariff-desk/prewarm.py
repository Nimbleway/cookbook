"""Pre-warm the shipped corpus: research 8 lanes × 2 fact classes.

Independent of embeddings — this only runs agents and saves raw records, so it can
run before the index exists.

Resumable: a lane already saved and fresh is skipped, so a crash or a Ctrl-C costs
only the runs in flight. Progress is logged per completion, because a long job with
no output is indistinguishable from a stuck one.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk.research import (  # noqa: E402
    Lane, is_fresh, load_cached, research, use_live,
)

# Deliberate spread: repeated codes across different origins (so the demo can
# compare lanes), a likely duty-free line, and origins with different overlay
# regimes. 8 lanes = 16 runs.
LANES = [
    Lane("8507.60.00", "Vietnam", product="lithium-ion battery packs"),
    Lane("8507.60.00", "China", product="lithium-ion battery packs"),
    Lane("7604.29.10", "Mexico", product="aluminum extrusions"),
    Lane("7604.29.10", "China", product="aluminum extrusions"),
    Lane("6109.10.00", "India", product="cotton knit t-shirts"),
    Lane("6109.10.00", "Bangladesh", product="cotton knit t-shirts"),
    Lane("4901.99.00", "United Kingdom", product="printed books"),
    Lane("8541.43.00", "Malaysia", product="photovoltaic modules"),
]

KINDS = ("rate", "overlay")
_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    if not use_live():
        print("USE_LIVE is false — pre-warming needs live runs.", file=sys.stderr)
        print("Re-run with: USE_LIVE=true ./.venv/bin/python prewarm.py", file=sys.stderr)
        return 2
    for env_key in ("NIMBLE_RATE_AGENT_ID", "NIMBLE_OVERLAY_AGENT_ID"):
        if not os.environ.get(env_key):
            print(f"{env_key} is not set — run setup_agents.py first", file=sys.stderr)
            return 2

    todo = []
    for lane in LANES:
        for kind in KINDS:
            cached = load_cached(lane, kind)
            if cached and is_fresh(cached, kind):
                log(f"SKIP  {lane.slug(kind)} — cached and fresh")
                continue
            todo.append((lane, kind))

    total = len(todo)
    log(f"{total} run(s) to do across {len(LANES)} lanes (4 concurrent)")
    if not total:
        return 0

    done = failed = 0
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(research, lane, kind): (lane, kind) for lane, kind in todo}
        for fut in as_completed(futures):
            lane, kind = futures[fut]
            try:
                record = fut.result()
                done += 1
                trust = record.get("metadata") or {}
                log(
                    f"OK    {lane.slug(kind)} — {record.get('elapsed_s')}s "
                    f"confidence={trust.get('confidence')} "
                    f"[{done + failed}/{total}]"
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                log(f"FAIL  {lane.slug(kind)} — {type(exc).__name__}: {exc} "
                    f"[{done + failed}/{total}]")

    elapsed = (time.monotonic() - started) / 60
    log(f"finished in {elapsed:.1f} min — {done} ok, {failed} failed")
    if failed:
        log("re-run to retry only the failures (cached successes are skipped)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
