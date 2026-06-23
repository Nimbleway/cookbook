"""Data contracts for Startup.Delivery — the spine of the whole app.

Everything the agent produces and the frontend renders keys off these three
models. Lock them first; keep web/lib/types.ts in sync.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Competitor(BaseModel):
    name: str
    url: str
    positioning: str = Field(description="What they do / how they pitch themselves")
    pricing: str | None = Field(default=None, description="Pricing if found")
    source_url: str = Field(description="Where this came from (a live Nimble result)")
    kind: str | None = Field(default=None, description="Type: saas|marketplace|agency|tool|community|media|other")


class PriorDelivery(BaseModel):
    """A past delivery in an overlapping niche that informed this one (cross-idea learning)."""

    brand: str
    domain: str
    tracking_id: str | None = None


class MarketHeat(BaseModel):
    """Structured 'how crowded is this space' signal from the Tower saturated_niches table."""

    niche: str
    competitor_count: int
    crowded: bool
    refreshed_at: str


class ReconResult(BaseModel):
    """Step 1 output — what the live web says about this idea."""

    idea: str
    competitors: list[Competitor] = []
    market_summary: str = Field(default="", description="Nimble include_answer synthesis, cited")
    positioning_gap: str | None = Field(default=None, description="Filled in Step 2 by the LLM")
    recon_at: str | None = Field(default=None, description="ISO-8601 time this recon ACTUALLY fetched (the original fetch time on a cache hit)")
    recon_from_cache: bool | None = Field(default=None, description="True if served from the disk cache (within TTL), False if fetched live; None if unknown/older record")
    market_heat: MarketHeat | None = Field(default=None, description="Tower crowded-space signal")
    complaints: list[str] = Field(default_factory=list, description="What users hate about incumbents (mined from live reviews)")
    # Free, already-fetched SERP signals the multi-signal score can cite (defaults
    # keep older persisted records valid). related_searches = Google's
    # parsing.entities.RelatedSearch query strings (demand breadth + intent);
    # result_count = the "About N results" total scraped from the SERP html.
    related_searches: list[str] = Field(default_factory=list, description="Google RelatedSearch query strings from the primary SERP (demand breadth + intent signal)")
    result_count: int | None = Field(default=None, description="'About N results' total parsed from the primary SERP html (rough demand-level signal)")
    # Deepened recon-time signals (Agent A). All optional with defaults so older
    # persisted records still validate, and a missing/failed signal is simply
    # "no signal" the deterministic score treats as 0 (the CORE INVARIANT).
    complaint_severity: float | None = Field(
        default=None,
        description="Aggregate severity (1-3) of the mined incumbent complaints (avg, EXTRACTED by the same complaint LLM call); None if no complaints",
    )
    priced_competitor_count: int = Field(
        default=0,
        description="How many competitors expose REAL pricing (from the best-effort WTP-band pass over already-scraped Extract markdowns; falls back to regex presence)",
    )
    pricing_band: str | None = Field(
        default=None,
        description="Normalized willingness-to-pay band across priced competitors, e.g. '$9-49/mo'; None when no real recurring pricing surfaced",
    )
    recon_confidence: str | None = Field(
        default=None,
        description="Deterministic recon COVERAGE level: 'high'|'med'|'low' (real competitors + successful extracts + trustworthy domain source). Caps the verdict confidence.",
    )


class DomainOption(BaseModel):
    """One TLD variant of a candidate name, checked live against name.com."""

    domain: str  # e.g. "freshpaws.delivery"
    tld: str  # e.g. "app"
    available: bool | None = None  # None until checked
    price_usd: float | None = None
    renewal_price_usd: float | None = None  # name.com year-2+ renewal price
    premium: bool = False  # name.com premium/aftermarket domain (priced way above standard)


class ScoreFactor(BaseModel):
    """One named, signed, capped contribution to the deterministic opportunity anchor.

    The score is no longer one axis pretending to be three: it's the SUM of these
    factors, each cited to the real evidence it was computed from. This is the
    product's credibility wedge — the number is auditable, every point is sourced.

    SHARED CONTRACT (mirrors web/src/lib/types.ts ScoreFactor):
      { signal, label, points (SIGNED), evidence, source_url|null, reliability }.
    """

    signal: str  # stable machine id, e.g. "contestability" | "demand" | "differentiation"
    label: str  # short human label for the chip, e.g. "Competition"
    points: int  # SIGNED contribution to the 0-100 anchor (negative is allowed)
    evidence: str  # one short cited line: WHAT in the recon produced this
    source_url: str | None = None  # where the evidence came from, when there is a URL
    reliability: str = "med"  # "high" | "med" | "low" — how trustworthy this signal is


class Verdict(BaseModel):
    """The decision the founder actually came for: build it, pivot, or pass."""

    call: str = "build"  # "build" | "pivot" | "pass"
    score: int = 50  # 0-100 opportunity score (higher = more open / attractive)
    confidence: str = "medium"  # "high" | "medium" | "low" — EVIDENCE STRENGTH behind the call
    recon_confidence: str | None = None  # "med"|"low" ONLY when thin recon coverage capped the confidence (for an honest "capped by recon" caption); None otherwise
    headline: str = ""  # one-line rationale grounded in the recon
    risks: list[str] = []  # 2-3 concrete risks
    next_steps: list[str] = []  # 3-5 first-week actions
    # The cited, signed factors that SUM to the anchor (the score's audit trail).
    # Default [] keeps older persisted Verdict records valid; rides on the Verdict
    # so it auto-persists via deliveries_store.record (the calibration feature store).
    score_breakdown: list[ScoreFactor] = []


class NameCandidate(BaseModel):
    """A proposed brand name + its real domain status across TLDs (Steps 2 + 3)."""

    name: str
    domain: str  # the chosen/best registrable domain, e.g. "freshpaws.delivery"
    available: bool | None = None  # None until checked via name.com (mirrors the chosen domain)
    price_usd: float | None = None
    reasoning: str = ""  # why the LLM picked it
    # Same name checked across several TLDs — the heart of the domain moment.
    variants: list[DomainOption] = []


class LakehouseIntel(BaseModel):
    """Aggregate lakehouse signal — the 'data-to-AI' loop made tangible.

    Composed from the local deliveries mirror (deliveries_store.niche_intel): it's
    fed BACK INTO the agent's naming + verdict prompts as grounding AND surfaced in
    the result. All fields are optional/defaulted so older records still validate.
    """

    deliveries_in_theme: int = 0  # past deliveries overlapping this idea's niche
    com_taken_pct: float | None = None  # % of those where the .com was unavailable
    contested_themes: list[str] = Field(default_factory=list)  # recurring niche tokens
    total_delivered: int = 0  # whole-lakehouse delivery count
    steer_note: str = ""  # the one-line steer the prompt acted on / UI shows


class Outcome(BaseModel):
    """What a founder actually DID with a verdict — the outcome-capture label.

    CAPTURE-ONLY: persisted (latest-wins) per delivery tracking_id so the
    deliveries corpus becomes a labeled feature store for a future
    outcome-calibration step. NOT yet fed into the score. All fields optional so
    a thumbs-only or decision-only or note-only capture is valid; record_outcome
    enforces that at least one of verdict_helpful/decision/note is present.

    SHARED CONTRACT (mirrors web/src/lib/types.ts Outcome). The server stamps
    captured_at (UTC ISO) + source; the web sends camelCase {verdictHelpful?,
    decision?, note?}.
    """

    verdict_helpful: bool | None = None  # thumbs on the verdict (None = not given)
    decision: str | None = None  # one of built|building|passed|considering|dead
    note: str = ""  # free-text, clipped to 500 chars at record time
    captured_at: str | None = None  # UTC ISO-8601, stamped server-side
    source: str = "web"  # where the outcome came from (default "web")


class DomainStrategy(BaseModel):
    """The AI reasoning layer ON TOP of the real name.com data for THIS delivery.

    A hybrid artifact: every concrete callout (renewal cliff, premium trap, the
    .com-vs-.delivery line, the defensive note) is computed deterministically from
    fields the agent already fetched — no invented numbers. Only the one-line
    `thesis` narration is LLM-authored (and falls back to a deterministic line on
    any failure), so the panel ties the `.delivery` thesis to this exact brand
    while staying grounded in real availability + pricing.
    """

    thesis: str  # 1-2 sentence strategy narration tying .delivery to THIS brand
    renewal_note: str | None = None  # the year-1 vs renewal cliff on the secured domain
    premium_warning: str | None = None  # premium/aftermarket traps across the variants
    com_vs_delivery: str  # how the exact-match .com compares to the secured TLD
    defensive_note: str | None = None  # rationale for the defensive launch kit
    recommendation: str  # the single concrete next move, grounded in the facts


class DeliveryPackage(BaseModel):
    """The final output — the 'box' the UI unpacks."""

    idea: str
    brand: str
    domain: str
    price_usd: float | None = None
    positioning_gap: str = ""
    market_summary: str = ""  # cited recon synthesis carried through from Step 1
    competitors: list[Competitor] = []
    landing_url: str | None = None  # bonus: the deployed page
    recon_at: str | None = None  # freshness: when the recon ACTUALLY fetched (original time on a cache hit)
    recon_from_cache: bool | None = None  # True if recon was served from cache (within TTL), False if live; None if unknown
    market_heat: MarketHeat | None = None  # crowded-space signal (Tower)
    domain_options: list[DomainOption] = []  # the winner's TLD grid (.com taken, .app open, ...)
    tracking_id: str | None = None  # DEL-YYYYMMDD-XXXXXXXX — the shipment's tracking number
    verdict: Verdict | None = None  # build/pivot/pass decision + score + risks + next steps
    suggestions: list[DomainOption] = []  # name.com's own suggested alternates for the brand
    complaints: list[str] = []  # what users hate about incumbents (mined from live reviews)
    launch_kit: list[DomainOption] = []  # defensive domains to lock the brand (get-/try-/.com)
    learned_from: list[PriorDelivery] = []  # past deliveries in this niche that shaped the names
    lakehouse_intel: LakehouseIntel | None = None  # aggregate lakehouse signal fed into the prompts + shown
    domain_strategy: DomainStrategy | None = None  # AI reasoning over the real name.com data for this delivery
    # Deepened recon-time signals carried through from ReconResult (Agent A). All
    # optional/defaulted so older records validate and the frontend renders them
    # only if present. The ScoreFactors already carry the load-bearing evidence;
    # these are the compact headline values the package surfaces in camelCase.
    complaint_severity: float | None = None  # aggregate 1-3 severity of mined complaints
    priced_competitor_count: int = 0  # competitors with real pricing (WTP-band pass)
    pricing_band: str | None = None  # normalized WTP band, e.g. "$9-49/mo"
    recon_confidence: str | None = None  # recon COVERAGE level "high"|"med"|"low"
    # The LATEST outcome a founder captured for this delivery (thumbs + build/pass
    # decision), folded in at read time by deliveries_store. Default None keeps
    # older records valid and reads unaffected when no outcome exists. CAPTURE-ONLY
    # — stored, not yet fed into the verdict/score.
    outcome: Outcome | None = None
