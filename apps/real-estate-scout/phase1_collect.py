import os
import json
import time
import csv
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("NIMBLE_API_KEY")

AGENT = "redfin_market_housing_data_community_2026_05_02"
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)
TIMEOUT_SECONDS = 30


def raw_path(city_id):
    return RAW_DIR / f"redfin_{city_id}.json"


def is_cached(city_id):
    return raw_path(city_id).exists()


def fetch(city_id, url_city, url_state):
    response = requests.post(
        "https://sdk.nimbleway.com/v1/agents/run",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"agent": AGENT, "params": {"city_id": city_id, "url_city": url_city, "url_state": url_state}},
        timeout=TIMEOUT_SECONDS,
    )
    data = response.json()
    raw_path(city_id).write_text(json.dumps(data, indent=2))
    return data.get("data", {}).get("parsing", [])


def main():
    with open("cities.csv") as f:
        cities = list(csv.DictReader(f))

    pending = [c for c in cities if not is_cached(c["city_id"])]
    cached = len(cities) - len(pending)
    print(f"Cities: {len(cities)} total | {cached} cached | {len(pending)} to fetch\n")

    summary = []

    for i, city in enumerate(pending, 1):
        label = f"{city['city_name']}, {city['state']}"
        print(f"[{i}/{len(pending)}] {label} → fetching...")
        t0 = time.time()

        try:
            results = fetch(city["city_id"], city["url_city"], city["url_state"])
            elapsed = time.time() - t0

            if not results:
                print(f"[{i}/{len(pending)}] ⚠ EMPTY ({elapsed:.1f}s)")
                summary.append((label, "empty"))
            else:
                print(f"[{i}/{len(pending)}] ✓ {elapsed:.1f}s")
                summary.append((label, "ok"))

        except requests.Timeout:
            elapsed = time.time() - t0
            print(f"[{i}/{len(pending)}] ✗ TIMEOUT ({elapsed:.1f}s)")
            summary.append((label, "timeout"))
        except Exception as e:
            print(f"[{i}/{len(pending)}] ✗ ERROR: {e}")
            summary.append((label, f"error: {e}"))

    ok = sum(1 for _, s in summary if s == "ok")
    empty = [l for l, s in summary if s == "empty"]
    timeouts = [l for l, s in summary if s == "timeout"]
    errors = [(l, s) for l, s in summary if s.startswith("error")]

    print(f"\n=== SUMMARY ===")
    print(f"✓  Success:  {ok}/{len(pending)}")
    if empty:
        print(f"⚠  Empty ({len(empty)}): {', '.join(empty)}")
    if timeouts:
        print(f"✗  Timeout ({len(timeouts)}): {', '.join(timeouts)}")
    if errors:
        print(f"✗  Errors ({len(errors)}):")
        for label, err in errors:
            print(f"     {label}: {err}")


if __name__ == "__main__":
    main()
