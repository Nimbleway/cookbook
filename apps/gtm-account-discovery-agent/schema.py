"""Structured outputs for the LLM steps in agent.py.

The model only extracts and grades evidence. Pass/fail decisions are made in code
(agent.firmographic_decision, agent.hiring_decision, agent.headcount_gate), so the
rules stay the same on every run.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Criterion = Literal["hq", "product", "size", "stage", "sales_hiring"]
Status = Literal["met", "not_met", "unclear"]


# --- step 2: candidate extraction ------------------------------------------

class EarlyRejection(BaseModel):
    criterion: Criterion
    reason: str = Field(description="The fact in the result that fails the criterion, quoted or paraphrased")


class Candidate(BaseModel):
    name: str = Field(description="Company name only, no legal suffix")
    domain: Optional[str] = Field(default=None, description="Bare hostname if a result states it, else null")
    evidence_url: str = Field(description="URL of the result that names the company")
    early_rejection: Optional[EarlyRejection] = Field(
        default=None,
        description="Set only when a result explicitly states a fact that fails a criterion",
    )


class CandidateList(BaseModel):
    candidates: List[Candidate]


# --- step 3: per-candidate judges ------------------------------------------

class CriterionCheck(BaseModel):
    status: Status = Field(description="met / not_met from explicit evidence; unclear when the evidence does not say")
    evidence: str = Field(description="The value found, e.g. 'San Francisco, CA' or 'Series B, $60M, Nov 2025'")
    source_url: Optional[str] = None


class FirmographicVerdict(BaseModel):
    domain: Optional[str] = Field(default=None, description="The company's bare hostname, if the evidence confirms it")
    hq: CriterionCheck
    product: CriterionCheck
    stage: CriterionCheck
    size: CriterionCheck


class HiringVerdict(BaseModel):
    status: Status
    role_title: Optional[str] = None
    location: Optional[str] = None
    posting_url: Optional[str] = Field(default=None, description="URL of the posting on the careers page or ATS board")
    evidence: str


# --- Pattern B trust gate --------------------------------------------------

class HeadcountFigure(BaseModel):
    low: int = Field(description="Lower bound; equal to high for a single number")
    high: int
    source: str = Field(description="Who states it, e.g. 'PitchBook', 'LinkedIn', 'company'")
    source_url: Optional[str] = None
    as_of: Optional[str] = Field(default=None, description="Date the source gives for the figure (YYYY-MM-DD or YYYY-MM); null if undated")


class HeadcountEvidence(BaseModel):
    figures: List[HeadcountFigure] = Field(description="Every headcount figure in the results for this company; empty if none")
