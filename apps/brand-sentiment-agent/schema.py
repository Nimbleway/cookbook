"""Structured schema for sentiment extraction and the triage output."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Sentiment = Literal["positive", "negative", "neutral"]


class ReviewItem(BaseModel):
    source: str = Field(description="Domain the item came from, e.g. 'reddit.com', 'trustpilot.com'")
    date: str = Field(
        description="Exact date the review/post was made, YYYY-MM-DD. If the platform only shows a "
        "relative date ('2 weeks ago'), compute the absolute date from today's date."
    )
    url: str
    star_rating: Optional[float] = Field(default=None, description="Only if the platform shows one")
    text_excerpt: str = Field(description="A short 1-2 sentence excerpt of the actual review or post text")
    theme: str = Field(description="One of the canonical_themes defined for this run, used verbatim")
    sentiment: Sentiment


class SentimentExtractionBatch(BaseModel):
    """What the LangChain agent returns: raw classified items, no counting or thresholds."""

    brand: str
    canonical_themes: List[str] = Field(
        description="4-8 theme labels you defined for this brand based on what you found. "
        "Every item.theme must be one of these strings, verbatim."
    )
    items: List[ReviewItem]


class ThemeRow(BaseModel):
    theme: str
    current_volume: int
    current_negative: int
    prior_volume: int
    prior_negative: int
    change_pct: Optional[float] = Field(default=None, description="null if prior_negative was 0 and current isn't")
    direction: Literal["up", "down", "flat", "new"]
    sample_size: int
    source_mix: Dict[str, int]
    escalated: bool
    representative_quotes: List[dict] = Field(default_factory=list, description="[{text, url, date}]")


class SentimentResult(BaseModel):
    brand: str
    window_days: int
    as_of_date: str
    theme_table: List[ThemeRow] = Field(description="Every theme that cleared the minimum sample size")
    triage_list: List[ThemeRow] = Field(description="Subset of theme_table that escalated, ranked by change_pct")
    insufficient_volume: List[str] = Field(description="Theme names dropped for too few items to report")
    total_items_considered: int
    total_items_after_dedupe: int
