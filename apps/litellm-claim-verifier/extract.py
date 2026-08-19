"""
Claim extraction — the cheap, mechanical half of the pipeline.

Finding the checkable propositions in a document is pattern work, not judgment, so
it runs on Haiku: one call for the whole document, at a fraction of a cent. What it
chooses NOT to check matters as much as what it does, so skipped spans are returned
with a reason and shown in the report.
"""

from __future__ import annotations

from llm import EXTRACTOR_MODEL, complete_json
from schemas import Extraction

SYSTEM = """You extract factual claims from documents so they can be checked against live web sources.

A claim qualifies only if it is a specific, checkable proposition about the world: a number, a date, an event, an attribution, a ranking, or a stated causal link. It must be checkable by someone reading a public web page.

Do NOT extract:
- opinions, predictions, or recommendations
- hedged statements ("may", "could", "some argue")
- definitions or descriptions of how something works
- anything true by construction ("this guide covers three topics")

For each claim:
- `text`: restate it as one self-contained checkable proposition. Resolve pronouns and add the subject, so the claim makes sense with no surrounding context. This string becomes a search query, so keep it clean and specific.
- `quote`: the verbatim sentence from the document, copied exactly. It is used to anchor annotations, so it must appear in the document character for character.
- `kind`: statistic | date | attribution | superlative | causal
- `time_sensitive`: true when the claim's truth depends on when you ask — current rankings, "the largest", "as of this year", prices, headcounts, version numbers, anything that moves. False for settled historical facts.

Ids are c01, c02, c03 in document order.

Return ONLY a JSON object:
{"claims": [{"id": "c01", "text": "...", "quote": "...", "kind": "statistic", "time_sensitive": true}],
 "skipped": [{"quote": "...", "reason": "opinion"}]}"""


def extract_claims(document: str, max_claims: int = 25) -> tuple[Extraction, float]:
    """Extract claims from a document. Returns (extraction, token cost)."""
    user = (
        f"Extract every checkable factual claim from this document. "
        f"Return at most {max_claims} claims, prioritising the ones a reader would most "
        f"want verified.\n\n---\n{document}\n---"
    )
    extraction, cost = complete_json(EXTRACTOR_MODEL, SYSTEM, user, Extraction)

    # Trim to the cap deterministically rather than trusting the model to count.
    if len(extraction.claims) > max_claims:
        extraction.claims = extraction.claims[:max_claims]
    return extraction, cost
