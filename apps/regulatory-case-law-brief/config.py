"""Config for Regulatory & Case-Law Brief."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://sdk.nimbleway.com/v1"
NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
HEADERS = {"Authorization": f"Bearer {NIMBLE_API_KEY}"}

APP_DIR = Path(__file__).parent
DATA = APP_DIR / "data"
RAW = DATA / "raw"
BRIEFS = APP_DIR / "briefs"
AGENTS_FILE = APP_DIR / "agents.json"
TOPICS_FILE = DATA / "topics.txt"
for _d in (DATA, RAW, BRIEFS):
    _d.mkdir(parents=True, exist_ok=True)

POLL_SECONDS = 20
RUN_TIMEOUT_S = 2700          # research runs ~10-20 min
CONCURRENCY = int(os.getenv("RCB_CONCURRENCY", "3"))
EFFORT = os.getenv("RCB_EFFORT", "high")
