"""Deterministic parser for finviz quote pages (markdown from Nimble Extract).

Financial numbers must be exact, so they are parsed with regex here rather than
left to the LLM. The agent reasons over these exact values; it never re-types them.
"""
import re
from typing import Optional

# finviz stat label -> our metric key
_LABELS = {
    "Market Cap": "market_cap_b",
    "P/E": "pe",
    "Forward P/E": "forward_pe",
    "P/S": "ps",
    "EV/EBITDA": "ev_ebitda",
    "PEG": "peg",
    "ROE": "roe",
    "Gross Margin": "gross_margin",
    "Oper. Margin": "op_margin",
    "Profit Margin": "profit_margin",
    "Sales": "sales_b",
    "Sales Y/Y TTM": "rev_growth",
    "Target Price": "price_target",
    "Recom": "analyst_recom",
}

# Values that finviz reports with a B/M/K magnitude suffix, normalized to $B.
_BILLIONS_FIELDS = {"market_cap_b", "sales_b"}

_RATING_ACTIONS = {"upgrade", "downgrade", "initiated", "reiterated", "resumed"}


def _strip_links(text: str) -> str:
    """Turn ``[label](url)`` into ``label`` so link-wrapped cells parse uniformly."""
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)


def _to_number(raw: Optional[str], billions: bool = False) -> Optional[float]:
    if raw is None:
        return None
    s = raw.replace("\\", "").replace(",", "").replace("%", "").replace("$", "").strip()
    if s in ("", "-", "--", "n/a", "N/A"):
        return None
    mult = 1.0
    if s and s[-1] in "BMK":
        suffix, s = s[-1], s[:-1]
        if billions:
            mult = {"B": 1.0, "M": 1e-3, "K": 1e-6}[suffix]
        else:
            mult = {"B": 1e9, "M": 1e6, "K": 1e3}[suffix]
    try:
        return round(float(s) * mult, 4)
    except ValueError:
        return None


def parse_finviz(markdown: str) -> dict:
    """Parse a finviz quote page into a dict of metrics, peers, and analyst actions."""
    raw = markdown
    text = _strip_links(markdown).replace("\\", "")

    out: dict = {}
    for label, key in _LABELS.items():
        m = re.search(r"\|\s*" + re.escape(label) + r"\s*\|\s*\*\*([^*|]+?)\*\*", text)
        out[key] = _to_number(m.group(1).strip() if m else None,
                              billions=key in _BILLIONS_FIELDS)

    # Ticker (the "# CMG" heading) and company name ("## [Chipotle Mexican Grill](...)").
    tk = re.search(r"^#\s*([A-Z][A-Z.\-]{0,9})\s*$", markdown, re.M)
    out["ticker_guess"] = tk.group(1).strip() if tk else None
    nm = re.search(r"##\s*\[?([^\]\n|]+?)\]?\(", markdown)
    out["name"] = nm.group(1).strip() if nm else None

    # Peer tickers come straight from the finviz "Peers" screener link.
    pm = re.search(r"Peers\]\(https://finviz\.com/screener\?t=([A-Z0-9,.]+)\)", raw)
    out["peers"] = pm.group(1).split(",") if pm else []

    # Recent analyst rating actions (the ratings table near the top of the page).
    actions = []
    row_re = re.compile(
        r"\|\s*([A-Z][a-z]{2}-\d{2}-\d{2})\s*\|\s*([A-Za-z]+)\s*\|\s*([^|]+?)\s*\|"
        r"\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    )
    for am in row_re.finditer(text):
        date, action, analyst, rating, target = (g.strip() for g in am.groups())
        if action.lower() in _RATING_ACTIONS:
            actions.append({
                "date": date, "action": action, "analyst": analyst,
                "rating_change": rating, "price_target": target,
            })
    out["analyst_actions"] = actions[:6]
    return out


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(parse_finviz(sys.stdin.read()), indent=2))
