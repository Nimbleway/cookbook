import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=False, raise_error_if_not_found=False))
if not os.getenv("NIMBLE_API_KEY"):
    load_dotenv(Path(__file__).parent.parent / "ai-consensus" / ".env")

API_KEY = os.getenv("NIMBLE_API_KEY")

AGENT = "zillow_plp"
RAW_DIR = Path("data/raw/zillow")
RAW_DIR.mkdir(parents=True, exist_ok=True)
TIMEOUT_SECONDS = 30

# 3 representative zip codes per top-10 city
# Chosen to cover downtown, mid-city, and a residential neighborhood
CITY_ZIPS = {
    ("Kansas City",   "MO"): ["64108", "64112", "64118"],
    ("Columbus",      "OH"): ["43215", "43201", "43209"],
    ("Philadelphia",  "PA"): ["19103", "19146", "19122"],
    ("Tacoma",        "WA"): ["98402", "98405", "98444"],
    ("Chicago",       "IL"): ["60614", "60618", "60632"],
    ("Reno",          "NV"): ["89501", "89503", "89523"],
    ("San Francisco", "CA"): ["94110", "94117", "94103"],
    ("Virginia Beach","VA"): ["23451", "23462", "23454"],
    ("Albuquerque",   "NM"): ["87102", "87106", "87110"],
    ("Dallas",        "TX"): ["75201", "75205", "75214"],
}


def raw_path(city, zip_code):
    slug = city.replace(" ", "_").lower()
    return RAW_DIR / f"{slug}_{zip_code}.json"


def is_cached(city, zip_code):
    return raw_path(city, zip_code).exists()


def fetch(city, zip_code):
    response = requests.post(
        "https://sdk.nimbleway.com/v1/agents/run",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"agent": AGENT, "params": {"zip_code": zip_code, "listing_type": "sales"}},
        timeout=TIMEOUT_SECONDS,
    )
    data = response.json()
    raw_path(city, zip_code).write_text(json.dumps(data, indent=2))
    results = data.get("data", {}).get("parsing", [])
    return results if isinstance(results, list) else []


def main():
    calls = [(city, state, zip_code)
             for (city, state), zips in CITY_ZIPS.items()
             for zip_code in zips]

    pending = [(city, state, z) for city, state, z in calls if not is_cached(city, z)]
    cached = len(calls) - len(pending)
    total = len(calls)
    print(f"Calls: {total} total | {cached} cached | {len(pending)} to fetch\n")

    summary = []
    total_listings = 0

    for i, (city, state, zip_code) in enumerate(pending, 1):
        label = f"{city}, {state} ({zip_code})"
        print(f"[{i}/{len(pending)}] {label} → fetching...")
        t0 = time.time()

        try:
            listings = fetch(city, zip_code)
            elapsed = time.time() - t0

            if not listings:
                print(f"[{i}/{len(pending)}] ⚠ EMPTY ({elapsed:.1f}s)")
                summary.append((label, "empty", 0))
            else:
                print(f"[{i}/{len(pending)}] ✓ {len(listings)} listings ({elapsed:.1f}s)")
                total_listings += len(listings)
                summary.append((label, "ok", len(listings)))

        except requests.Timeout:
            elapsed = time.time() - t0
            print(f"[{i}/{len(pending)}] ✗ TIMEOUT ({elapsed:.1f}s)")
            summary.append((label, "timeout", 0))
        except Exception as e:
            print(f"[{i}/{len(pending)}] ✗ ERROR: {e}")
            summary.append((label, f"error: {e}", 0))

    ok      = sum(1 for _, s, _ in summary if s == "ok")
    empty   = [(l, n) for l, s, n in summary if s == "empty"]
    timeouts = [l for l, s, _ in summary if s == "timeout"]
    errors  = [(l, s) for l, s, _ in summary if s.startswith("error")]

    print(f"\n=== SUMMARY ===")
    print(f"✓  Success:        {ok}/{len(pending)}")
    print(f"   Total listings: {total_listings}")
    print(f"   Avg per zip:    {total_listings // ok if ok else 0}")
    if empty:
        print(f"⚠  Empty ({len(empty)}):  {', '.join(l for l, _ in empty)}")
    if timeouts:
        print(f"✗  Timeout ({len(timeouts)}): {', '.join(timeouts)}")
    if errors:
        for label, err in errors:
            print(f"✗  {label}: {err}")


if __name__ == "__main__":
    main()
