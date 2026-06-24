import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NIMBLE_API_KEY")
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

PAGES_PER_CATEGORY = 3
TIMEOUT_SECONDS = 60

CATEGORIES = {
    "electronics":   "electronics",
    "grocery":       "grocery",
    "health":        "hpc",
    "beauty":        "beauty",
    "toys":          "toys-and-games",
    "pet-supplies":  "pet-supplies",
    "sports":        "sporting-goods",
    "tools":         "hi",
    "kitchen":       "kitchen",
    "office":        "office-products",
}


def raw_path(label: str, page: int) -> Path:
    return RAW_DIR / f"best_sellers_{label}_page{page}.json"


def fetch(label: str, slug: str, page: int) -> list:
    response = requests.post(
        "https://sdk.nimbleway.com/v1/agents/run",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"agent": "amazon_best_sellers", "params": {"category": slug, "page": page}},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("data", {}).get("parsing", [])
    raw_path(label, page).write_text(json.dumps(data, indent=2))
    return results


def run():
    calls = [
        (label, slug, page)
        for label, slug in CATEGORIES.items()
        for page in range(1, PAGES_PER_CATEGORY + 1)
    ]
    total = len(calls)

    stats = {"ok": 0, "cached": 0, "timeout": 0, "error": 0}
    category_counts: dict[str, int] = {label: 0 for label in CATEGORIES}

    print(f"Phase 1 — Collecting Amazon Best Sellers ({total} calls)\n")

    for n, (label, slug, page) in enumerate(calls, 1):
        path = raw_path(label, page)

        if path.exists():
            cached = json.loads(path.read_text())
            count = len(cached.get("data", {}).get("results", []))
            print(f"[{n:2}/{total}] {label}/page{page} → cached ({count} results)")
            stats["cached"] += 1
            category_counts[label] += count
            continue

        print(f"[{n:2}/{total}] {label}/page{page} → fetching...", end=" ", flush=True)
        t0 = time.time()

        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(fetch, label, slug, page)
                results = future.result(timeout=TIMEOUT_SECONDS + 5)

            elapsed = time.time() - t0
            count = len(results)

            if count == 0:
                print(f"⚠  0 results ({elapsed:.1f}s) ← EMPTY — investigate")
                stats["error"] += 1
            else:
                print(f"✓  {count} results ({elapsed:.1f}s)")
                stats["ok"] += 1
                category_counts[label] += count

        except TimeoutError:
            elapsed = time.time() - t0
            print(f"✗  TIMEOUT ({elapsed:.0f}s)")
            stats["timeout"] += 1

        except Exception as e:
            elapsed = time.time() - t0
            print(f"✗  ERROR ({elapsed:.1f}s): {e}")
            stats["error"] += 1

    print(f"\n── Phase 1 Complete {'─' * 36}")
    print(f"  {total} calls: {stats['ok']} ✓  {stats['cached']} cached  "
          f"{stats['timeout']} timeout  {stats['error']} error")
    print("\n  Results per category:")
    for label, count in category_counts.items():
        flag = " ⚠" if count < 50 else ""
        print(f"    {label:<16} {count} results{flag}")


if __name__ == "__main__":
    run()
