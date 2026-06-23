import csv
import json
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_FILE = Path("data/asins.csv")
ASINS_PER_CATEGORY = 50

CATEGORIES = [
    "electronics", "grocery", "health", "beauty", "toys",
    "pet-supplies", "sports", "tools", "kitchen", "office",
]

FIELDNAMES = [
    "asin", "category", "rank", "product_name",
    "price", "rating", "review_count",
]


def load_category(label: str) -> list[dict]:
    records = []
    for page in range(1, 4):
        path = RAW_DIR / f"best_sellers_{label}_page{page}.json"
        if not path.exists():
            print(f"  ⚠  missing: {path.name}")
            continue
        data = json.loads(path.read_text())
        results = data.get("data", {}).get("parsing", [])
        for r in results:
            records.append({
                "asin":         r.get("asin", "").strip(),
                "category":     label,
                "rank":         r.get("rank"),
                "product_name": r.get("product_name", "").strip(),
                "price":        r.get("price"),
                "rating":       r.get("rating"),
                "review_count": r.get("review_count"),
            })
    return records


def run():
    seen_asins: set[str] = set()
    all_rows: list[dict] = []
    category_counts: dict[str, int] = {}

    print("Phase 1 — Processing raw files into asins.csv\n")

    for label in CATEGORIES:
        records = load_category(label)

        # Deduplicate within + across categories; keep first by rank
        unique = []
        for r in sorted(records, key=lambda x: x["rank"] or 9999):
            asin = r["asin"]
            if not asin or asin in seen_asins:
                continue
            seen_asins.add(asin)
            unique.append(r)
            if len(unique) == ASINS_PER_CATEGORY:
                break

        category_counts[label] = len(unique)
        all_rows.extend(unique)
        flag = " ⚠" if len(unique) < ASINS_PER_CATEGORY else ""
        print(f"  {label:<16} {len(unique)}/{ASINS_PER_CATEGORY} ASINs{flag}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n── Done {'─' * 42}")
    print(f"  Total ASINs written: {len(all_rows)}")
    print(f"  Output: {OUT_FILE}")

    short = [label for label, n in category_counts.items() if n < ASINS_PER_CATEGORY]
    if short:
        print(f"\n  ⚠  Short categories (< 50): {', '.join(short)}")
        print("     Add more pages or swap in a broader category slug.")


if __name__ == "__main__":
    run()
