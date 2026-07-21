"""Config for Influencer Finder."""
import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")   # load the app's .env regardless of the process working directory

BASE_URL = "https://sdk.nimbleway.com/v1"
NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
HEADERS = {"Authorization": f"Bearer {NIMBLE_API_KEY}"}
DATA = APP_DIR / "data"
RAW = DATA / "raw"
AGENTS_FILE = APP_DIR / "agents.json"
QUERIES_FILE = DATA / "queries.txt"
for _d in (DATA, RAW):
    _d.mkdir(parents=True, exist_ok=True)

POLL_SECONDS = 20
RUN_TIMEOUT_S = 2700          # dataset_building runs ~10-20 min
CONCURRENCY = int(os.getenv("IF_CONCURRENCY", "3"))
EFFORT = os.getenv("IF_EFFORT", "high")

# Supabase (the store). Falls back to the local cache when unset.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE = "influencers"
