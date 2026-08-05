"""Cache code lookups for the demo products so the lookup box works offline.

`USE_LIVE=false` replays these, which keeps the demo free and safe to record. Run
this once (live) after `setup_agents.py`.

    USE_LIVE=true ./.venv/bin/python prefetch_lookups.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk.classify import (  # noqa: E402
    CACHE_DIR, SAMPLE_DIR, find_candidates, slugify, use_live,
)

# The corpus products, plus one deliberately not in the corpus so the lookup can be
# demonstrated on something the desk has never seen.
PRODUCTS = [
    "lithium-ion battery packs",
    "cotton knit t-shirts",
    "aluminium extrusions",
    "photovoltaic solar modules",
    "printed books",
    "stainless steel insulated drinks bottle",
]


def main() -> int:
    if not use_live():
        print("USE_LIVE must be true to prefetch", file=sys.stderr)
        return 2
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for product in PRODUCTS:
        result = find_candidates(product)
        if result.get("error"):
            print(f"FAIL  {product}: {result['error'][:90]}", flush=True)
            failures += 1
            continue
        count = len(result.get("candidates") or [])
        where = "cached" if result.get("from_cache") else f"{result.get('elapsed_s')}s"
        print(f"OK    {product}: {count} candidate(s) ({where})", flush=True)
        src = CACHE_DIR / f"{slugify(product)}.json"
        if src.exists():
            shutil.copy2(src, SAMPLE_DIR / src.name)
    print(f"\n{len(PRODUCTS) - failures}/{len(PRODUCTS)} cached into "
          f"{SAMPLE_DIR.relative_to(HERE)}/")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
