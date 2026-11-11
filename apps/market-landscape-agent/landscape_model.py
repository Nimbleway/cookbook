"""Dedupe, include/exclude enforcement, bottom-up sizing, and reconciliation: all
deterministic code, not the LLM's job. The extraction step proposes; this enforces.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from schema import BottomUpEstimate, LandscapeResult, PublishedEstimate, ReconciliationFlag, VendorCandidate

# ARR-from-funding heuristic, stated plainly wherever it's used: for a vendor with a
# known funding total but no disclosed revenue, assume ARR is roughly a quarter of
# total funding raised. This is a common rough SaaS heuristic, not a measurement, and
# every use of it is logged in `assumptions` so the number can be challenged.
FUNDING_TO_ARR_MULTIPLE = 0.25
RECONCILIATION_TOLERANCE = 2.0  # published estimate flagged if it's >2x or <0.5x the bottom-up midpoint

_LEGAL_SUFFIX = re.compile(
    r"[\s,]+(?:inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|gmbh)\.?$",
    re.I,
)
# Matches "$1.2B", "USD 1.2 billion", "US$1.2bn", or bare "1.2 billion" - published
# figures use all of these interchangeably and rarely lead with a bare $ sign.
_DOLLAR_RE = re.compile(r"(?:\$|USD\s|US\$\s?)?([\d,.]+)\s*(billion|million|thousand|bn|mn|b|m|k)\b", re.I)
_UNIT_MULT = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}


def stem(name: str) -> str:
    n = name.strip().lower()
    for cut in ("(", "/", " - ", " – ", " — "):
        n = n.split(cut)[0]
    n = re.sub(r"[.'’]", "", n)
    n = re.sub(r"[-_&]", " ", n)
    prev = None
    while prev != n:
        prev = n
        n = _LEGAL_SUFFIX.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def parse_dollar_figure(text: str) -> Optional[float]:
    """Extract the first dollar amount from a free-text figure like '$1.2B by 2027'."""
    m = _DOLLAR_RE.search(text)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    unit = m.group(2).lower()
    return num * _UNIT_MULT[unit]


def dedupe_and_enforce(candidates: List[VendorCandidate]) -> Tuple[List[VendorCandidate], List[VendorCandidate]]:
    """One entry per company. Enforce the exclusion rule in code: include=True with no
    evidence, or include=False with no reason, both get corrected rather than trusted.
    """
    seen: set[str] = set()
    included: List[VendorCandidate] = []
    excluded: List[VendorCandidate] = []
    for c in candidates:
        key = stem(c.company_name)
        if key in seen:
            continue
        seen.add(key)
        if c.include and not c.evidence_urls:
            c.include = False
            c.exclusion_reason = c.exclusion_reason or "marked included but no evidence URL was captured"
        if not c.include and not c.exclusion_reason:
            c.exclusion_reason = "marked excluded with no reason given by extraction"
        (included if c.include else excluded).append(c)
    return included, excluded


def compute_bottom_up(included: List[VendorCandidate]) -> BottomUpEstimate:
    disclosed_sum = 0.0
    disclosed_count = 0
    estimated_sum = 0.0
    estimated_count = 0
    assumptions: List[str] = []

    for c in included:
        arr = parse_dollar_figure(c.disclosed_arr) if c.disclosed_arr else None
        if arr is not None:
            disclosed_sum += arr
            disclosed_count += 1
            continue
        funding = parse_dollar_figure(c.funding_total) if c.funding_total else None
        if funding is not None:
            est = funding * FUNDING_TO_ARR_MULTIPLE
            estimated_sum += est
            estimated_count += 1

    total = len(included)
    ratio = disclosed_count / total if total else 0.0
    confidence = "high" if ratio >= 0.5 else ("medium" if disclosed_count > 0 else "low")

    assumptions.append(f"{disclosed_count}/{total} included vendors have a disclosed ARR/revenue figure")
    if estimated_count:
        assumptions.append(
            f"{estimated_count} vendors with known funding but no disclosed ARR are estimated at "
            f"{FUNDING_TO_ARR_MULTIPLE:.0%} of total funding raised (a rough SaaS heuristic, not a measurement)"
        )
    remaining = total - disclosed_count - estimated_count
    if remaining:
        assumptions.append(f"{remaining} vendors have neither disclosed ARR nor a parseable funding figure and contribute $0 to either bound")

    return BottomUpEstimate(
        low=round(disclosed_sum, 0),
        high=round(disclosed_sum + estimated_sum, 0),
        disclosed_count=disclosed_count,
        estimated_count=estimated_count,
        total_included=total,
        confidence=confidence,
        assumptions=assumptions,
    )


def reconcile(bottom_up: BottomUpEstimate, published: List[PublishedEstimate]) -> List[ReconciliationFlag]:
    mid = (bottom_up.low + bottom_up.high) / 2 if (bottom_up.low or bottom_up.high) else 0.0
    flags: List[ReconciliationFlag] = []
    for p in published:
        val = parse_dollar_figure(p.figure)
        if val is None or mid == 0:
            flags.append(
                ReconciliationFlag(
                    published_source=p.source,
                    published_figure=p.figure,
                    parsed_published_value=val,
                    bottom_up_low=bottom_up.low,
                    bottom_up_high=bottom_up.high,
                    ratio_vs_midpoint=None,
                    flagged=False,
                    note="could not compute a ratio: figure unparseable or bottom-up estimate is zero",
                )
            )
            continue
        ratio = val / mid
        flagged = ratio > RECONCILIATION_TOLERANCE or ratio < (1 / RECONCILIATION_TOLERANCE)
        note = (
            f"published figure is {ratio:.1f}x the bottom-up midpoint"
            if flagged
            else f"within {RECONCILIATION_TOLERANCE:.0f}x of the bottom-up midpoint"
        )
        flags.append(
            ReconciliationFlag(
                published_source=p.source,
                published_figure=p.figure,
                parsed_published_value=val,
                bottom_up_low=bottom_up.low,
                bottom_up_high=bottom_up.high,
                ratio_vs_midpoint=round(ratio, 2),
                flagged=flagged,
                note=note,
            )
        )
    return flags


def build_result(
    category: str, inclusion_criteria: List[str], candidates: List[VendorCandidate],
    published_estimates: List[PublishedEstimate], as_of_date: str,
) -> LandscapeResult:
    included, excluded = dedupe_and_enforce(candidates)
    bottom_up = compute_bottom_up(included)
    reconciliation = reconcile(bottom_up, published_estimates)
    return LandscapeResult(
        category=category,
        as_of_date=as_of_date,
        inclusion_criteria=inclusion_criteria,
        included=included,
        excluded=excluded,
        bottom_up=bottom_up,
        published_estimates=published_estimates,
        reconciliation=reconciliation,
    )
