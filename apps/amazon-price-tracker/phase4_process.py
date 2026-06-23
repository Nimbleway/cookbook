"""
Phase 4 — Extract non-price signals from combined_valid.csv.

Outputs:
  data/signals_history.parquet  — (asin, run_number): bsr, availability, list_price, s&s, demand
  data/title_changes.parquet    — title change events with BSR context
  data/signal_alerts.parquet    — multi-signal change events per run transition
  data/oos_summary.parquet      — per-ASIN OOS rate and availability stats
"""
import pandas as pd
from datetime import datetime, timedelta

SRC = "data/combined_valid.csv"
LAST_RUN_TIME = datetime(2026, 5, 14, 11, 0)

COLS = [
    "exec_uuid", "asin", "zip_code",
    "availability", "list_price",
    "subscribe_and_save", "bought_in_past_month",
    "best_sellers_category_1_rank", "best_sellers_category_1_name",
    "product_title",
]

print("Loading columns...")
df = pd.read_csv(SRC, usecols=COLS, low_memory=False)
print(f"  {len(df):,} rows")

# ── Run numbering (same as phase3) ────────────────────────────────────────────
exec_order = list(dict.fromkeys(df["exec_uuid"]))
n_runs = len(exec_order)
run_map = {uuid: i + 1 for i, uuid in enumerate(exec_order)}
df["run_number"] = df["exec_uuid"].map(run_map)
df["timestamp"] = df["run_number"].apply(
    lambda n: LAST_RUN_TIME - timedelta(hours=(n_runs - n))
)
print(f"  {n_runs} runs")

# ── Type cleanup ──────────────────────────────────────────────────────────────
df["list_price"] = pd.to_numeric(df["list_price"], errors="coerce")
df["best_sellers_category_1_rank"] = pd.to_numeric(
    df["best_sellers_category_1_rank"], errors="coerce"
)

# Availability: normalize multiple possible representations
avail_str = df["availability"].astype(str).str.strip().str.lower()
df["is_available"] = avail_str.isin(["true", "1", "yes", "in stock", "available"])

# subscribe_and_save: coerce to bool
ss_str = df["subscribe_and_save"].astype(str).str.strip().str.lower()
df["ss_on"] = ss_str.isin(["true", "1", "yes"])

# ── signals_history.parquet ───────────────────────────────────────────────────
# One row per (asin, run_number) — aggregate across 10 zip codes
# BSR, title, list_price are the same across zips (take first non-null)
# availability: True if available in ANY zip
# ss_on: True if S&S available in ANY zip
print("Building signals history...")

def first_nonnull(s):
    s = s.dropna()
    return s.iloc[0] if len(s) > 0 else None

sig = (
    df.groupby(["asin", "run_number"])
    .agg(
        timestamp=("timestamp", "first"),
        bsr_rank=("best_sellers_category_1_rank", first_nonnull),
        bsr_name=("best_sellers_category_1_name", first_nonnull),
        list_price=("list_price", first_nonnull),
        subscribe_and_save=("ss_on", "any"),
        bought_in_past_month=("bought_in_past_month", first_nonnull),
        product_title=("product_title", first_nonnull),
        is_available=("is_available", "any"),
        n_available_zips=("is_available", "sum"),
    )
    .reset_index()
)
sig["bsr_rank"] = pd.to_numeric(sig["bsr_rank"], errors="coerce")
sig["list_price"] = pd.to_numeric(sig["list_price"], errors="coerce")
sig.to_parquet("data/signals_history.parquet", index=False)
print(f"  Saved signals_history.parquet ({len(sig):,} rows, {sig['asin'].nunique()} ASINs)")

# ── title_changes.parquet ─────────────────────────────────────────────────────
print("Finding title changes...")
sig_sorted = sig.sort_values(["asin", "run_number"])
title_changes = []

for asin, grp in sig_sorted.groupby("asin"):
    grp = grp.dropna(subset=["product_title"]).reset_index(drop=True)
    if len(grp) < 2:
        continue
    for i in range(1, len(grp)):
        prev = grp.iloc[i - 1]
        curr = grp.iloc[i]
        old_t = str(prev["product_title"]).strip()
        new_t = str(curr["product_title"]).strip()
        if old_t != new_t:
            title_changes.append({
                "asin": asin,
                "run_number": int(curr["run_number"]),
                "timestamp": curr["timestamp"],
                "old_title": old_t,
                "new_title": new_t,
                "bsr_before": prev["bsr_rank"],
                "bsr_after": curr["bsr_rank"],
            })

tc = pd.DataFrame(title_changes) if title_changes else pd.DataFrame(
    columns=["asin","run_number","timestamp","old_title","new_title","bsr_before","bsr_after"]
)
if len(tc) > 0:
    tc["bsr_delta"] = pd.to_numeric(tc["bsr_after"], errors="coerce") - \
                      pd.to_numeric(tc["bsr_before"], errors="coerce")
    meta = pd.read_parquet("data/asin_meta.parquet")[["asin", "brand", "image_url"]]
    tc = tc.merge(meta, on="asin", how="left")
tc.to_parquet("data/title_changes.parquet", index=False)
print(f"  Saved title_changes.parquet ({len(tc)} events)")

# ── oos_summary.parquet ───────────────────────────────────────────────────────
# oos_runs  = runs where ANY zip was unavailable (n_available_zips < 10)
# fully_oos = runs where ALL zips were unavailable (n_available_zips == 0)
print("Building OOS summary...")
oos = (
    sig.groupby("asin")
    .agg(
        total_runs=("run_number", "count"),
        oos_runs=("n_available_zips", lambda x: (x < 10).sum()),
        fully_oos_runs=("n_available_zips", lambda x: (x == 0).sum()),
        last_available=("is_available", "last"),
    )
    .reset_index()
)
oos["oos_rate"]       = (oos["oos_runs"]       / oos["total_runs"] * 100).round(1)
oos["fully_oos_rate"] = (oos["fully_oos_runs"] / oos["total_runs"] * 100).round(1)
meta = pd.read_parquet("data/asin_meta.parquet")[["asin", "product_title", "brand"]]
oos = oos.merge(meta, on="asin", how="left").sort_values("oos_rate", ascending=False)
oos.to_parquet("data/oos_summary.parquet", index=False)
print(f"  Saved oos_summary.parquet ({len(oos)} ASINs, "
      f"{int((oos['oos_rate'] > 0).sum())} with any OOS, "
      f"{int((oos['fully_oos_rate'] > 0).sum())} fully OOS)")

# ── signal_alerts.parquet ─────────────────────────────────────────────────────
# Per-run-transition events where multiple signals changed simultaneously
print("Finding multi-signal events...")
# Merge with price swings to detect web_price changes
ph = pd.read_parquet("data/price_history.parquet")[["asin", "run_number", "web_price"]]
# median web_price per (asin, run_number) across all zips
ph_med = ph.groupby(["asin", "run_number"])["web_price"].median().reset_index()
ph_med.rename(columns={"web_price": "web_price_med"}, inplace=True)
sig2 = sig.merge(ph_med, on=["asin", "run_number"], how="left")
sig2 = sig2.sort_values(["asin", "run_number"])

events = []
for asin, grp in sig2.groupby("asin"):
    grp = grp.reset_index(drop=True)
    for i in range(1, len(grp)):
        prev, curr = grp.iloc[i - 1], grp.iloc[i]
        changed = []

        # Web price change > 1%
        if pd.notna(prev["web_price_med"]) and pd.notna(curr["web_price_med"]) and prev["web_price_med"] > 0:
            pct = abs(curr["web_price_med"] - prev["web_price_med"]) / prev["web_price_med"] * 100
            if pct >= 1:
                changed.append(f"price &#36;{prev['web_price_med']:.2f}→&#36;{curr['web_price_med']:.2f}")

        # BSR moved >= 20 positions
        if pd.notna(prev["bsr_rank"]) and pd.notna(curr["bsr_rank"]):
            delta = int(curr["bsr_rank"]) - int(prev["bsr_rank"])
            if abs(delta) >= 20:
                arrow = "↑" if delta < 0 else "↓"
                changed.append(f"BSR #{int(prev['bsr_rank'])}→#{int(curr['bsr_rank'])} {arrow}")

        # Availability flip
        if bool(prev["is_available"]) != bool(curr["is_available"]):
            changed.append("OOS→back" if curr["is_available"] else "→OOS")

        # Title change
        old_t = str(prev.get("product_title") or "").strip()
        new_t = str(curr.get("product_title") or "").strip()
        if old_t and new_t and old_t != new_t:
            changed.append("title changed")

        # List price change > $0.50
        if pd.notna(prev["list_price"]) and pd.notna(curr["list_price"]):
            if abs(curr["list_price"] - prev["list_price"]) > 0.50:
                changed.append(f"MSRP &#36;{prev['list_price']:.2f}→&#36;{curr['list_price']:.2f}")

        # S&S toggled
        if bool(prev["subscribe_and_save"]) != bool(curr["subscribe_and_save"]):
            changed.append("S&amp;S toggled")

        if len(changed) >= 2:
            events.append({
                "asin": asin,
                "run_number": int(curr["run_number"]),
                "timestamp": curr["timestamp"],
                "n_signals": len(changed),
                "signals": " · ".join(changed),
            })

alerts = pd.DataFrame(events) if events else pd.DataFrame(
    columns=["asin","run_number","timestamp","n_signals","signals"]
)
if len(alerts) > 0:
    meta2 = pd.read_parquet("data/asin_meta.parquet")[["asin", "product_title", "brand"]]
    alerts = alerts.merge(meta2, on="asin", how="left")
    alerts = alerts.sort_values(["n_signals", "asin", "run_number"], ascending=[False, True, True])
alerts.to_parquet("data/signal_alerts.parquet", index=False)
print(f"  Saved signal_alerts.parquet ({len(alerts)} events, "
      f"{alerts['asin'].nunique() if len(alerts) > 0 else 0} ASINs)")

print("\nDone.")
