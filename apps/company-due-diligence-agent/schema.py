"""Structured output schema for the due-diligence profile."""

from __future__ import annotations

from typing import Dict, List, Optional

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
    confidence_by_dimension: Dict[str, str] = Field(
        description="dimension -> one of high/medium/low"
    )
    sources: List[str]
