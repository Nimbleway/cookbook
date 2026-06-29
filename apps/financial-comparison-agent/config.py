"""Shared configuration and environment loading for the Comps Agent."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Load this app's .env.
load_dotenv(BASE / ".env")

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

MODEL = os.getenv("COMPS_MODEL", "claude-sonnet-4-6")
USE_LIVE = os.getenv("USE_LIVE", "true").lower() in ("1", "true", "yes")

# Nimble brand colors for the dashboard
NIMBLE_YELLOW = "#edc602"
