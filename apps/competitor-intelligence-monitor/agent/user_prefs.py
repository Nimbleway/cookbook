import json
from pathlib import Path
from datetime import datetime

PREFS_FILE = Path(__file__).parent / "user_prefs.json"


def load_all_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text()) if PREFS_FILE.exists() else {}
    except Exception as e:
        print(f"[Prefs] Load error: {e}")
        return {}


def save_prefs(slack_user_id: str, prefs: dict) -> None:
    all_prefs = load_all_prefs()
    prefs["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_prefs[slack_user_id] = prefs
    PREFS_FILE.write_text(json.dumps(all_prefs, indent=2))
