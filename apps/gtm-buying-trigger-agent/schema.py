"""Pattern A structured output: what the extraction step returns for one account.

The trigger fields match the triggers[] items in config.OUTPUT_SCHEMA (the Pattern B
schema), so both patterns end in the same report shape. agent.py nests these triggers
under the account, and post_process() sets trigger_count and strongest_trigger.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TriggerType = Literal["funding_round", "leadership_hire", "expansion", "product_launch",
                      "partnership", "acquisition", "customer_win", "other"]


class Trigger(BaseModel):
    event_date: str = Field(description="Date the event happened or was announced, YYYY-MM-DD. Not the article's publish date.")
    trigger_type: TriggerType
    headline: str = Field(description="One line naming the event")
    why_it_is_a_trigger: str
    strength: Literal["High", "Medium", "Low"] = Field(
        description="How directly the event changes the account's go-to-market priorities or budget")
    source_url: str = Field(description="URL of the result that reports the event; prefer the company's own page")


class ExcludedEvent(BaseModel):
    headline: str
    reason: str = Field(description="e.g. event dated before the window, not a trigger")


class AccountExtraction(BaseModel):
    triggers: List[Trigger] = Field(default_factory=list, description="One row per underlying event")
    excluded_events: List[ExcludedEvent] = Field(default_factory=list)
    outreach_angle: Optional[str] = Field(
        default=None, description="One sentence a rep could open with, using only facts from these triggers; null if no triggers")
