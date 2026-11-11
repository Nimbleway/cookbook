"""Structured schema for vendor landscape extraction and the reconciliation output."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VendorCandidate(BaseModel):
    company_name: str
    headquarters: Optional[str] = None
    product_focus: str
    deployment_model: Optional[str] = Field(default=None, description="e.g. 'self-hosted', 'cloud', 'hybrid'")
    pricing_model: Optional[str] = Field(default=None, description="e.g. 'per-seat', 'usage-based'")
    target_segment: Optional[str] = Field(default=None, description="e.g. 'enterprise', 'SMB', 'developer-led'")
    funding_total: Optional[str] = Field(default=None, description="Short phrase, e.g. '$45M'")
    disclosed_arr: Optional[str] = Field(
        default=None, description="Only if a revenue/ARR figure is explicitly stated somewhere public, e.g. '$20M ARR'"
    )
    major_investors: List[str] = Field(default_factory=list)
    evidence_urls: List[str]
    include: bool = Field(description="True only if this candidate passes every inclusion criterion")
    exclusion_reason: Optional[str] = Field(
        default=None, description="Required when include=False: the specific criterion it failed"
    )


class PublishedEstimate(BaseModel):
    source: str
    figure: str = Field(description="As published, e.g. '$1.2B by 2027' - keep the original wording")
    methodology: Optional[str] = None
    url: str
    published_date: Optional[str] = None


class LandscapeExtractionBatch(BaseModel):
    """What the LangChain agent returns: raw candidates and raw published estimates."""

    category: str
    inclusion_criteria: List[str]
    candidates: List[VendorCandidate]
    published_estimates: List[PublishedEstimate]


class BottomUpEstimate(BaseModel):
    low: float = Field(description="Sum of disclosed ARR only, in dollars")
    high: float = Field(description="low + estimated ARR for funded vendors without disclosed revenue")
    disclosed_count: int
    estimated_count: int
    total_included: int
    confidence: str = Field(description="high | medium | low, based on the disclosed/total ratio")
    assumptions: List[str]


class ReconciliationFlag(BaseModel):
    published_source: str
    published_figure: str
    parsed_published_value: Optional[float]
    bottom_up_low: float
    bottom_up_high: float
    ratio_vs_midpoint: Optional[float] = Field(default=None, description="published / bottom-up midpoint")
    flagged: bool
    note: str


class LandscapeResult(BaseModel):
    category: str
    as_of_date: str
    inclusion_criteria: List[str]
    included: List[VendorCandidate]
    excluded: List[VendorCandidate]
    bottom_up: BottomUpEstimate
    published_estimates: List[PublishedEstimate]
    reconciliation: List[ReconciliationFlag]
