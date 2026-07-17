"""Shared config for Assortment Gap Finder."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

BASE_URL = "https://sdk.nimbleway.com/v1"
NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY", "")
USE_LIVE = os.getenv("USE_LIVE", "true").lower() == "true"

RAW_DIR = APP_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = APP_DIR / "data" / "sample_run"
AGENTS_FILE = APP_DIR / "agents.json"

CATEGORY = "coffee makers"

# Gate-1 simplified: Amazon-only discovery, 6 subcategory chunks -> 300+ SKUs after dedup.
# Walmart/Target participate at the verification stage (live-shelf counterexample search).
CHUNKS = [
    ("amz-drip", "drip coffee makers", 50),
    ("amz-espresso", "espresso machines", 50),
    ("amz-single-serve", "single-serve and pod coffee makers", 50),
    ("amz-specialty", "french press, pour-over, and moka pot coffee makers", 40),
    ("amz-cold-brew", "cold brew and iced coffee makers", 40),
    ("amz-combo", "grind-and-brew combo machines and dual coffee makers", 40),
]

AMAZON_SOURCES = {
    "allow": [{"title": "Amazon", "domains": ["amazon.com", "www.amazon.com"], "order": 0}],
    "block": [],
    "avoid": "third-party price aggregators and review blogs",
    "prioritize": "retailer category browse pages, search results, and best-seller lists",
}

PRICE_BANDS = [(0, 50, "<$50"), (50, 150, "$50-150"), (150, 400, "$150-400"), (400, 10**9, "$400+")]

# Databricks
DBX_HOST = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
DBX_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH", "")
DBX_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
DBX_CATALOG = os.getenv("DATABRICKS_CATALOG", "main")
if not __import__("re").match(r"^[A-Za-z0-9_]+$", DBX_CATALOG):
    raise ValueError(f"DATABRICKS_CATALOG must be a plain identifier, got: {DBX_CATALOG!r}")
DBX_SCHEMA = f"{DBX_CATALOG}.assortment_gap_finder"


def agent_id(name):
    return json.loads(AGENTS_FILE.read_text())[name]
