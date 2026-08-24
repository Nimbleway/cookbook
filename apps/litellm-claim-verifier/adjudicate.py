"""
Adjudication — the judgment half of the pipeline.

Deciding whether a set of retrieved passages actually settles a claim is the part
that needs a strong model, so this runs on Opus while extraction runs on Haiku.
Both go through `litellm.completion`; the only difference is the model string. That
is the whole argument for routing per task step rather than per application.

`unverifiable` is a real outcome. A verifier that always reaches a verdict is
guessing, and a guess dressed as a citation is worse than an honest abstention.
"""

from __future__ import annotations

from llm import ADJUDICATOR_MODEL, complete_json
from schemas import Claim, Evidence, Verdict

SYSTEM = """You judge whether retrieved web sources support, contradict, or fail to settle a specific claim.

Rules:
- Judge ONLY against the supplied sources. Do not use your own knowledge of the world, and do not fill gaps from memory — your training data may be stale, which is the entire reason these sources were fetched.
- `supported`: a source states the claim, or states something the claim follows from directly.
- `contradicted`: a source states something incompatible with the claim. Populate `correction` with the accurate version, phrased as a replacement sentence.
- `unverifiable`: the sources do not settle it — they are off-topic, too vague, or simply silent. This is a legitimate and expected outcome. Use it rather than stretching a weak source.
- `deciding_url`: the ONE source that settles it. Null when unverifiable.
- `confidence`: high when a source states the claim plainly; medium when it requires a short inference; low when the source is suggestive but thin.
- Numbers must match in magnitude and unit to count as supported. "About 40,000" does not support "42,300". A different unit is a contradiction, not a match.
- Excerpts are truncated windows of larger pages and may start or end mid-sentence. Judge what is present; do not speculate about what was cut.
- `rationale`: one sentence, referring to what the source actually says.

Return ONLY a JSON object:
{"claim_id": "...", "status": "supported", "confidence": "high", "deciding_url": "https://...", "rationale": "...", "correction": null}"""


def _format_evidence(evidence: list[Evidence]) -> str:
    if not evidence:
        return "(no sources were retrieved for this claim)"

    blocks = []
    for i, e in enumerate(evidence, 1):
        dated = e.date or (f"{e.date_raw} (relative)" if e.date_raw else "no date given")
        blocks.append(
            f"[SOURCE {i}]\nurl: {e.url}\ntitle: {e.title}\ndate: {dated}\nexcerpt:\n{e.text}"
        )
    return "\n\n".join(blocks)


def adjudicate_claim(claim: Claim, evidence: list[Evidence]) -> tuple[Verdict, float]:
    """Judge one claim against its retrieved sources. Returns (verdict, token cost)."""
    if not evidence:
        # No model call when there is nothing to judge — an honest verdict for free.
        return (
            Verdict(
                claim_id=claim.id,
                status="unverifiable",
                confidence="high",
                deciding_url=None,
                rationale="No sources were retrieved for this claim, so nothing settles it.",
                correction=None,
            ),
            0.0,
        )

    user = (
        f"CLAIM (id {claim.id}, kind {claim.kind}, "
        f"{'time-sensitive' if claim.time_sensitive else 'not time-sensitive'}):\n"
        f"{claim.text}\n\n"
        f"SOURCES:\n{_format_evidence(evidence)}"
    )
    verdict, cost = complete_json(ADJUDICATOR_MODEL, SYSTEM, user, Verdict, max_tokens=2000)

    # The model occasionally echoes a paraphrased id; the caller's id is authoritative.
    verdict.claim_id = claim.id

    # Guard the contract rather than trusting it: a deciding_url must be one we supplied.
    known = {e.url for e in evidence}
    if verdict.deciding_url and verdict.deciding_url not in known:
        verdict.deciding_url = next((u for u in known if verdict.deciding_url in u or u in verdict.deciding_url), None)

    # A supported or contradicted verdict without a source we actually supplied is not a
    # verdict this app is willing to publish: the citation IS the evidence. Rather than
    # showing a settled status with nothing behind it, fall back to unverifiable.
    if verdict.status in ("supported", "contradicted") and not verdict.deciding_url:
        verdict.status = "unverifiable"
        verdict.rationale = (
            f"{verdict.rationale} (Downgraded: the adjudicator did not cite one of the "
            f"retrieved sources, so the claim is recorded as unsettled.)"
        ).strip()

    if verdict.status == "unverifiable":
        verdict.correction = None

    return verdict, cost
