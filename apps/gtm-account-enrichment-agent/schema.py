"""Pattern A output schema: the account profile the extraction step fills in.

The fields mirror config.PROFILE_OUTPUT_SCHEMA (the Pattern B schema), with two
differences that keep source precedence in your code instead of the model:

  - field_sources records the URL behind every value the model sets.
  - conflicts keeps every disagreeing value with its URL and date. The model leaves
    the field itself null; agent.resolve_conflicts() fills it using the rules in
    config.SOURCE_TIERS and config.FRESHEST_WINS.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Leader(BaseModel):
    name: str
    title: str


class Signal(BaseModel):
    date: str = Field(description="YYYY-MM-DD, or YYYY-MM when the day is not stated")
    signal: str = Field(description="What happened, in one line")
    source_url: str


class FieldSource(BaseModel):
    field: str = Field(description="Profile field name, e.g. 'headquarters'")
    source_url: str = Field(description="URL of the evidence result that supports the value")


class SourcedValue(BaseModel):
    value: str = Field(description="The value exactly as this source states it")
    source_url: str
    as_of: Optional[str] = Field(
        default=None,
        description="Date the source gives for the value, or its publish date (YYYY-MM-DD or YYYY-MM). Null if unknown.",
    )


class Conflict(BaseModel):
    field: str = Field(description="Profile field name the values disagree on")
    values: List[SourcedValue] = Field(description="Every distinct value found, one entry per source")
    chosen: Optional[str] = Field(default=None, description="Set by the application's precedence rule, not by the model")
    rule: Optional[str] = Field(default=None, description="Which precedence rule picked `chosen`")


class AccountProfile(BaseModel):
    company_name: str
    domain: str = Field(description="Bare hostname, no protocol")
    description: Optional[str] = Field(default=None, description="One or two sentences on what the company sells and to whom")
    vertical: Optional[str] = None
    products: List[str] = Field(default_factory=list)
    target_customer: Optional[str] = None
    headquarters: Optional[str] = Field(default=None, description="City, State, Country")
    founded_year: Optional[int] = None
    employee_count: Optional[str] = Field(default=None, description="Estimate with as-of date and source type")
    funding_stage: Optional[str] = None
    total_funding_usd: Optional[float] = None
    last_round: Optional[str] = Field(default=None, description="Round, amount, date, lead investor")
    investors: List[str] = Field(default_factory=list)
    leadership: List[Leader] = Field(default_factory=list)
    customer_count: Optional[str] = Field(default=None, description="Most recent stated customer count with date")
    currently_hiring: Optional[Literal["Yes", "No"]] = None
    open_roles_summary: Optional[str] = Field(default=None, description="Approximate number of open roles and their functions")
    recent_signals: List[Signal] = Field(default_factory=list)
    field_sources: List[FieldSource] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
