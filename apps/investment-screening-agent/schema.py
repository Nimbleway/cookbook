"""Structured output schema for the screening result."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    company_name: str
    headquarters: Optional[str] = None
    product_focus: str = Field(description="What the company builds, in one line")
    target_customer: str = Field(description="Who it sells to")
    funding_total: Optional[str] = Field(default=None, description="e.g. '$27M' or 'undisclosed'")
    major_investors: List[str] = Field(default_factory=list)
    fit_rationale: str = Field(description="One line: why this company matches the thesis")
    fit_score: str = Field(description="strong | moderate | weak")
    evidence_urls: List[str]


class Excluded(BaseModel):
    company_name: str
    reason: str


class ScreeningResult(BaseModel):
    thesis: str
    as_of_date: str
    inclusion_criteria: List[str]
    candidates: List[Candidate]
    ranked_shortlist: List[str] = Field(description="Company names, best fit first")
    excluded: List[Excluded] = Field(default_factory=list)
    sources: List[str]
