"""Pydantic models for the comparable-company analysis."""
from __future__ import annotations

from statistics import median
from typing import List, Optional

from pydantic import BaseModel, Field

# Numeric metric fields used for the comps table and the peer-median row.
NUMERIC_FIELDS = [
    "market_cap_b", "pe", "forward_pe", "ps", "ev_ebitda", "peg",
    "rev_growth", "gross_margin", "op_margin", "profit_margin", "roe",
    "price_target", "analyst_recom",
]

# Human-friendly column labels for the dashboard table.
FIELD_LABELS = {
    "market_cap_b": "Mkt Cap ($B)",
    "pe": "P/E",
    "forward_pe": "Fwd P/E",
    "ps": "P/S",
    "ev_ebitda": "EV/EBITDA",
    "peg": "PEG",
    "rev_growth": "Rev Gr %",
    "gross_margin": "Gross %",
    "op_margin": "Oper %",
    "profit_margin": "Net %",
    "roe": "ROE %",
    "price_target": "Tgt Price",
    "analyst_recom": "Recom",
}


class Catalyst(BaseModel):
    """A recent, dated market-moving event for a ticker."""
    ticker: str
    headline: str
    date: Optional[str] = None
    kind: Optional[str] = Field(
        default=None, description="earnings | rating | guidance | other"
    )


class CompanyMetrics(BaseModel):
    """Valuation multiples and fundamentals for a single company."""
    ticker: str
    name: Optional[str] = None
    is_target: bool = False
    market_cap_b: Optional[float] = None
    pe: Optional[float] = None
    forward_pe: Optional[float] = None
    ps: Optional[float] = None
    ev_ebitda: Optional[float] = None
    peg: Optional[float] = None
    rev_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    op_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    roe: Optional[float] = None
    price_target: Optional[float] = None
    analyst_recom: Optional[float] = None
    source_url: Optional[str] = None


class ComparableSet(BaseModel):
    """The full deliverable: target + peers, catalysts, and a valuation verdict."""
    target_ticker: str
    target_name: Optional[str] = None
    companies: List[CompanyMetrics] = Field(default_factory=list)
    catalysts: List[Catalyst] = Field(default_factory=list)
    verdict: str = ""

    def target(self) -> Optional[CompanyMetrics]:
        return next((c for c in self.companies if c.is_target), None)

    def peers(self) -> List[CompanyMetrics]:
        return [c for c in self.companies if not c.is_target]

    def peer_median(self) -> dict:
        """Median of each numeric field across the peers (excludes the target)."""
        out = {}
        for f in NUMERIC_FIELDS:
            vals = [getattr(c, f) for c in self.peers() if getattr(c, f) is not None]
            out[f] = round(median(vals), 2) if vals else None
        return out
