import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import anthropic

load_dotenv(find_dotenv(usecwd=False, raise_error_if_not_found=False))
if not os.getenv("ANTHROPIC_API_KEY"):
    load_dotenv(Path(__file__).parent.parent / "ai-consensus" / ".env")
RAW_DIR = Path("data/raw")
OUT_FILE = Path("data/top10_cities.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# --- Parse helpers ---

def parse_price(s):
    if not s:
        return None
    s = s.replace(",", "").replace("$", "").strip()
    if "M" in s:
        return float(s.replace("M", "")) * 1_000_000
    if "K" in s:
        return float(s.replace("K", "")) * 1_000
    try:
        return float(re.sub(r"[^\d.]", "", s))
    except:
        return None

def parse_pct(s):
    if not s:
        return None
    try:
        return float(s.replace("%", "").replace("+", "").strip())
    except:
        return None

def parse_int(s):
    if not s:
        return None
    try:
        return int(s.replace(",", "").strip())
    except:
        return None


# --- Load and parse all raw files ---

records = []
for f in sorted(RAW_DIR.glob("redfin_*.json")):
    data = json.loads(f.read_text())
    r = data.get("data", {}).get("parsing", {})
    url = data.get("url", "")

    city_slug = url.split("/city/")[1].split("/")[2] if "/city/" in url else "Unknown"
    state = url.split("/city/")[1].split("/")[1] if "/city/" in url else "??"
    city_name = city_slug.replace("-", " ")

    records.append({
        "city": city_name,
        "state": state,
        "description": r.get("description", ""),
        "median_price": parse_price(r.get("median_sale_price")),
        "days_on_market": parse_int(r.get("avg_days_on_market")),
        "sale_to_list": parse_pct(r.get("sale_to_list_ratio")),
        "price_per_sqft": parse_price(r.get("median_sale_per_sqft")),
        "homes_sold": parse_int(r.get("num_homes_sold")),
        "yoy_change": parse_pct(r.get("yoy_sale_price_change")),
        "raw": r,
    })

print(f"Loaded {len(records)} cities")


# --- Compute preliminary score to pre-rank ---

def normalize(values, invert=False):
    valid = [v for v in values if v is not None]
    lo, hi = min(valid), max(valid)
    if hi == lo:
        return [0.5 if v is not None else None for v in values]
    normed = [(v - lo) / (hi - lo) if v is not None else None for v in values]
    return [1 - n if (invert and n is not None) else n for n in normed]

yoy_norm      = normalize([r["yoy_change"] for r in records])
stl_norm      = normalize([r["sale_to_list"] for r in records])
dom_norm      = normalize([r["days_on_market"] for r in records], invert=True)
vol_norm      = normalize([r["homes_sold"] for r in records])
price_norm    = normalize([r["median_price"] for r in records], invert=True)

for i, r in enumerate(records):
    components = [yoy_norm[i], stl_norm[i], dom_norm[i], vol_norm[i], price_norm[i]]
    valid = [c for c in components if c is not None]
    weights = [0.30, 0.25, 0.20, 0.15, 0.10]
    score = sum(w * c for w, c in zip(weights, components) if c is not None)
    r["prelim_score"] = round(score, 4)

records.sort(key=lambda r: r["prelim_score"], reverse=True)
top30 = records[:30]

print(f"Pre-ranked. Sending top 30 to Claude for final scoring...\n")


# --- Build Claude prompt ---

city_lines = []
for r in top30:
    city_lines.append(
        f"- {r['city']}, {r['state']}: "
        f"median ${r['median_price']/1000:.0f}K, "
        f"{r['days_on_market']}d on market, "
        f"{r['sale_to_list']:.1f}% sale-to-list, "
        f"{r['yoy_change']:+.1f}% YoY, "
        f"{r['homes_sold']} homes sold. "
        f"{r['description']}"
    )

prompt = """You are a real estate investment analyst. Below are 30 US housing markets ranked by a preliminary composite score (YoY appreciation, sale-to-list ratio, days on market, volume, affordability).

Your job: select the top 10 markets for investment and explain why each one made the cut. Think like an investor — balance appreciation trend, market competitiveness, affordability/entry point, and liquidity. Flag any markets that look good on numbers but have structural risks worth noting.

For each of your top 10, provide:
- City, State
- Investment thesis (2-3 sentences: why this market, what the opportunity is)
- Key risk (1 sentence)

Return your answer as a JSON array:
[
  {
    "rank": 1,
    "city": "Nashville",
    "state": "TN",
    "thesis": "...",
    "risk": "..."
  },
  ...
]

Only return the JSON array, no other text.

Markets to evaluate:
""" + "\n".join(city_lines)


# --- Call Claude ---

client = anthropic.Anthropic()

print("Calling Claude...")
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    messages=[{"role": "user", "content": prompt}]
)

response_text = message.content[0].text.strip()

# Strip markdown code fences if present
if response_text.startswith("```"):
    response_text = re.sub(r"^```[a-z]*\n?", "", response_text)
    response_text = re.sub(r"\n?```$", "", response_text)

top10 = json.loads(response_text)


# --- Enrich with raw metrics and save ---

city_lookup = {(r["city"].lower(), r["state"]): r for r in records}

for entry in top10:
    key = (entry["city"].lower(), entry["state"])
    match = city_lookup.get(key, {})
    entry["median_price"] = match.get("median_price")
    entry["days_on_market"] = match.get("days_on_market")
    entry["sale_to_list"] = match.get("sale_to_list")
    entry["yoy_change"] = match.get("yoy_change")
    entry["homes_sold"] = match.get("homes_sold")
    entry["price_per_sqft"] = match.get("price_per_sqft")
    entry["prelim_score"] = match.get("prelim_score")

OUT_FILE.write_text(json.dumps(top10, indent=2))

print(f"\n=== TOP 10 INVESTMENT MARKETS ===\n")
for entry in top10:
    print(f"#{entry['rank']} {entry['city']}, {entry['state']}")
    print(f"   Price: ${entry['median_price']/1000:.0f}K | {entry['days_on_market']}d | {entry['sale_to_list']:.1f}% STL | {entry['yoy_change']:+.1f}% YoY")
    print(f"   Thesis: {entry['thesis']}")
    print(f"   Risk:   {entry['risk']}")
    print()

print(f"Saved to {OUT_FILE}")
