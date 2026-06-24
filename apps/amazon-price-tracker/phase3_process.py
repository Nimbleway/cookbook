"""
Phase 3 — Process combined_valid.csv into lean parquet files for the dashboard.

Assigns timestamps: last run = May 14 2026 11:00 AM, each run is 1 hour earlier.
Outputs:
  data/price_history.parquet  — one row per (asin, zip_code, run)
  data/asin_meta.parquet      — one row per asin (stable metadata)
"""

import pandas as pd
from datetime import datetime, timedelta

SRC = "data/combined_valid.csv"
LAST_RUN_TIME = datetime(2026, 5, 14, 11, 0)

COLS = [
    "exec_uuid", "asin", "zip_code", "web_price", "list_price",
    "product_title", "brand", "availability",
    "average_of_reviews", "number_of_reviews", "bought_in_past_month",
    "best_sellers_category_1_name", "best_sellers_category_1_rank",
    "subscribe_and_save", "subscription_price", "image_url",
]

print("Loading columns from CSV...")
df = pd.read_csv(SRC, usecols=COLS, low_memory=False)
print(f"  {len(df):,} rows loaded")

# Assign run_number 1–N based on first appearance of exec_uuid in file order
exec_order = list(dict.fromkeys(df["exec_uuid"]))  # preserves insertion order, deduped
n_runs = len(exec_order)
run_map = {uuid: i + 1 for i, uuid in enumerate(exec_order)}
df["run_number"] = df["exec_uuid"].map(run_map)

# Assign timestamps: run N -> LAST_RUN_TIME - (n_runs - N) hours
df["timestamp"] = df["run_number"].apply(
    lambda n: LAST_RUN_TIME - timedelta(hours=(n_runs - n))
)

print(f"  {n_runs} runs detected")
print(f"  First run: {LAST_RUN_TIME - timedelta(hours=n_runs - 1)}")
print(f"  Last run:  {LAST_RUN_TIME}")

# Clean up prices
df["web_price"] = pd.to_numeric(df["web_price"], errors="coerce")
df["list_price"] = pd.to_numeric(df["list_price"], errors="coerce")
df["subscription_price"] = pd.to_numeric(df["subscription_price"], errors="coerce")
df["average_of_reviews"] = pd.to_numeric(df["average_of_reviews"], errors="coerce")
df["number_of_reviews"] = pd.to_numeric(df["number_of_reviews"], errors="coerce")

# Drop rows with no price
df = df.dropna(subset=["web_price"])
print(f"  {len(df):,} rows after dropping missing prices")

# --- price_history.parquet ---
price_cols = ["asin", "zip_code", "run_number", "timestamp", "web_price",
              "list_price", "availability", "subscription_price"]
ph = df[price_cols].copy()
ph.to_parquet("data/price_history.parquet", index=False)
print(f"Saved data/price_history.parquet ({ph.memory_usage(deep=True).sum() / 1e6:.1f} MB in memory)")

# --- asin_meta.parquet ---
# One stable row per ASIN — take the most recent non-null value for each metadata field
meta_cols = ["asin", "product_title", "brand", "average_of_reviews",
             "number_of_reviews", "bought_in_past_month",
             "best_sellers_category_1_name", "best_sellers_category_1_rank",
             "subscribe_and_save", "image_url"]

meta = (
    df.sort_values("run_number", ascending=False)
      .groupby("asin")[meta_cols[1:]]
      .first()
      .reset_index()
)
meta.columns = meta_cols
meta.to_parquet("data/asin_meta.parquet", index=False)
print(f"Saved data/asin_meta.parquet ({len(meta)} ASINs)")

# --- swing summary for the dashboard leaderboard ---
price_stats = (
    df.groupby("asin")["web_price"]
    .agg(
        price_min="min",
        price_max="max",
        price_mean="mean",
        price_std="std",
        n_obs="count",
    )
    .reset_index()
)
price_stats["swing_abs"] = price_stats["price_max"] - price_stats["price_min"]
price_stats["swing_pct"] = (price_stats["swing_abs"] / price_stats["price_min"] * 100).round(1)
price_stats = price_stats.merge(meta[["asin", "product_title", "brand",
                                      "best_sellers_category_1_name",
                                      "average_of_reviews", "number_of_reviews"]], on="asin")
price_stats = price_stats.sort_values("swing_abs", ascending=False)
price_stats.to_parquet("data/asin_swings.parquet", index=False)
print(f"Saved data/asin_swings.parquet")

# --- zip summary: median price per (asin, zip) ---
zip_stats = (
    df.groupby(["asin", "zip_code"])["web_price"]
    .agg(price_median="median", price_mean="mean", price_std="std", n_obs="count")
    .reset_index()
)
zip_stats.to_parquet("data/zip_stats.parquet", index=False)
print(f"Saved data/zip_stats.parquet")

print("\nDone.")
