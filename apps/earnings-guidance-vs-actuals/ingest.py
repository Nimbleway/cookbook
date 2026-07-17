"""Ingest raw backfill JSONs into the Snowflake ledger (idempotent MERGEs).

Usage: python ingest.py            # ingest everything in data/raw/
       python ingest.py NVDA_last4 # specific files
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

import config as C
from setup_snowflake import connect

DB = None  # set in main from env

MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12,
        "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


_YEAR_TOKENS = re.compile(r"\b(?:fy\s*)?(?:19|20)\d{2}\b")


def _strip_years(t):
    """Calendar years in labels ('full-year 2024', 'FY2026') must never parse as values."""
    return _YEAR_TOKENS.sub(" ", t)


def parse_money(text):
    """'$26.0B', '$45.0 billion', '68.9', '23,5' -> float or None. Deterministic, no LLM."""
    if not text:
        return None
    t = _strip_years(str(text).lower().replace(",", "")).strip()
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:(k|m|b|t|thousand|million|billion|trillion)\b)?", t)
    if not m:
        return None
    val = float(m.group(1))
    if m.group(2):
        val *= MULT[m.group(2)]
    if "%" in t:
        return val  # percentages stay as the raw number
    return val


def parse_range(guided_value, guided_range):
    """Return (low, mid, high) from the guided strings."""
    src = guided_range or guided_value or ""
    t = _strip_years(str(src).lower().replace(",", ""))
    # range dashes ("46.5%-47.5%", "$26.0b–$26.5b") must not read as negative signs
    t = re.sub(r"(?<=[\d%kmbt])\s*[-–—]\s*(?=\$?\d)", " to ", t)
    pm = re.search(r"(-?\d+(?:\.\d+)?)\s*(k|m|b|t|thousand|million|billion|trillion)?\s*(?:%|percent)?\s*(?:,)?\s*(?:plus or minus|\+/-|±)\s*(\d+(?:\.\d+)?)\s*%", t)
    if pm:
        mid = float(pm.group(1)) * (MULT.get(pm.group(2)) or 1)
        pct = float(pm.group(3)) / 100
        return mid * (1 - pct), mid, mid * (1 + pct)
    nums = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:(k|m|b|t|thousand|million|billion|trillion)\b)?", t)
    vals = [float(n) * (MULT.get(u) or 1) for n, u in nums if n]
    if len(vals) >= 2 and any(sep in t for sep in ("-", "–", " to ")):
        lo, hi = min(vals[0], vals[1]), max(vals[0], vals[1])
        return lo, (lo + hi) / 2, hi
    v = parse_money(guided_value) or (vals[0] if vals else None)
    return (v, v, v) if v is not None else (None, None, None)


def norm_metric(name):
    n = re.sub(r"\(.*?\)", "", str(name)).strip().lower()
    n = n.replace("total ", "")
    return {"revenues": "revenue", "net revenue": "revenue", "sales": "revenue"}.get(n, n)


def metric_verdict(low, high, actual):
    if actual is None or low is None:
        return "not_guided"
    # units guard: percent-scale guidance ("+2.5% YoY growth") vs dollar-scale actual
    # (or vice versa) cannot be graded - magnitudes off by >1000x are a scale mismatch
    ref = max(abs(low), abs(high or low))
    if ref > 0 and abs(actual) > 0 and (abs(actual) / ref > 50 or ref / abs(actual) > 50):
        return "not_guided"
    if actual > high:
        return "beat"
    if actual < low:
        return "miss"
    return "inline"


def unwrap(v):
    """Annotated-output form: {'@value': x, '@citation': [...]} -> x."""
    return v.get("@value") if isinstance(v, dict) and "@value" in v else v


def norm_obj(m):
    """Normalize a metric entry: JSON-encoded strings and @value/@citation wrappers.
    Returns a plain dict or None if unparseable."""
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(m, dict):
        return None
    out, cite_url = {}, None
    for k, v in m.items():
        if isinstance(v, dict) and "@value" in v:
            out[k] = v["@value"]
            cits = v.get("@citation") or []
            cite_url = cite_url or next(
                (c.get("url") for c in cits if str(c.get("url", "")).startswith("https://")), None)
        else:
            out[k] = v
    if cite_url and not str(out.get("source_url", "")).startswith("https://"):
        out["source_url"] = cite_url
    return out


def rows_from_file(path):
    d = json.loads(path.read_text())
    result = d["result"]
    content = result["output"]["content"]
    trust = result["output"].get("trust") or {}   # NOTE: trust lives under output
    claims = trust.get("claims") or []

    # claim lookup by json path -> best citation url + excerpt
    claim_by_path = {}
    for cl in claims:
        cits = cl.get("citations") or []
        url = next((c.get("url") for c in cits if str(c.get("url", "")).startswith("https://")), None)
        claim_by_path[cl.get("path", "")] = {
            "confidence": cl.get("confidence"), "reasoning": cl.get("reasoning"),
            "url": url, "title": (cits[0].get("title") if cits else None),
            "excerpt": (cits[0].get("excerpts") or [None])[0] if cits and isinstance(cits[0].get("excerpts"), list) else None,
        }

    def repaired_url(in_schema_url, path):
        if str(in_schema_url or "").startswith("https://"):
            return in_schema_url
        cl = claim_by_path.get(path)
        return (cl and cl["url"]) or in_schema_url

    ledger_rows, claim_rows = [], []
    for qi, q in enumerate(content):
        if not isinstance(q, dict):
            continue
        actual_list = [n for n in (norm_obj(m) for m in q.get("actual_metrics") or []) if n and n.get("metric")]
        guidance_list = [n for n in (norm_obj(m) for m in q.get("guidance_metrics") or []) if n and n.get("metric")]
        actuals = {norm_metric(m["metric"]): (m, mi) for mi, m in enumerate(actual_list)}
        seen_keys = set()
        for gi, g in enumerate(guidance_list):
            key = norm_metric(g["metric"])
            act, act_i = actuals.get(key, (None, None))
            if key in seen_keys:  # e.g. quarterly capex + full-year capex in one quarter
                key = str(g["metric"]).strip().lower()
            seen_keys.add(key)
            low, mid, high = parse_range(g.get("guided_value"), g.get("guided_range"))
            actual_num = parse_money(act.get("actual_value")) if act else None
            verdict = metric_verdict(low, high, actual_num)
            if verdict == "not_guided" and low is not None and actual_num is not None:
                # scale mismatch (e.g. percent guidance on a dollar metric): the raw
                # strings keep the record, but numeric columns must not enable bogus math
                low = mid = high = None
            gpath = f"$[{qi}].guidance_metrics[{gi}].guided_value"
            apath = f"$[{qi}].actual_metrics[{act_i}].actual_value" if act_i is not None else gpath
            ledger_rows.append({
                "ticker": d["ticker"], "fiscal_quarter": q["fiscal_quarter"],
                "report_date": q.get("report_date"), "metric": key, "metric_raw": g["metric"],
                "guided_value_raw": g.get("guided_value"), "guided_range_raw": g.get("guided_range"),
                "guided_low": low, "guided_mid": mid, "guided_high": high,
                "actual_value_raw": act.get("actual_value") if act else None,
                "actual_value_num": actual_num,
                "metric_verdict": verdict,
                "quarter_verdict": q.get("verdict"), "notes": q.get("notes"),
                "guidance_source_url": repaired_url(g.get("source_url"), gpath),
                "actual_source_url": repaired_url(act.get("source_url"), apath) if act else None,
                "run_id": d["run_id"],
            })
        # keep actuals that had no guidance partner (e.g. total revenue reported
        # against segment-level guidance) - the headline view pairs them
        guided_keys = {norm_metric(g["metric"]) for g in guidance_list}
        for ai, a in enumerate(actual_list):
            key = norm_metric(a["metric"])
            if key in guided_keys:
                continue
            if key in seen_keys:
                key = str(a["metric"]).strip().lower()
            seen_keys.add(key)
            apath = f"$[{qi}].actual_metrics[{ai}].actual_value"
            ledger_rows.append({
                "ticker": d["ticker"], "fiscal_quarter": q["fiscal_quarter"],
                "report_date": q.get("report_date"), "metric": key, "metric_raw": a["metric"],
                "guided_value_raw": None, "guided_range_raw": None,
                "guided_low": None, "guided_mid": None, "guided_high": None,
                "actual_value_raw": a.get("actual_value"),
                "actual_value_num": parse_money(a.get("actual_value")),
                "metric_verdict": "not_guided",
                "quarter_verdict": q.get("verdict"), "notes": q.get("notes"),
                "guidance_source_url": None,
                "actual_source_url": repaired_url(a.get("source_url"), apath),
                "run_id": d["run_id"],
            })
    for cl_path, cl in claim_by_path.items():
        claim_rows.append({
            "claim_id": hashlib.md5(f"{d['run_id']}|{cl_path}".encode()).hexdigest(),
            "run_id": d["run_id"], "ticker": d["ticker"], "json_path": cl_path,
            "confidence": cl["confidence"], "reasoning": cl["reasoning"],
            "citation_url": cl["url"], "citation_title": cl["title"], "excerpt": cl["excerpt"],
        })
    run_row = {
        "run_id": d["run_id"], "interaction_id": d.get("interaction_id"),
        "ticker": d["ticker"], "quarter_window": d["window"], "status": "completed",
        "effort": "high", "overall_confidence": trust.get("confidence"),
        "completed_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "wall_clock_s": d.get("wall_clock_s"), "raw_result": json.dumps(result),
    }
    return run_row, ledger_rows, claim_rows


def merge(cur, table, rows, key_cols):
    """Batch MERGE: executemany into a temp table, then one MERGE statement."""
    if not rows:
        return
    cols = list(rows[0].keys())
    tmp = f"TMP_{table}"
    cur.execute(f"CREATE TEMPORARY TABLE IF NOT EXISTS {DB}.LEDGER.{tmp} LIKE {DB}.LEDGER.{table}")
    cur.execute(f"TRUNCATE TABLE {DB}.LEDGER.{tmp}")
    select_cols = ", ".join(
        f"PARSE_JSON(column{i+1})" if c == "raw_result" else f"column{i+1}"
        for i, c in enumerate(cols))
    placeholders = ", ".join(["%s"] * len(cols))
    cur.executemany(
        f"INSERT INTO {DB}.LEDGER.{tmp} ({', '.join(cols)}) "
        f"SELECT {select_cols} FROM VALUES ({placeholders})",
        [[row[c] for c in cols] for row in rows])
    on = " AND ".join(f"EQUAL_NULL(t.{k}, s.{k})" for k in key_cols)
    sets = ", ".join(f"t.{c} = s.{c}" for c in cols if c not in key_cols)
    cur.execute(f"MERGE INTO {DB}.LEDGER.{table} t USING {DB}.LEDGER.{tmp} s ON {on} "
                f"WHEN MATCHED THEN UPDATE SET {sets} "
                f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) "
                f"VALUES ({', '.join('s.' + c for c in cols)})")


def main():
    global DB
    import os
    DB = os.environ.get("SNOWFLAKE_DATABASE", "EARNINGS_DESK")
    names = sys.argv[1:]
    files = sorted(C.RAW_DIR.glob("*.json"))
    if names:
        files = [f for f in files if f.stem in names]
    conn = connect()
    cur = conn.cursor()
    total_l = total_c = 0
    for f in files:
        run_row, ledger_rows, claim_rows = rows_from_file(f)
        quarters = {r["fiscal_quarter"] for r in ledger_rows}
        if len(quarters) < 4 or not ledger_rows:
            print(f"!! {f.stem}: DEGRADED RUN ({len(quarters)} quarters, {len(ledger_rows)} rows) "
                  f"- delete data/raw/{f.stem}.json and re-run backfill for this chunk")
        merge(cur, "RUNS", [run_row], ["run_id"])
        merge(cur, "GUIDANCE_LEDGER", ledger_rows, ["ticker", "fiscal_quarter", "metric"])
        merge(cur, "CLAIMS", claim_rows, ["claim_id"])
        total_l += len(ledger_rows); total_c += len(claim_rows)
        print(f"{f.stem}: {len(ledger_rows)} ledger rows, {len(claim_rows)} claims")
    conn.commit(); conn.close()
    print(f"done: {total_l} ledger rows, {total_c} claims across {len(files)} files")


if __name__ == "__main__":
    main()
