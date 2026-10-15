"""The cost model: deterministic arithmetic, not the LLM's job.

Given a vendor's extracted pricing tiers and a buyer profile, compute a modeled annual
cost per tier and pick the cheapest computable one. A tier is only "computable" if the
buyer profile has a quantity for its billing unit AND the tier publishes enough of a
rate structure to price that quantity. Anything else goes to quote_required with the
specific missing input named, never estimated.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from schema import CostEstimate, PriceTier, QuoteRequired, VendorPricing


def price_tier(tier: PriceTier, buyer_profile: dict) -> Tuple[Optional[float], List[str], Optional[str]]:
    """Returns (modeled_monthly_cost, assumptions, missing_input_reason).

    Exactly one of (cost, reason) is set; assumptions is only populated when cost is.
    Dispatches on tier.tier_type, an explicit field the extraction step sets, rather than
    inferring the rate structure from which fields happen to be null. "unpublished" always
    routes to quote_required: it is never treated as an implicit all-inclusive flat fee.
    """
    unit = tier.billing_unit
    if tier.tier_type == "unpublished":
        return None, [], f"{tier.tier_name} pricing structure is not fully published on the vendor's page"
    if unit == "other" or unit not in buyer_profile:
        return None, [], f"buyer profile has no quantity for billing unit '{unit}'"
    qty = buyer_profile[unit]

    if tier.tier_type == "flat_all_inclusive":
        if tier.base_fee_monthly is None:
            return None, [], f"{tier.tier_name} marked flat_all_inclusive but no base_fee_monthly was extracted"
        if tier.included_quantity is not None and qty > tier.included_quantity:
            return None, [], (
                f"{tier.tier_name} is capped at {tier.included_quantity:,.0f} {unit}; "
                f"buyer profile needs {qty:,.0f}, this tier does not apply"
            )
        cap_note = f", capped at {tier.included_quantity:,.0f} {unit}" if tier.included_quantity is not None else ""
        assumptions = [f"flat all-inclusive fee ${tier.base_fee_monthly:,.0f}/mo ({tier.tier_name}){cap_note}, no per-{unit} charge"]
        return round(tier.base_fee_monthly, 2), assumptions, None

    if tier.tier_type == "base_plus_overage":
        if tier.base_fee_monthly is None or tier.included_quantity is None or tier.overage_rate_per_unit is None:
            return None, [], (
                f"{tier.tier_name} marked base_plus_overage but base_fee_monthly, included_quantity, "
                f"or overage_rate_per_unit is missing"
            )
        overage_qty = max(0.0, qty - tier.included_quantity)
        monthly = tier.base_fee_monthly + overage_qty * tier.overage_rate_per_unit
        assumptions = [
            f"base fee ${tier.base_fee_monthly:,.0f}/mo ({tier.tier_name})",
            f"{tier.included_quantity:,.0f} {unit} included, ${tier.overage_rate_per_unit:,.2f}/{unit} overage beyond that",
            f"buyer profile has {qty:,.0f} {unit} -> {overage_qty:,.0f} {unit} of overage",
        ]
        return round(monthly, 2), assumptions, None

    if tier.tier_type == "pure_per_unit":
        if tier.flat_rate_per_unit is None:
            return None, [], f"{tier.tier_name} marked pure_per_unit but no flat_rate_per_unit was extracted"
        monthly = qty * tier.flat_rate_per_unit
        assumptions = [f"${tier.flat_rate_per_unit:,.2f}/{unit} flat rate, no base fee or included allowance"]
        return round(monthly, 2), assumptions, None

    return None, [], f"unrecognized tier_type '{tier.tier_type}'"


def build_cost_ranking(
    vendors: List[VendorPricing], buyer_profile: dict
) -> Tuple[List[CostEstimate], List[QuoteRequired]]:
    ranking: List[CostEstimate] = []
    quote_required: List[QuoteRequired] = []

    for v in vendors:
        best: Optional[CostEstimate] = None
        reasons: List[str] = []
        for tier in v.tiers:
            monthly, assumptions, reason = price_tier(tier, buyer_profile)
            if monthly is None:
                reasons.append(f"{tier.tier_name}: {reason}")
                continue
            est = CostEstimate(
                vendor=v.vendor,
                tier_used=tier.tier_name,
                billing_unit=tier.billing_unit,
                modeled_monthly_cost=monthly,
                modeled_annual_cost=round(monthly * 12, 2),
                assumptions=assumptions,
            )
            if best is None or est.modeled_annual_cost < best.modeled_annual_cost:
                best = est
        if best is not None:
            ranking.append(best)
        else:
            quote_required.append(
                QuoteRequired(
                    vendor=v.vendor,
                    missing_input=reasons[0].split(": ", 1)[-1] if reasons else "no tiers extracted",
                    reason="; ".join(reasons) if reasons else "no pricing tiers were extracted for this vendor",
                )
            )

    ranking.sort(key=lambda e: e.modeled_annual_cost)
    return ranking, quote_required
