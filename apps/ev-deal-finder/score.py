"""
Scoring engine for EV deal finder.
Scores each listing on 5 factors, writes deal_score back to listings.json.

Usage:
    python score.py
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "listings.json"

# Weights must sum to 1.0
WEIGHTS = {
    "price":     0.30,
    "mileage":   0.25,
    "year":      0.20,
    "condition": 0.15,
    "safety":    0.10,
}

CONDITION_MAP = {
    "certified pre-owned": 1.0,
    "excellent": 0.95,
    "very good": 0.85,
    "good": 0.75,
    "fair": 0.55,
    "used": 0.70,      # eBay generic "used"
    "remanufactured": 0.50,
    "for parts": 0.10,
}

TITLE_MAP = {
    "clean": 1.0,
    "lien": 0.80,
    "rebuilt": 0.50,
    "salvage": 0.20,
    "parts only": 0.10,
}

def _condition_score(condition_str: str) -> float:
    if not condition_str:
        return 0.65
    c = condition_str.lower()
    for key, score in CONDITION_MAP.items():
        if key in c:
            return score
    return 0.65


def _title_score(title_str: str) -> float:
    if not title_str:
        return 0.80
    t = title_str.lower()
    for key, score in TITLE_MAP.items():
        if key in t:
            return score
    return 0.80


def _relative_score(value: float, lo: float, hi: float, lower_is_better: bool = True) -> float:
    """Score a value against the global min/max across all listings.
    lower_is_better=True: lowest value = 1.0, highest = 0.0 (price, mileage)
    lower_is_better=False: highest value = 1.0, lowest = 0.0 (year)
    """
    if hi == lo:
        return 0.5
    if lower_is_better:
        return max(0.0, min(1.0, 1.0 - (value - lo) / (hi - lo)))
    else:
        return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _clean_condition(condition_str: str) -> str:
    """Trim eBay's verbose condition boilerplate to just the label."""
    if not condition_str:
        return ""
    # eBay format: "Used: A vehicle is considered used..." → "Used"
    label = condition_str.split(":")[0].strip()
    return label if label else condition_str[:30]


def score_listings(listings: list) -> list:
    # Clean condition strings
    for l in listings:
        l["condition"] = _clean_condition(l.get("condition", ""))

    # Compute global min/max for continuous metrics
    prices   = [l["price"]   for l in listings if l.get("price")   and l["price"] > 0]
    mileages = [l["mileage"] for l in listings if l.get("mileage") is not None]
    years    = [l["year"]    for l in listings if l.get("year")]

    price_lo,   price_hi   = min(prices),   max(prices)
    mileage_lo, mileage_hi = min(mileages), max(mileages)
    year_lo,    year_hi    = min(years),    max(years)

    for l in listings:
        p_score = _relative_score(l.get("price") or 0,   price_lo,   price_hi,   lower_is_better=True)
        m_score = _relative_score(l.get("mileage"), mileage_lo, mileage_hi, lower_is_better=True) if l.get("mileage") is not None else 0.5
        y_score = _relative_score(l.get("year") or 0,    year_lo,    year_hi,    lower_is_better=False)
        c_score = _condition_score(l.get("condition", ""))
        s_score = _title_score(l.get("title_status", ""))

        deal = (
            p_score * WEIGHTS["price"]
            + m_score * WEIGHTS["mileage"]
            + y_score * WEIGHTS["year"]
            + c_score * WEIGHTS["condition"]
            + s_score * WEIGHTS["safety"]
        )

        l["price_score"] = round(p_score, 3)
        l["mileage_score"] = round(m_score, 3)
        l["year_score"] = round(y_score, 3)
        l["condition_score"] = round(c_score, 3)
        l["safety_score"] = round(s_score, 3)
        l["deal_score"] = round(deal, 3)

    return listings


def main():
    with open(DATA_FILE) as f:
        listings = json.load(f)

    listings = score_listings(listings)

    with open(DATA_FILE, "w") as f:
        json.dump(listings, f, indent=2)

    print(f"Scored {len(listings)} listings.")
    print("\nTop 5 deals:")
    top = sorted(listings, key=lambda x: x["deal_score"], reverse=True)[:5]
    for l in top:
        print(f"  [{l['deal_score']:.2f}] {l['year']} {l['make']} {l['model']} — ${l['price']:,.0f}, {l.get('mileage','?'):,} mi — {l['city']}, {l['state']}")


if __name__ == "__main__":
    main()
