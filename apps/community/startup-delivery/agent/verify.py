"""Grounding verifier — checks the agent's outputs against the live recon.

PURE + OFFLINE: no network, no LLM, no I/O. Every function operates only on the
in-memory ReconResult / NameCandidate / Verdict objects it is handed, so it is
fast, deterministic, and trivially unit-testable (see agent/eval/).

The job is to catch the classic LLM grounding failures:
  - citing a competitor that the live recon never surfaced (hallucination),
  - proposing a brand name that collides with an incumbent's domain, and
  - articulating a "gap" that references nothing real in the evidence.

DESIGN BIAS — prefer FALSE NEGATIVES over false positives. The matching is
deliberately GENEROUS (a cited name matches a competitor on almost any plausible
signal) and a mention is only flagged when it looks like a real brand citation
(an explicit domain, a CamelCase token, or a multi-word proper phrase). Ordinary
sentence-case prose never trips a warning. This keeps the soft-verify hooks in
llm.py from ever over-flagging the proven deterministic demo path.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .schemas import NameCandidate, ReconResult, Verdict

# Corporate suffixes we ignore when normalizing a name ("Acme Inc" == "Acme").
_LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "co", "corp", "corporation", "company",
    "gmbh", "plc", "llp", "limited",
}

# Common words trimmed from the edges of a captured Capitalized phrase so that
# "Unlike MoeGo" resolves to the brand "MoeGo", not the connector "Unlike".
_COMMON_WORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "without", "by", "from",
    "to", "in", "on", "of", "at", "as", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "this", "that", "these", "those", "their", "our", "we",
    "they", "you", "i", "he", "she", "no", "not", "none", "all", "both", "most",
    "many", "some", "any", "each", "every", "while", "whereas", "unlike", "like",
    "than", "then", "so", "such", "more", "less", "very", "only", "just", "also",
    "however", "yet", "still", "here", "there", "now", "today", "currently",
    "market", "markets", "customer", "customers", "user", "users", "founder",
    "founders", "startup", "startups", "company", "companies", "competitor",
    "competitors", "incumbent", "incumbents", "product", "products", "tool",
    "tools", "platform", "platforms", "service", "services", "solution",
    "solutions", "app", "apps", "software", "business", "businesses", "team",
    "teams", "people", "everyone", "anyone", "someone",
}

# A run of one or more Capitalized words (allowing internal caps like "MoeGo").
_PHRASE_RE = re.compile(r"[A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*)*")
# A domain-like token, e.g. "moego.pet" or "freshpaws.com".
_DOMAIN_RE = re.compile(r"\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+)\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Small pure helpers                                                          #
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    """Lowercase, drop punctuation + legal suffixes, collapse whitespace."""
    t = (text or "").lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    words = [w for w in t.split() if w and w not in _LEGAL_SUFFIXES]
    return " ".join(words)


def _compact(text: str) -> str:
    return _norm(text).replace(" ", "")


def _registrable(url: str) -> str:
    """The registrable host of a URL: drop www, keep the last two labels."""
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else (parts[0] if parts else "")


def _host_label(url: str) -> str:
    """The registrable second-level label, e.g. 'moego' from 'moego.pet'."""
    reg = _registrable(url)
    return reg.split(".")[0] if reg else ""


def _slug(text: str) -> str:
    """A registrable second-level label from a brand name (mirrors llm._slug)."""
    s = (text or "").strip().lower().replace("&", "and")
    s = re.sub(r"[\s_]+", "", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    return s.strip("-")


def _edit_distance_within(a: str, b: str, k: int) -> bool:
    """True if Levenshtein(a, b) <= k. Bounded + early-exit for speed."""
    la, lb = len(a), len(b)
    if abs(la - lb) > k:
        return False
    if a == b:
        return True
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = cur[0]
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if cur[j] < row_min:
                row_min = cur[j]
        if row_min > k:
            return False
        prev = cur
    return prev[lb] <= k


# --------------------------------------------------------------------------- #
# Recon index (built once per call, then reused)                              #
# --------------------------------------------------------------------------- #
class _CompetitorIndex:
    """Pre-normalized view of one competitor for cheap repeated matching."""

    __slots__ = ("norm", "compact", "labels")

    def __init__(self, name: str, urls: list[str]) -> None:
        self.norm = _norm(name)
        self.compact = self.norm.replace(" ", "")
        labels: set[str] = set()
        for u in urls:
            lbl = _host_label(u)
            if lbl:
                labels.add(lbl)
        self.labels = labels


def _index(recon: ReconResult) -> list[_CompetitorIndex]:
    out: list[_CompetitorIndex] = []
    for comp in recon.competitors:
        out.append(_CompetitorIndex(comp.name, [comp.url, comp.source_url]))
    return out


def _mention_matches(compact: str, norm: str, index: list[_CompetitorIndex]) -> bool:
    """GENEROUS: does this mention plausibly refer to a real competitor?

    Matches on exact/compact equality, substring containment (>=4 chars), the
    registrable host label, or edit-distance<=1. Generous on purpose so we
    almost never flag a real citation as fabricated.
    """
    if not compact:
        return True  # nothing concrete to judge -> don't flag
    for comp in index:
        if compact == comp.compact:
            return True
        if norm and comp.norm and (norm in comp.norm or comp.norm in norm):
            return True
        if comp.compact and len(compact) >= 4 and (
            compact in comp.compact or comp.compact in compact
        ):
            return True
        for lbl in comp.labels:
            if compact == lbl:
                return True
            if len(compact) >= 4 and len(lbl) >= 4 and (compact in lbl or lbl in compact):
                return True
            if len(compact) >= 4 and _edit_distance_within(compact, lbl, 1):
                return True
    return False


def _trim_common(words: list[str]) -> list[str]:
    """Drop leading/trailing common connector words from a captured phrase."""
    lo, hi = 0, len(words)
    while lo < hi and words[lo].lower() in _COMMON_WORDS:
        lo += 1
    while hi > lo and words[hi - 1].lower() in _COMMON_WORDS:
        hi -= 1
    return words[lo:hi]


def _is_brandish_single(word: str) -> bool:
    """A single token reads like a brand only if it has an INTERNAL capital
    (CamelCase / PascalCase / an acronym), e.g. MoeGo, PetDesk, IBM — not a
    plain Title-Case noun like 'Groomers'."""
    return any(ch.isupper() for ch in word[1:])


def _candidate_mentions(text: str) -> list[str]:
    """Extract brand-like citation mentions from free text.

    Two sources: explicit domain tokens, and Capitalized phrases (trimmed of
    common words). Single-word phrases qualify only when CamelCase; multi-word
    phrases always qualify. Ordinary prose yields nothing.
    """
    mentions: list[str] = []
    seen: set[str] = set()

    def _add(m: str) -> None:
        key = _compact(m)
        if key and key not in seen:
            seen.add(key)
            mentions.append(m)

    for raw in _PHRASE_RE.findall(text or ""):
        words = _trim_common(raw.split())
        if not words:
            continue
        if len(words) == 1 and not _is_brandish_single(words[0]):
            continue
        _add(" ".join(words))

    for token in _DOMAIN_RE.findall((text or "").lower()):
        label = token.split(".")[0]
        if len(label) >= 3:
            _add(token)

    return mentions


# --------------------------------------------------------------------------- #
# Public checks                                                               #
# --------------------------------------------------------------------------- #
def competitors_cited_exist(text: str, recon: ReconResult) -> list[str]:
    """Cited brand names in `text` that do NOT appear in recon.competitors.

    Fuzzy + case-insensitive: ignores Inc/LLC and matches on a competitor's
    name OR the registrable host of its URL. Returns the offending mentions
    (empty list == everything cited is grounded). Tuned to avoid over-flagging.
    """
    index = _index(recon)
    missing: list[str] = []
    for mention in _candidate_mentions(text):
        if not _mention_matches(_compact(mention), _norm(mention), index):
            missing.append(mention)
    return missing


def names_collide_with_incumbents(
    candidates: list[NameCandidate], recon: ReconResult
) -> list[NameCandidate]:
    """Candidates whose slug equals (or is edit-distance<=1 from) an incumbent's
    registrable host label, e.g. proposing 'MoeGo' when moego.pet is a rival.

    Edit-distance matching only kicks in for labels >=4 chars so short labels
    don't generate spurious near-collisions. Returns the colliding candidates.
    """
    labels: set[str] = set()
    for comp in recon.competitors:
        for u in (comp.url, comp.source_url):
            lbl = _host_label(u)
            if lbl and len(lbl) >= 3:
                labels.add(lbl)
    if not labels:
        return []

    colliding: list[NameCandidate] = []
    for cand in candidates:
        slug = _slug(cand.name) or _slug((cand.domain or "").split(".")[0])
        if not slug:
            continue
        for lbl in labels:
            if slug == lbl or (
                min(len(slug), len(lbl)) >= 4 and _edit_distance_within(slug, lbl, 1)
            ):
                colliding.append(cand)
                break
    return colliding


def gap_is_grounded(gap: str, recon: ReconResult) -> bool:
    """True if the positioning gap references >=1 real competitor name OR a
    mined complaint. When the recon surfaced no competitors and no complaints,
    there is nothing to ground against, so we return True (never flag).
    """
    g_norm = _norm(gap)
    if not g_norm:
        # An empty gap is genuinely ungrounded — but only worth flagging when
        # there was real evidence it could have referenced.
        return not recon.competitors and not recon.complaints
    g_tokens = set(re.findall(r"[a-z]{4,}", g_norm))
    g_compact = g_norm.replace(" ", "")

    for comp in recon.competitors:
        cn = _norm(comp.name)
        if cn and cn in g_norm:
            return True
        for tok in cn.split():
            if len(tok) >= 4 and tok in g_tokens:
                return True
        for u in (comp.url, comp.source_url):
            lbl = _host_label(u)
            if lbl and len(lbl) >= 4 and lbl in g_compact:
                return True

    for complaint in recon.complaints:
        c_tokens = set(re.findall(r"[a-z]{4,}", complaint.lower()))
        if c_tokens & g_tokens:
            return True

    if not recon.competitors and not recon.complaints:
        return True
    return False


# Tokens that signal a gap names a real, UNDERSERVED SEGMENT (a who/where/how the
# field leaves open) — not just a vague "big opportunity". A segment-naming gap is
# worth more in the score than a generic-but-grounded one. Kept deliberately broad
# (audience, channel, model, price-tier words) so it rewards specificity offline.
_SEGMENT_TOKENS = frozenset({
    # who / audience
    "smb", "smbs", "enterprise", "consumer", "consumers", "prosumer", "b2b", "b2c",
    "freelancer", "freelancers", "solo", "indie", "teams", "team", "students",
    "seniors", "parents", "nonprofit", "nonprofits", "clinics", "vets", "groomers",
    "owners", "creators", "agencies",
    # where / geography + channel
    "rural", "urban", "suburban", "local", "regional", "nationwide", "mobile",
    "offline", "online", "in-person", "remote", "field",
    # how / model + tier
    "self-serve", "selfserve", "diy", "managed", "white-label", "marketplace",
    "subscription", "freemium", "premium", "concierge", "budget", "low-cost",
    "high-end", "luxury", "boutique", "niche", "vertical", "specialized",
    "last-minute", "lastminute", "on-demand", "ondemand", "same-day", "instant",
    "automated", "integrated", "all-in-one",
    # who / job specificity
    "underserved", "overlooked", "ignored", "segment", "audience", "vertical",
})


def gap_strength(gap: str, recon: ReconResult) -> int:
    """How strong is the positioning gap, on a 0/1/2 ladder. Pure + offline.

    Grades the gap so the score can REPLACE the old flat "+12 if any gap" bonus
    with a graded one (0 -> 0, 1 -> +6, 2 -> +12 in llm._anchor_score):

      0  ungrounded — references no real competitor / mined complaint at all
         (a vague "big opportunity" line). Reuses gap_is_grounded.
      1  grounded but GENERIC — it cites the evidence but names no concrete
         underserved segment (who/where/how the field leaves open).
      2  grounded AND names a real underserved SEGMENT — the sharpest wedge.

    A genuinely empty gap with no evidence to cite returns 0 (nothing earned).
    """
    if not gap or not gap.strip():
        return 0
    if not gap_is_grounded(gap, recon):
        return 0
    # Grounded against real evidence — does it ALSO name a concrete segment? Look
    # for segment vocabulary OR an explicit hyphenated/compound segment phrase.
    g_norm = _norm(gap)
    tokens = set(re.findall(r"[a-z][a-z0-9-]{2,}", g_norm))
    raw_tokens = set(re.findall(r"[a-z][a-z0-9-]{2,}", (gap or "").lower()))
    if (tokens | raw_tokens) & _SEGMENT_TOKENS:
        return 2
    return 1


def verify_outputs(
    recon: ReconResult,
    gap: str,
    candidates: list[NameCandidate],
    verdict: Verdict | None = None,
) -> dict[str, Any]:
    """Run every grounding check and return a structured report.

    Shape: {"ok": bool, "warnings": [{"check", "message", "items"}, ...]}.
    `ok` is True only when no check produced a warning. Never raises.
    """
    warnings: list[dict[str, Any]] = []

    cited_missing = competitors_cited_exist(gap, recon)
    if cited_missing:
        warnings.append({
            "check": "cited_competitors_exist",
            "message": (
                "positioning gap cites competitor(s) absent from the recon: "
                + ", ".join(cited_missing)
            ),
            "items": cited_missing,
        })

    if not gap_is_grounded(gap, recon):
        warnings.append({
            "check": "gap_grounded",
            "message": "positioning gap references no real competitor or mined complaint",
            "items": [],
        })

    collisions = names_collide_with_incumbents(candidates, recon)
    if collisions:
        names = [c.name for c in collisions]
        warnings.append({
            "check": "name_collision",
            "message": "name candidate(s) collide with an incumbent's domain: " + ", ".join(names),
            "items": names,
        })

    if verdict is not None:
        verdict_text = " ".join([verdict.headline, *verdict.risks, *verdict.next_steps])
        verdict_missing = competitors_cited_exist(verdict_text, recon)
        if verdict_missing:
            warnings.append({
                "check": "verdict_citations_exist",
                "message": (
                    "verdict cites competitor(s) absent from the recon: "
                    + ", ".join(verdict_missing)
                ),
                "items": verdict_missing,
            })

    return {"ok": not warnings, "warnings": warnings}
