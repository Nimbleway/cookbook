"""Targeted review mining: SKUs adjacent to candidate gap cells, 4 per run.

Usage: python mine.py           # picks ~10 SKUs from candidate cells, runs, loads Delta
"""
import json
import time
from datetime import datetime, timezone

import config as C
import delta
import gaps
import wsa

PER_RUN = 4
MAX_SKUS = 12


def pick_targets():
    """Top-reviewed SKUs in (or adjacent to) each candidate cell."""
    cands = gaps.candidate_cells()
    if not cands:
        cands = [{"subcat": "espresso", "band": "$50-150"}]  # sane default
    targets, seen = [], set()
    for c in cands:
        _, rows = delta.query(f"""
            SELECT product_name, product_url, sku_key
            FROM {C.DBX_SCHEMA}.catalog
            WHERE {gaps.normalize_subcat_sql()} = ?
            ORDER BY review_count DESC NULLS LAST LIMIT 4""", [c["subcat"]])
        for name, url, key in rows:
            if key not in seen:
                seen.add(key)
                targets.append({"name": name, "url": url, "key": key, "cell": c})
        if len(targets) >= MAX_SKUS:
            break
    return targets[:MAX_SKUS]


def run_batch(agent_id, batch):
    lines = "\n".join(f"- {t['name']} ({t['url']})" for t in batch)
    prompt = (f"Review themes for the following products on amazon.com. For each: the 2-4 most "
              f"recurring complaint themes and 2-3 praise themes with VERBATIM quotes and review-page "
              f"source URLs.\n{lines}")
    run = wsa.start_run(agent_id, prompt)
    result, _ = wsa.wait_for_result(agent_id, run["id"])
    return run["id"], result


def main():
    agent = C.agent_id("review_miner")
    targets = pick_targets()
    print(f"mining {len(targets)} SKUs in batches of {PER_RUN}")
    url_to_key = {t["url"]: t["key"] for t in targets}
    name_to_key = {t["name"].lower(): t["key"] for t in targets}
    theme_rows = []
    for i in range(0, len(targets), PER_RUN):
        batch = targets[i:i + PER_RUN]
        t0 = time.time()
        run_id, result = run_batch(agent, batch)
        (C.RAW_DIR / f"mine_{i // PER_RUN}.json").write_text(json.dumps(
            {"run_id": run_id, "result": result}, indent=1))
        rows = result["output"]["content"]
        for r in rows:
            if not isinstance(r, dict):
                continue
            key = url_to_key.get(r.get("product_url")) or name_to_key.get(
                str(r.get("product_name", "")).lower()) or r.get("product_name")
            for kind, arr in (("complaint", r.get("top_complaints") or []),
                              ("praise", r.get("top_praise") or [])):
                for t in arr:
                    if isinstance(t, dict):
                        theme_rows.append({
                            "sku_key": key, "product_name": r.get("product_name"),
                            "retailer": r.get("retailer", "amazon"),
                            "found": bool(r.get("found", True)), "kind": kind,
                            "theme": t.get("theme"), "quote": t.get("representative_quote"),
                            "quote_source_url": t.get("source_url"), "run_id": run_id,
                            "observed_at": r.get("observed_at")})
        print(f"batch {i // PER_RUN}: {len(rows)} SKUs in {int(time.time() - t0)}s")
    delta.replace_rows("review_themes", theme_rows)
    print(f"loaded {len(theme_rows)} theme rows")


if __name__ == "__main__":
    main()
