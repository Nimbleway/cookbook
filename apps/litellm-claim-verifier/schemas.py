"""
Schemas first — every stage of the pipeline hands the next one a validated object,
never a loose dict. Extraction and adjudication both use these as the structured
output contract for the model call, so a malformed response fails at the boundary
instead of halfway through a report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimKind = Literal["statistic", "date", "attribution", "superlative", "causal"]
VerdictStatus = Literal["supported", "contradicted", "unverifiable"]
Confidence = Literal["high", "medium", "low"]


class Claim(BaseModel):
    """One checkable proposition lifted out of the source document."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="stable short id, e.g. c01")
    text: str = Field(description="the claim restated as a single checkable proposition")
    quote: str = Field(description="verbatim sentence from the document, for anchoring markup")
    kind: ClaimKind
    time_sensitive: bool = Field(
        description="true when the claim's truth depends on recency — 'currently', "
        "'the largest', 'as of this year', or any figure that moves"
    )


class SkippedSpan(BaseModel):
    """Something the extractor deliberately did not treat as a claim."""

    model_config = ConfigDict(extra="ignore")

    quote: str
    reason: str = Field(description="why it is not checkable: opinion, hedged, definitional, forward-looking")


class Extraction(BaseModel):
    """The extractor's full structured response for one document."""

    model_config = ConfigDict(extra="ignore")

    claims: list[Claim]
    skipped: list[SkippedSpan] = Field(default_factory=list)


class Evidence(BaseModel):
    """One retrieved source, already truncated to its relevant window."""

    model_config = ConfigDict(extra="ignore")

    url: str
    title: str
    text: str = Field(description="truncated, claim-windowed excerpt — never the full page")
    date: str | None = Field(default=None, description="absolute publish date when Nimble supplied one")
    date_raw: str | None = Field(
        default=None,
        description="Nimble's relative date ('2 weeks ago') when no absolute date exists",
    )
    full_length: int = Field(description="length of the untruncated snippet, for the truncation report")


class Verdict(BaseModel):
    """The adjudicator's ruling on one claim."""

    model_config = ConfigDict(extra="ignore")

    claim_id: str
    status: VerdictStatus
    confidence: Confidence
    deciding_url: str | None = Field(
        default=None, description="the single source that settles it; null when unverifiable"
    )
    rationale: str = Field(description="one sentence, referring to what the evidence actually says")
    correction: str | None = Field(
        default=None, description="the accurate version — populated only when contradicted"
    )


class ClaimResult(BaseModel):
    """A claim, its evidence, and its verdict — the unit the report renders."""

    model_config = ConfigDict(extra="ignore")

    claim: Claim
    evidence: list[Evidence]
    verdict: Verdict
    search_focus: Literal["news", "general"]
    search_query: str
    search_cost: float = 0.0
    adjudicate_cost: float = 0.0


class RunCost(BaseModel):
    """Cost split the way the integration reports it: search spend vs token spend."""

    model_config = ConfigDict(extra="ignore")

    search_queries: int = 0
    search_spend: float = 0.0
    extract_spend: float = 0.0
    adjudicate_spend: float = 0.0

    @property
    def token_spend(self) -> float:
        return self.extract_spend + self.adjudicate_spend

    @property
    def total(self) -> float:
        return self.search_spend + self.token_spend

    def per_claim(self, n_claims: int) -> float:
        return self.total / n_claims if n_claims else 0.0


class Run(BaseModel):
    """A complete verification run — this is what gets cached for demo mode."""

    model_config = ConfigDict(extra="ignore")

    document_path: str
    document_text: str
    results: list[ClaimResult]
    skipped: list[SkippedSpan] = Field(default_factory=list)
    cost: RunCost = Field(default_factory=RunCost)
    live: bool = True
