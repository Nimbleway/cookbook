"""Dedupe, windowing, minimum-sample, and escalation logic: deterministic code, not the
LLM's job. The agent's only job is to find, classify, and date items consistently.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import List, Tuple

from schema import ReviewItem, SentimentResult, ThemeRow

MIN_SAMPLE_SIZE = 4
ESCALATION_THRESHOLD_PCT = 25.0


def dedupe(items: List[ReviewItem]) -> List[ReviewItem]:
    """Drop syndicated/duplicate reviews: same normalized text on the same date."""
    seen: set[str] = set()
    out: List[ReviewItem] = []
    for it in items:
        norm = re.sub(r"[^a-z0-9]+", "", it.text_excerpt.lower())[:120]
        key = f"{norm}|{it.date}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def split_windows(items: List[ReviewItem], as_of: dt.date, window_days: int) -> Tuple[List[ReviewItem], List[ReviewItem]]:
    cur_start = as_of - dt.timedelta(days=window_days)
    prior_start = cur_start - dt.timedelta(days=window_days)
    current, prior = [], []
    for it in items:
        try:
            d = dt.date.fromisoformat(it.date)
        except ValueError:
            continue
        if cur_start <= d <= as_of:
            current.append(it)
        elif prior_start <= d < cur_start:
            prior.append(it)
    return current, prior


def _stats(items: List[ReviewItem], theme: str) -> tuple[int, int, dict[str, int]]:
    theme_items = [i for i in items if i.theme == theme]
    volume = len(theme_items)
    negative = sum(1 for i in theme_items if i.sentiment == "negative")
    mix = dict(Counter(i.source for i in theme_items))
    return volume, negative, mix


def build_result(
    brand: str,
    batch_items: List[ReviewItem],
    canonical_themes: List[str],
    as_of: dt.date,
    window_days: int = 90,
    min_sample_size: int = MIN_SAMPLE_SIZE,
    escalation_threshold_pct: float = ESCALATION_THRESHOLD_PCT,
) -> SentimentResult:
    total_considered = len(batch_items)
    deduped = dedupe(batch_items)
    current, prior = split_windows(deduped, as_of, window_days)

    theme_table: List[ThemeRow] = []
    insufficient: List[str] = []

    for theme in canonical_themes:
        cur_vol, cur_neg, cur_mix = _stats(current, theme)
        prior_vol, prior_neg, _ = _stats(prior, theme)

        if cur_vol < min_sample_size:
            insufficient.append(theme)
            continue

        if prior_neg == 0:
            change_pct = None if cur_neg == 0 else 100.0
            direction = "flat" if cur_neg == 0 else "new"
        else:
            change_pct = round((cur_neg - prior_neg) / prior_neg * 100, 1)
            direction = "up" if change_pct > 5 else ("down" if change_pct < -5 else "flat")

        escalated = (change_pct is not None and change_pct >= escalation_threshold_pct) or (
            prior_vol == 0 and cur_neg >= min_sample_size
        )

        quotes = [
            {"text": i.text_excerpt, "url": i.url, "date": i.date}
            for i in current
            if i.theme == theme and i.sentiment == "negative"
        ][:3]

        theme_table.append(
            ThemeRow(
                theme=theme,
                current_volume=cur_vol,
                current_negative=cur_neg,
                prior_volume=prior_vol,
                prior_negative=prior_neg,
                change_pct=change_pct,
                direction=direction,
                sample_size=cur_vol,
                source_mix=cur_mix,
                escalated=escalated,
                representative_quotes=quotes if escalated else [],
            )
        )

    triage_list = sorted(
        [r for r in theme_table if r.escalated],
        key=lambda r: (r.change_pct if r.change_pct is not None else 0),
        reverse=True,
    )

    return SentimentResult(
        brand=brand,
        window_days=window_days,
        as_of_date=as_of.isoformat(),
        theme_table=theme_table,
        triage_list=triage_list,
        insufficient_volume=insufficient,
        total_items_considered=total_considered,
        total_items_after_dedupe=len(deduped),
    )
