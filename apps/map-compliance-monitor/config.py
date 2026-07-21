"""Central config for MAP Compliance Monitor."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://sdk.nimbleway.com/v1"
NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")

APP_DIR = Path(__file__).parent
DATA = APP_DIR / "data"
RAW = DATA / "raw"
NOTICES = APP_DIR / "notices"          # local fallback copies of Google Doc notices
DB_PATH = DATA / "mcm.db"
AGENTS_FILE = APP_DIR / "agents.json"
SKUS_CSV = DATA / "skus.csv"

for _d in (DATA, RAW, NOTICES):
    _d.mkdir(parents=True, exist_ok=True)

# --- Orchestration ---
CONCURRENCY = int(os.getenv("MCM_CONCURRENCY", "8"))
POLL_SECONDS = 15
RUN_TIMEOUT_S = 2700                    # per-run watchdog (open-web discovery runs ~15-25 min)
DEFAULT_EFFORT = "high"

# --- Recall (thin-SKU flagging; the max re-run itself is permission-gated) ---
MIN_SELLERS = int(os.getenv("MCM_MIN_SELLERS", "6"))

# Doc/markdown notices are capped to the most severe violations (tracker keeps ALL).
NOTICE_LIMIT = int(os.getenv("MCM_NOTICE_LIMIT", "15"))

# --- Demo mode ---
# Discovery (discover.py) always calls live; USE_LIVE governs the app/dashboard runtime.
USE_LIVE = os.getenv("USE_LIVE", "false").lower() == "true"

# --- Google action layer (gated on creds; local fallback when absent) ---
GOOGLE_SA_JSON = os.getenv("GOOGLE_SA_JSON")            # path to service-account JSON
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")          # existing sheet to write the tracker to
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")  # folder for Doc notices

HEADERS = {"Authorization": f"Bearer {NIMBLE_API_KEY}"}
