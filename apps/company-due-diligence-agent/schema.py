"""Structured output schema for the due-diligence profile."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Person(BaseModel):
    name: str
    role: str
    background: Optional[str] = Field(default=None, description="Prior roles / notable history")


class Funding(BaseModel):
    total_raised: Optional[str] = Field(
        default=None, description="Short phrase only, e.g. '$1.9B' — never a paragraph or inline URLs"
    )
    last_round: Optional[str] = Field(
        default=None, description="Short phrase, e.g. 'Series F, $750M' — the round name and size"
    )
    last_round_date: Optional[str] = Field(default=None, description="e.g. 'Jun 2026'")
    last_round_valuation: Optional[str] = Field(default=None, description="e.g. '$44B post-money'")
    key_investors: List[str] = Field(default_factory=list)


class Scorecard(BaseModel):
    strengths: List[str]
    risks: List[str]
    insufficient_evidence: List[str] = Field(
        description="Dimensions where public evidence was thin or conflicting"
    )


class DimensionConfidence(BaseModel):
    """One dimension's confidence grade.

    A list of these rather than a ``Dict[str, str]``: the Agent API rejects open
    objects in ``output_schema``, so a mapping cannot be expressed there. Keeping both
    patterns on the same list shape means a Pattern B result parses with this model.
    """

    dimension: str = Field(description="One of the seven diligence dimensions")
    grade: Literal["high", "medium", "low"]


class DiligenceProfile(BaseModel):
    company: str
    as_of_date: str
    business_model: str
    products_services: List[str]
    leadership: List[Person]
    funding: Funding
    partnerships: List[str] = Field(default_factory=list)
    competitors: List[str]
    regulatory_notes: Optional[str] = None
    scorecard: Scorecard
    confidence_by_dimension: List[DimensionConfidence] = Field(
        description="One entry per diligence dimension, each graded high/medium/low"
    )
    sources: List[str]
