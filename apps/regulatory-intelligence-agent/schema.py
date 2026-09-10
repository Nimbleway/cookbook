"""Structured output schema for the regulatory brief."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Development(BaseModel):
    title: str = Field(description="Short headline for the development")
    type: Literal["filing", "enforcement", "investigation", "policy", "guidance", "other"]
    date: str = Field(description="Date of the development (YYYY-MM-DD or as reported)")
    issuing_body: str = Field(description="Regulator, court, or company that issued it")
    summary: str = Field(description="What changed, in 1-3 sentences")
    materiality: Literal["high", "medium", "low"]
    why_it_matters: str = Field(description="Why this could affect the company or sector")
    confidence: Literal["high", "medium", "low"] = "medium"
    source_urls: List[str] = Field(
        description="URLs of the primary documents supporting this development"
    )


class RegulatoryBrief(BaseModel):
    entity: str = Field(description="The company, sector, or topic researched")
    as_of_date: str = Field(description="Date the research was run")
    developments: List[Development]
    overall_assessment: str = Field(
        description="2-4 sentences on the net regulatory picture for the subject"
    )
    sources: List[str] = Field(description="All primary source URLs cited in the brief")
