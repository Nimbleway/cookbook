"""Structured schema for vendor pricing extraction and the cost model output."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

BillingUnit = Literal["host", "gb_ingested_monthly", "seat", "event_monthly", "other"]

TierType = Literal["flat_all_inclusive", "base_plus_overage", "pure_per_unit", "unpublished"]


class PriceTier(BaseModel):
    tier_name: str = Field(description="e.g. 'Pro', 'Enterprise'")
    billing_unit: BillingUnit = Field(
        description="What the price scales with. Use 'other' only if genuinely none of the listed units apply."
    )
    tier_type: TierType = Field(
        description=(
            "How this tier's rate structure works, per what the page actually states: "
            "flat_all_inclusive = one fee, page explicitly says no additional per-unit charge "
            "(set base_fee_monthly only). base_plus_overage = base fee plus overage beyond an "
            "included allowance (set base_fee_monthly, included_quantity, overage_rate_per_unit, "
            "all three). pure_per_unit = no base fee, billed purely per unit (set "
            "flat_rate_per_unit only). unpublished = the page does not state enough to price this "
            "tier (leave every rate field null) - this is the correct value when you are unsure, "
            "never guess flat_all_inclusive to fill a gap."
        )
    )
    base_fee_monthly: Optional[float] = Field(default=None, description="Flat monthly fee, if published")
    included_quantity: Optional[float] = Field(
        default=None,
        description=(
            "For base_plus_overage: units included before overage applies. For "
            "flat_all_inclusive: the HARD CAP this tier is limited to, if any (e.g. a "
            "free tier capped at 5 hosts) - set this whenever the page states a cap, "
            "even though the tier is otherwise a flat fee. Leave null only if the tier "
            "is truly uncapped."
        ),
    )
    overage_rate_per_unit: Optional[float] = Field(
        default=None, description="Cost per unit of billing_unit beyond included_quantity"
    )
    flat_rate_per_unit: Optional[float] = Field(
        default=None, description="For pure per-unit pricing with no base fee or included allowance"
    )
    source_url: str


class PackagingChange(BaseModel):
    date: str = Field(description="YYYY-MM-DD as published in the changelog")
    description: str
    source_url: str


class VendorPricing(BaseModel):
    vendor: str
    tiers: List[PriceTier]
    packaging_changes_last_90_days: List[PackagingChange] = Field(default_factory=list)
    sources: List[str]


class VendorExtractionBatch(BaseModel):
    """What the LangChain agent returns: raw extracted pricing data, no arithmetic."""

    vendors: List[VendorPricing]


class CostEstimate(BaseModel):
    vendor: str
    tier_used: str
    billing_unit: str
    modeled_monthly_cost: float
    modeled_annual_cost: float
    assumptions: List[str] = Field(description="Plain-language statement of every input used in the calculation")


class QuoteRequired(BaseModel):
    vendor: str
    missing_input: str = Field(description="The specific field that could not be computed from public pages")
    reason: str


class PricingComparisonResult(BaseModel):
    buyer_profile: Dict[str, float]
    as_of_date: str
    vendors: List[VendorPricing]
    cost_ranking: List[CostEstimate] = Field(description="Sorted cheapest first, computable vendors only")
    quote_required: List[QuoteRequired]
