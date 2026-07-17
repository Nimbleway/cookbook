"""Create the three production agents (idempotent via agents.json)."""
import json

import requests

import config as C

H = {"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}

CATALOG_DISCOVERY = {
    "display_name": "AGF Catalog Discovery",
    "description": "Discovers the full catalog of a retail category on one retailer at high recall.",
    "icon": "🛒",
    "use_case": "dataset_building",
    "effort": "high",
    "domain_expertise": """# Retail Catalog Discovery — Domain Expertise

You are a digital-shelf analyst building a complete catalog of products in a retail category on a specific retailer's site.

## Coverage
- The category, subcategory, and retailer come from the prompt. Enumerate category browse pages, search results, and best-seller lists; paginate — do not stop at the first results page.
- Recall targets in the prompt (e.g. 'at least 40 distinct products') are hard minimums; keep expanding subcategories and price points until met.

## Row rules
- One row per distinct product model. Deduplicate color/size variants into one row (keep the most-reviewed variant's URL).
- price_usd, rating, review_count copied verbatim from the product listing as strings. Use null when not shown, never omit the field.
- product_url must be a direct product-detail-page URL on the retailer's site.
- Include source_url (the listing/search page where found) and observed_at (ISO 8601).
- Never invent data - omit a product rather than guess. All numeric-looking fields (price, rating, review counts) are strings copied from the page.""",
    "goals": [
        "Meets the minimum distinct-product count stated in the prompt (e.g. at least 40 distinct products)",
        "Covers the category beyond the first results page - spans subcategories and price points",
        "One row per distinct product model with variants deduplicated",
        "Every row has a direct product_url on the retailer's own site",
        "price_usd, rating, review_count are strings copied from the page; null when not shown, never invented",
        "Every row includes source_url and observed_at (ISO 8601)",
    ],
    "sources": C.AMAZON_SOURCES,
    "output_schema": {
        "type": "array",
        "description": "One row per distinct product in the category on the retailer.",
        "items": {
            "type": "object",
            "required": ["product_name", "brand", "retailer", "product_url", "source_url", "observed_at"],
            "properties": {
                "product_name": {"type": "string"},
                "brand": {"type": "string"},
                "retailer": {"type": "string", "description": "amazon | walmart | target"},
                "subcategory": {"type": ["string", "null"], "description": "e.g. drip, espresso, single-serve, french-press"},
                "price_usd": {"type": ["string", "null"], "description": "Current price as shown, string, e.g. '129.99'"},
                "rating": {"type": ["string", "null"], "description": "Avg star rating as shown, string, e.g. '4.6'"},
                "review_count": {"type": ["string", "null"], "description": "Review count as shown, string, e.g. '12,483'"},
                "product_url": {"type": "string"},
                "source_url": {"type": "string"},
                "observed_at": {"type": "string", "description": "ISO 8601"},
            },
            "additionalProperties": True,
        },
    },
    "suggested_questions": [
        "Coffee makers on amazon.com - at least 40 distinct products across drip, espresso, and single-serve",
        "Espresso machines under $200 on walmart.com - at least 30 distinct products",
        "Single-serve coffee makers on target.com - full catalog",
    ],
}

REVIEW_MINER = {
    "display_name": "AGF Review Miner",
    "description": "Mines recurring review complaint/praise themes with verbatim quotes for known SKUs.",
    "icon": "🔍",
    "use_case": "enrichment",
    "effort": "high",
    "domain_expertise": """# Review Theme Mining — Domain Expertise

You are a consumer-insights analyst mining customer reviews for a known list of products.

## Per product
- Locate the product's page and its customer reviews on the retailer named in the prompt.
- Read enough reviews (prioritize recent + critical) to identify recurring themes, not one-off gripes.
- top_complaints: the 2-4 most recurring negative themes. top_praise: the 2-3 most recurring positive themes.
- representative_quote must be a VERBATIM customer sentence copied from a real review - never paraphrase, never fabricate. source_url is the URL of the review page where the quote appears.
- avg_rating and review_count as strings exactly as shown on the page; null if not shown.
- If a product cannot be found, return its row with found=false and empty theme arrays - never omit a product.""",
    "goals": [
        "Returns one row per product in the input list - never omits a product (found=false when not located)",
        "top_complaints has 2-4 recurring negative themes per found product, each with a verbatim representative_quote and the source_url of the review page",
        "top_praise has 2-3 recurring positive themes per found product with verbatim quotes and source URLs",
        "Quotes are copied verbatim from real customer reviews - never paraphrased or invented",
        "avg_rating and review_count are strings as shown on the page; null when not shown",
    ],
    "sources": {
        "allow": [{"title": "Amazon", "domains": ["amazon.com", "www.amazon.com"], "order": 0}],
        "block": [],
        "avoid": "editorial review blogs and affiliate roundups",
        "prioritize": "the retailer's own customer review pages for the exact product",
    },
    "output_schema": {
        "type": "array",
        "description": "One row per input product.",
        "items": {
            "type": "object",
            "required": ["product_name", "retailer", "found", "top_complaints", "top_praise", "observed_at"],
            "properties": {
                "product_name": {"type": "string"},
                "retailer": {"type": "string"},
                "found": {"type": "boolean"},
                "product_url": {"type": ["string", "null"]},
                "avg_rating": {"type": ["string", "null"]},
                "review_count": {"type": ["string", "null"]},
                "top_complaints": {"type": "array", "items": {"type": "object",
                    "required": ["theme", "representative_quote", "source_url"],
                    "properties": {
                        "theme": {"type": "string"},
                        "theme_frequency_note": {"type": ["string", "null"]},
                        "representative_quote": {"type": "string"},
                        "source_url": {"type": "string"}},
                    "additionalProperties": True}},
                "top_praise": {"type": "array", "items": {"type": "object",
                    "required": ["theme", "representative_quote", "source_url"],
                    "properties": {
                        "theme": {"type": "string"},
                        "representative_quote": {"type": "string"},
                        "source_url": {"type": "string"}},
                    "additionalProperties": True}},
                "observed_at": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "suggested_questions": [
        "Review themes for Ninja DualBrew Pro CFP301 and Keurig K-Elite on amazon.com",
        "Top complaints for Breville Bambino Plus on amazon.com with verbatim quotes",
        "Review themes for Keurig K-Compact and Mr. Coffee 12-Cup on walmart.com",
    ],
}

WHITESPACE_VERIFIER = {
    "display_name": "AGF Whitespace Verifier",
    "description": "Verifies whether a hypothesized assortment gap truly exists on a retailer's live shelf.",
    "icon": "🧭",
    "use_case": "research",
    "effort": "max",
    "domain_expertise": """# Assortment Whitespace Verification — Domain Expertise

You are a merchandising analyst verifying assortment-gap hypotheses against a retailer's live shelf.

## Method
- The prompt states a gap hypothesis, e.g. 'no espresso machine under $150 with an integrated milk frother rated 4.2+ exists on target.com'.
- Search the named retailer's live catalog exhaustively for counterexamples before ruling. A single in-stock counterexample refutes the gap.
- verdict: 'confirmed' (no counterexample found after thorough search), 'refuted' (counterexample found), or 'partial' (near-misses exist; explain the nearest miss).
- closest_matches: the 2-5 products closest to the gap spec, with price, rating, and URL as shown on the page (strings).
- Distinguish 'not found after thorough search' from 'confirmed absent' in the evidence_summary. Never invent products or prices; cite every claim.

## Taught merchandising rules
- Always segment analysis by price band; a gap statement must name its price band.""",
    "goals": [
        "States a verdict of exactly 'confirmed', 'refuted', or 'partial' for the gap hypothesis",
        "Searches the named retailer's live shelf for counterexamples before ruling - never rules from general knowledge",
        "Lists 2-5 closest_matches with price, rating, and a direct product URL, all copied from the page",
        "evidence_summary explains the ruling and distinguishes 'not found after thorough search' from 'confirmed absent'",
        "Every claim carries a source URL; never invents products, prices, or ratings",
    ],
    "sources": {
        "allow": [
            {"title": "Target", "domains": ["target.com", "www.target.com"], "order": 0},
            {"title": "Walmart", "domains": ["walmart.com", "www.walmart.com"], "order": 1},
            {"title": "Amazon", "domains": ["amazon.com", "www.amazon.com"], "order": 2},
        ],
        "block": [],
        "avoid": "affiliate roundups and price aggregators",
        "prioritize": "the retailer named in the hypothesis - its live search and category pages",
    },
    "output_schema": {
        "type": "object",
        "required": ["gap_statement", "verdict", "closest_matches", "evidence_summary", "observed_at"],
        "properties": {
            "gap_statement": {"type": "string"},
            "verdict": {"type": "string", "enum": ["confirmed", "refuted", "partial"]},
            "closest_matches": {"type": "array", "items": {"type": "object",
                "required": ["product_name", "product_url"],
                "properties": {
                    "product_name": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "price_usd": {"type": ["string", "null"]},
                    "rating": {"type": ["string", "null"]},
                    "why_close_but_not_matching": {"type": ["string", "null"]},
                    "product_url": {"type": "string"}},
                "additionalProperties": True}},
            "evidence_summary": {"type": "string"},
            "observed_at": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "suggested_questions": [
        "Verify: no espresso machine under $150 with an integrated milk frother rated 4.2+ exists on target.com",
        "Verify: no 12-cup drip coffee maker with a thermal carafe under $80 exists on walmart.com",
        "Verify: every single-serve machine under $60 on amazon.com has recurring leak complaints",
    ],
}


def create(cfg):
    r = requests.post(f"{C.BASE_URL}/task-agents", headers=H, json=cfg, timeout=120)
    r.raise_for_status()
    return r.json()["id"]


def main():
    if C.AGENTS_FILE.exists():
        print(f"agents.json exists - reusing {json.loads(C.AGENTS_FILE.read_text())}")
        return
    ids = {
        "catalog_discovery": create(CATALOG_DISCOVERY),
        "review_miner": create(REVIEW_MINER),
        "whitespace_verifier": create(WHITESPACE_VERIFIER),
    }
    C.AGENTS_FILE.write_text(json.dumps(ids, indent=2))
    print("created:", ids)


if __name__ == "__main__":
    main()
