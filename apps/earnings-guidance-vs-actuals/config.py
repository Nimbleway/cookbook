"""Shared config for Earnings Guidance vs Actuals."""
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

# Mixed 12: 8 big tech + 4 fresh Q2 reporters (Gate 1, 2026-07-16)
WATCHLIST = [
    ("AAPL", "Apple", "Apple's fiscal year ends late September. Apple gives no formal revenue "
     "guidance since FY2020 - guidance is delivered qualitatively on earnings calls "
     "(revenue growth direction, gross margin range, opex range, tax rate); capture those "
     "call outlooks per quarter rather than expecting formal ranges. Cover every requested "
     "quarter even when guidance is sparse."),
    ("MSFT", "Microsoft", "Microsoft's fiscal year ends June 30."),
    ("GOOGL", "Alphabet", ""),
    ("AMZN", "Amazon", ""),
    ("META", "Meta Platforms", ""),
    ("NVDA", "NVIDIA", "NVIDIA's fiscal year ends late January."),
    ("TSLA", "Tesla", "Tesla gives no formal quarterly revenue/EPS guidance - capture delivery growth, margin and capex outlooks."),
    ("NFLX", "Netflix", ""),
    ("JPM", "JPMorgan Chase", "Banks guide full-year NII and expenses rather than quarterly EPS - capture those outlooks."),
    ("GS", "Goldman Sachs", "Banks rarely give formal quarterly guidance - capture whatever forward outlook management gave."),
    ("JNJ", "Johnson & Johnson", "J&J guides FULL-YEAR sales and EPS, updated with each quarterly report. "
     "For each requested quarter, produce a row whose guidance_metrics are the full-year outlook "
     "as restated with the PRIOR quarter's results (label metrics 'FY sales (outlook)', 'FY adjusted EPS (outlook)'), "
     "and whose actual_metrics are that quarter's reported sales and adjusted EPS. "
     "Never return an empty row set - every requested quarter gets a row."),
    ("IBM", "IBM", ""),
]

CHUNKS = {
    "last4": "last 4 REPORTED fiscal quarters",
    "q5to8": "5th through 8th most recently reported fiscal quarters",
}


def agent_id():
    return json.loads(AGENTS_FILE.read_text())["scorecard_agent"]
