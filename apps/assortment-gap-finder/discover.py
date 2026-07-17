"""Discovery batch: 6 Amazon chunks -> 300+ SKUs into Delta. Resumable.

Usage: python discover.py [chunk_id ...]   (no args = all chunks not yet on disk)
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import config as C
import delta
import wsa

STOP_TOKENS = re.compile(
    r"\b(black|white|red|silver|stainless(?:\s+steel)?|gray|grey|matte|chrome|"
    r"\d+\s*(?:oz|ounce|cup|cups|pack)|20\d\d)\b")


def sku_key(row):
    """(retailer, canonical id or normalized model name)."""
    url = row.get("product_url") or ""
    m = re.search(r"/dp/([A-Z0-9]{10})", url) or re.search(r"/ip/(\d+)", url) or \
        re.search(r"/A-(\d+)", url)
    if m:
        return f"{row.get('retailer', 'amazon')}:{m.group(1)}"
    name = STOP_TOKENS.sub("", str(row.get("product_name", "")).lower())
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return f"{row.get('retailer', 'amazon')}:{row.get('brand', '')}:{name}".lower()


def parse_num(s, cast=float):
    if s is None:
        return None
    m = re.search(r"[\d,]+(?:\.\d+)?", str(s))
    if not m:
        return None
    try:
        return cast(float(m.group(0).replace(",", "")))
    except ValueError:
        return None


def one_chunk(agent_id, chunk_id, scope, goal):
    out = C.RAW_DIR / f"discover_{chunk_id}.json"
    if out.exists():
        return chunk_id, "skipped (exists)", 0, 0
    prompt = (f"{scope} on amazon.com - at least {goal} distinct products. Cover the whole "
              f"price range and paginate beyond the first results page. Category context: {C.CATEGORY}.")
    for attempt in (1, 2):
        t0 = time.time()
        try:
            run = wsa.start_run(agent_id, prompt, sources=C.AMAZON_SOURCES)
            result, run_final = wsa.wait_for_result(agent_id, run["id"])
            rows = result["output"]["content"]
            out.write_text(json.dumps({"run_id": run["id"], "chunk_id": chunk_id,
                                       "wall_clock_s": int(time.time() - t0),
                                       "result": result}, indent=1))
            return chunk_id, "ok", len(rows), int(time.time() - t0)
        except Exception as e:
            print(f"  ! {chunk_id} attempt {attempt}: {e}", flush=True)
            time.sleep(10)
    return chunk_id, "FAILED after 2 attempts", 0, 0


def load_to_delta():
    """Dedup across all raw chunk files and rewrite the catalog table."""
    best = {}
    run_meta = []
    for f in sorted(C.RAW_DIR.glob("discover_*.json")):
        d = json.loads(f.read_text())
        rows = d["result"]["output"]["content"]
        run_meta.append({"chunk_id": d["chunk_id"], "retailer": "amazon",
                         "subcategory": d["chunk_id"], "run_id": d["run_id"],
                         "status": "completed", "item_count": len(rows),
                         "wall_clock_s": d.get("wall_clock_s"), "error": None,
                         "completed_at": datetime.now(timezone.utc)})
        for r in rows:
            if not isinstance(r, dict) or not r.get("product_name"):
                continue
            k = sku_key(r)
            rc = parse_num(r.get("review_count"), int) or 0
            prev = best.get(k)
            if prev and (parse_num(prev.get("review_count"), int) or 0) >= rc:
                continue
            r["_key"], r["_chunk"], r["_run"] = k, d["chunk_id"], d["run_id"]
            best[k] = r
    catalog = [{
        "sku_key": r["_key"], "product_name": r.get("product_name"),
        "brand": r.get("brand"), "retailer": r.get("retailer", "amazon"),
        "subcategory": r.get("subcategory"),
        "price_usd": parse_num(r.get("price_usd")), "price_raw": r.get("price_usd"),
        "rating": parse_num(r.get("rating")), "rating_raw": r.get("rating"),
        "review_count": parse_num(r.get("review_count"), int),
        "review_count_raw": r.get("review_count"),
        "product_url": r.get("product_url"), "source_url": r.get("source_url"),
        "observed_at": r.get("observed_at"), "chunk_id": r["_chunk"], "run_id": r["_run"],
    } for r in best.values()]
    with delta.connect() as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {C.DBX_SCHEMA}.catalog")
        cur.execute(f"DELETE FROM {C.DBX_SCHEMA}.discovery_runs")
    delta.insert_rows("catalog", catalog)
    delta.insert_rows("discovery_runs", run_meta)
    print(f"catalog: {len(catalog)} distinct SKUs from "
          f"{sum(m['item_count'] for m in run_meta)} raw rows across {len(run_meta)} chunks")


def main():
    agent = C.agent_id("catalog_discovery")
    wanted = sys.argv[1:] or [c[0] for c in C.CHUNKS]
    jobs = [(cid, scope, goal) for cid, scope, goal in C.CHUNKS if cid in wanted]
    print(f"{len(jobs)} chunks (3 concurrent)")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one_chunk, agent, *j) for j in jobs]
        for i, fut in enumerate(as_completed(futures), 1):
            cid, status, n, secs = fut.result()
            print(f"[{i}/{len(jobs)}] {cid}: {status} ({n} items, {secs}s)", flush=True)
    load_to_delta()


if __name__ == "__main__":
    main()
