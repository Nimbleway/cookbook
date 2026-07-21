"""Canonical production agent config — the exact config validated in the design smoke run.

One dataset_building agent: open-web discovery of every seller of one exact SKU,
with advertised price + cited evidence. Sources use EMPTY-domain category groups
only (steering, not a host whitelist) so long-tail/unauthorized sellers surface.
"""

SELLER_DISCOVERY = {
    "display_name": "MCM Seller Discovery",
    "description": "Open-web discovery of every seller of one exact SKU, with advertised price + cited evidence.",
    "icon": "🛡️",
    "use_case": "dataset_building",
    "effort": "high",
    "domain_expertise": """# MAP Seller Discovery — Domain Expertise

You are a brand-protection analyst building a complete map of every online seller
offering one exact product SKU, so the brand can enforce its Minimum Advertised Price.

## Where to search — cast the widest net
- The exact SKU comes from the prompt (brand + product + size/variant). Find EVERY
  distinct seller offering it for sale online, not just the well-known retailers.
- Deliberately go beyond Amazon and Walmart: marketplace third-party sellers
  (Amazon 3P, eBay, Walmart Marketplace), Google Shopping listings, independent
  beauty/hair e-commerce stores, discounters/overstock sites, and salon/pro sites.
- The long-tail independent and marketplace sellers are the MOST important to find —
  they are where Minimum Advertised Price violations concentrate. Do not stop at the
  obvious names.

## SKU matching
- Match the EXACT product and size/variant named in the prompt. Do not include a
  different size, a bundle, or a different product as the same SKU — note size in
  the row if it differs.

## Row rules — one row per distinct seller offer
- seller_name and seller_domain (bare hostname, e.g. beautystore.com — no https://).
- advertised_price: the price shown on the listing, copied VERBATIM as a string
  (e.g. "23.99"). currency as shown (e.g. "USD"). Never compute or estimate a price.
- listing_url: the direct product/offer URL on that seller (never a search page).
- seller_type: one of authorized_retailer | marketplace_third_party |
  independent_store | discounter | unknown — your best evidence-based guess.
- in_stock: true/false when determinable, else null.
- observed_at: ISO 8601 timestamp.

## Anti-hallucination
- Never invent a seller or a price. Omit a seller rather than guess.
- The advertised price must be a real number visible on the listing you cite.""",
    "goals": [
        "Returns as many DISTINCT sellers of the exact SKU as can be found — does not stop at Amazon/Walmart",
        "Includes long-tail sellers: marketplace third-party, independent stores, and discounters, not only major retailers",
        "One row per distinct seller offer with seller_name and seller_domain (bare hostname)",
        "advertised_price is a verbatim string copied from the listing, with currency; never computed or invented",
        "listing_url is a direct product/offer URL on that seller's site (never a search page)",
        "Every row includes seller_type, observed_at (ISO 8601); in_stock when determinable",
    ],
    "sources": {
        "allow": [
            {"title": "Marketplaces (Amazon 3P, eBay, Walmart Marketplace)", "domains": [], "order": 0},
            {"title": "Google Shopping", "domains": [], "order": 1},
            {"title": "Independent Beauty & Hair E-commerce Stores", "domains": [], "order": 2},
            {"title": "Discount / Overstock Retailers", "domains": [], "order": 3},
            {"title": "Salon & Professional Retailers", "domains": [], "order": 4},
        ],
        "block": [],
        "avoid": "coupon/deal-aggregator blogs, affiliate roundups, and pages that do not sell the product directly",
        "prioritize": "actual product listing pages where the item can be purchased, across the widest possible set of distinct sellers including small independent stores",
    },
    "output_schema": {
        "type": "array",
        "description": "One row per distinct seller offering the exact SKU.",
        "items": {
            "type": "object",
            "required": ["seller_name", "seller_domain", "advertised_price", "listing_url", "observed_at"],
            "properties": {
                "seller_name": {"type": "string"},
                "seller_domain": {"type": "string", "description": "Bare hostname, no protocol"},
                "advertised_price": {"type": "string", "description": "Verbatim from listing, e.g. '23.99'"},
                "currency": {"type": ["string", "null"], "description": "e.g. 'USD'"},
                "seller_type": {"type": "string", "description": "authorized_retailer | marketplace_third_party | independent_store | discounter | unknown"},
                "in_stock": {"type": ["boolean", "null"]},
                "listing_url": {"type": "string"},
                "observed_at": {"type": "string", "description": "ISO 8601"},
            },
            "additionalProperties": True,
        },
    },
    "suggested_questions": [
        "Every online seller of Olaplex No. 3 Hair Perfector 100ml and its advertised price",
        "All sellers of Kérastase Nutritive 8H Magic Night Serum 90ml with current prices",
        "Who is selling Olaplex No. 4 Bond Maintenance Shampoo 250ml online, and at what price",
    ],
}


def run_input(brand: str, product_name: str, size: str) -> str:
    """Build the per-SKU run prompt."""
    sku = f"{brand} {product_name}"
    if size:
        sku += f", {size} size"
    return (
        f"Find every online seller of {sku}, and capture each seller's advertised price. "
        "Include marketplace third-party sellers and small independent stores, not just major retailers."
    )
