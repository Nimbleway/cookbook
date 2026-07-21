"""Parse raw discovery results → offers, violations, and seller rollup.

Violation logic is DETERMINISTIC and app-side (never LLM-judged):
  a below-MAP violation is advertised_price_num < map_price.
Evidence (price excerpt + source URL) is pulled from trust.claims whose JSON
path targets the row's advertised_price field.
"""
from __future__ import annotations

import csv
from collections import Counter
import json
import re
import sqlite3

import config as C

PRICE_RE = re.compile(r"(\d[\d,]*\.?\d*)")


def parse_price(raw) -> float | None:
    """Deterministically parse a verbatim price string to a float, or None."""
    if raw is None:
        return None
    m = PRICE_RE.search(str(raw).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def load_skus() -> dict:
    with open(C.SKUS_CSV, newline="", encoding="utf-8") as f:
        return {r["sku_id"]: r for r in csv.DictReader(f)}


def claim_evidence(trust: dict) -> dict:
    """Map row index -> {url, excerpt, confidence} from advertised_price claims."""
    out = {}
    for c in trust.get("claims", []) or []:
        path = c.get("path") or ""
        m = re.match(r"\$\[(\d+)\]\.advertised_price", path)
        if not m:
            continue
        idx = int(m.group(1))
        cites = c.get("citations", []) or []
        first = cites[0] if cites else {}
        excerpts = first.get("excerpts") or []
        out[idx] = {
            "evidence_url": first.get("url"),
            "evidence_excerpt": excerpts[0] if excerpts else None,
            "confidence": c.get("confidence"),
        }
    return out


def build():
    skus = load_skus()
    offers, violations = [], []
    per_sku_summary = []

    for sid, meta in skus.items():
        raw_path = C.RAW / f"{sid}.json"
        if not raw_path.exists():
            continue
        payload = json.loads(raw_path.read_text())
        if payload.get("status") != "completed":
            per_sku_summary.append({"sku_id": sid, "status": payload.get("status"), "sellers": 0, "violations": 0})
            continue
        out = (payload.get("result") or {}).get("output", {}) or {}
        rows = out.get("content") if isinstance(out.get("content"), list) else []
        evid = claim_evidence(out.get("trust", {}) or {})
        map_price = parse_price(meta["map_price"])
        seen = set()
        n_viol = 0
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            domain = (row.get("seller_domain") or "").strip().lower().removeprefix("www.")
            url = row.get("listing_url") or ""
            # Include seller name + price so two distinct marketplace sellers sharing one
            # product URL aren't collapsed (only drop truly identical rows).
            sname = (row.get("seller_name") or "").strip().lower()
            price_raw = str(row.get("advertised_price") or "").strip()
            key = (domain, url, sname, price_raw)
            if not domain or key in seen:
                continue
            seen.add(key)
            price_num = parse_price(row.get("advertised_price"))
            e = evid.get(i, {})
            offer = {
                "sku_id": sid, "brand": meta["brand"], "product_name": meta["product_name"], "size": meta["size"],
                "map_price": map_price,
                "seller_name": row.get("seller_name"), "seller_domain": domain,
                "seller_type": row.get("seller_type") or "unknown",
                "advertised_price_raw": row.get("advertised_price"), "advertised_price_num": price_num,
                "currency": row.get("currency"), "in_stock": row.get("in_stock"),
                "listing_url": url, "observed_at": row.get("observed_at"),
                "evidence_url": e.get("evidence_url"), "evidence_excerpt": e.get("evidence_excerpt"),
                "price_confidence": e.get("confidence"),
            }
            offers.append(offer)
            if price_num is not None and map_price is not None and price_num < map_price:
                gap_abs = round(map_price - price_num, 2)
                gap_pct = round(100 * gap_abs / map_price, 1)
                violations.append({**offer, "gap_abs": gap_abs, "gap_pct": gap_pct})
                n_viol += 1
        per_sku_summary.append({"sku_id": sid, "status": "completed", "sellers": len(seen), "violations": n_viol})

    return offers, violations, per_sku_summary


def seller_key(v: dict) -> str:
    """Enforcement identity = the seller DOMAIN. Clean and deterministic; the free-text
    seller_name is too noisy to split reliably (marketplace boilerplate, casing, "sold by"
    phrasings). For independent stores the domain IS the seller; for marketplaces the
    domain is the takedown unit (one Brand Registry complaint), so all 3P listings on a
    marketplace roll up together."""
    return v.get("seller_domain") or ""


def seller_rollup(violations: list[dict]) -> list[dict]:
    """Repeat-offender view: group by seller DOMAIN. Representative name/type = most common
    observed for that domain (useful for independent stores; a marketplace shows its own name)."""
    agg = {}
    for v in violations:
        d = seller_key(v)
        a = agg.setdefault(d, {"seller_domain": d, "names": Counter(), "types": Counter(),
                               "skus": set(), "violation_count": 0, "gap_pcts": []})
        if v.get("seller_name"):
            a["names"][v["seller_name"].strip()] += 1
        if v.get("seller_type"):
            a["types"][v["seller_type"]] += 1
        a["skus"].add(v["sku_id"])
        a["violation_count"] += 1
        a["gap_pcts"].append(v["gap_pct"])
    out = []
    for a in agg.values():
        gaps = a["gap_pcts"]
        out.append({
            "seller_domain": a["seller_domain"],
            "seller_name": a["names"].most_common(1)[0][0] if a["names"] else a["seller_domain"],
            "seller_type": a["types"].most_common(1)[0][0] if a["types"] else "unknown",
            "distinct_skus_violated": len(a["skus"]),
            "violation_count": a["violation_count"],
            "avg_gap_pct": round(sum(gaps) / len(gaps), 1) if gaps else 0,
            "max_gap_pct": max(gaps) if gaps else 0,
        })
    out.sort(key=lambda r: (r["distinct_skus_violated"], r["violation_count"]), reverse=True)
    return out


def write_db(offers, violations):
    con = sqlite3.connect(C.DB_PATH)
    cur = con.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS offers; DROP TABLE IF EXISTS violations;
        CREATE TABLE offers (sku_id TEXT, brand TEXT, product_name TEXT, size TEXT, map_price REAL,
            seller_name TEXT, seller_domain TEXT, seller_type TEXT, advertised_price_raw TEXT,
            advertised_price_num REAL, currency TEXT, in_stock INTEGER, listing_url TEXT, observed_at TEXT,
            evidence_url TEXT, evidence_excerpt TEXT, price_confidence TEXT);
        CREATE TABLE violations (sku_id TEXT, brand TEXT, product_name TEXT, size TEXT, map_price REAL,
            seller_name TEXT, seller_domain TEXT, seller_type TEXT, advertised_price_num REAL,
            gap_abs REAL, gap_pct REAL, listing_url TEXT, evidence_url TEXT, evidence_excerpt TEXT,
            price_confidence TEXT, observed_at TEXT);
    """)
    cur.executemany(
        "INSERT INTO offers VALUES (:sku_id,:brand,:product_name,:size,:map_price,:seller_name,:seller_domain,"
        ":seller_type,:advertised_price_raw,:advertised_price_num,:currency,:in_stock,:listing_url,:observed_at,"
        ":evidence_url,:evidence_excerpt,:price_confidence)", offers)
    cur.executemany(
        "INSERT INTO violations VALUES (:sku_id,:brand,:product_name,:size,:map_price,:seller_name,:seller_domain,"
        ":seller_type,:advertised_price_num,:gap_abs,:gap_pct,:listing_url,:evidence_url,:evidence_excerpt,"
        ":price_confidence,:observed_at)",
        [{k: v.get(k) for k in ("sku_id", "brand", "product_name", "size", "map_price", "seller_name",
          "seller_domain", "seller_type", "advertised_price_num", "gap_abs", "gap_pct", "listing_url",
          "evidence_url", "evidence_excerpt", "price_confidence", "observed_at")} for v in violations])
    con.commit()
    con.close()


def main():
    offers, violations, per_sku = build()
    rollup = seller_rollup(violations)
    (C.DATA / "offers.json").write_text(json.dumps(offers, indent=2))
    (C.DATA / "violations.json").write_text(json.dumps(violations, indent=2))
    (C.DATA / "seller_rollup.json").write_text(json.dumps(rollup, indent=2))
    summary = {
        "skus_processed": sum(1 for s in per_sku if s["status"] == "completed"),
        "total_offers": len(offers),
        "unique_sellers": len({o["seller_domain"] for o in offers}),
        "total_violations": len(violations),
        "sellers_in_violation": len(rollup),
        "top_offender": rollup[0] if rollup else None,
        "per_sku": per_sku,
    }
    (C.DATA / "summary.json").write_text(json.dumps(summary, indent=2))
    write_db(offers, violations)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_sku"}, indent=2, default=str))


if __name__ == "__main__":
    main()
