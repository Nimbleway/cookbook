"""Deterministic brand-name scoring + ranking (no network, no LLM, no I/O).

PURE + OFFLINE, in the same spirit as agent/verify.py: every function operates
only on the in-memory NameCandidate / ReconResult objects it is handed, so it is
fast, deterministic, and trivially testable (see the __main__ block below).

The job is to reorder the LLM's name candidates so the most *brandable* one tends
to win the downstream name.com TLD check — and to DROP any candidate that collides
with an incumbent's registrable host (a colliding brand is never something we want
to ship). We always keep >=1 candidate so the availability loop has something to
work with.

`score_name` blends four cheap, well-understood brandability signals into a single
0-100 score:
  - LENGTH        — short is memorable; names > 12 chars are penalized progressively.
  - SYLLABLES     — 1-3 syllables say-able in one breath; more is penalized.
  - PRONOUNCEABLE — needs vowels and no long consonant clusters; this also GATES the
                    whole score (an unpronounceable name is unusable however short).
  - DICTIONARY    — an exact common-dictionary word is recognizable but harder to own
                    / trademark, so it gets a mild penalty vs a coined/blended word.
"""
from __future__ import annotations

import re
from collections import Counter

if __package__ in (None, ""):
    # Allow `python3 agent/naming.py` (script mode, no package context) to exercise
    # the inline self-checks below — fall back to absolute imports off the repo root.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent import verify
    from agent.schemas import NameCandidate, ReconResult
else:
    from . import verify
    from .schemas import NameCandidate, ReconResult

# y counts as a vowel for syllable/pronounceability purposes ("pawly", "rhythm").
_VOWELS = frozenset("aeiouy")

_NON_LABEL = re.compile(r"[^a-z0-9]")

# A compact set of everyday English words. Used ONLY for the dictionary-word
# heuristic: if the whole brand IS a plain dictionary word it's recognizable but
# less ownable/trademarkable than a coined or blended root, so it earns a mild
# penalty. Deliberately small + embedded so this module stays pure and offline.
_DICT_WORDS = frozenset({
    "able", "about", "above", "across", "after", "again", "agent", "alert", "alive",
    "amber", "anchor", "angle", "apple", "april", "arrow", "aspect", "atlas", "audio",
    "autumn", "award", "basic", "beach", "bear", "berry", "black", "blank", "blaze",
    "block", "bloom", "blue", "board", "boat", "bold", "bolt", "bonus", "book",
    "boost", "brand", "brave", "bread", "break", "brick", "bridge", "bright", "broad",
    "brook", "brush", "build", "cabin", "cable", "candy", "canvas", "carbon", "cargo",
    "cedar", "chain", "chalk", "charm", "chart", "chase", "cheer", "cherry", "chief",
    "clay", "clean", "clear", "clever", "click", "cliff", "climb", "cloud", "clover",
    "coast", "comet", "coral", "craft", "crane", "crisp", "crown", "crystal", "cycle",
    "daily", "dawn", "delta", "depot", "diamond", "drift", "eagle", "early", "earth",
    "ember", "energy", "engine", "fable", "falcon", "feather", "fern", "fiber",
    "field", "flame", "flash", "fleet", "flint", "flora", "flow", "flower", "focus",
    "forest", "forge", "frame", "fresh", "frost", "garden", "gem", "giant", "glass",
    "globe", "glory", "glow", "grain", "grand", "grape", "grass", "green", "grid",
    "grove", "guard", "happy", "harbor", "haven", "hazel", "heart", "honey", "horizon",
    "house", "human", "ivory", "jade", "jolly", "jump", "kite", "lake", "lamp",
    "leaf", "ledger", "lemon", "level", "light", "lily", "lion", "lotus", "lucky",
    "lunar", "magic", "maple", "marble", "market", "meadow", "metal", "metro",
    "mint", "mirror", "modern", "moon", "mortar", "motion", "mountain", "nest",
    "noble", "north", "novel", "oasis", "ocean", "olive", "onyx", "orbit", "orchid",
    "otter", "owl", "paper", "peach", "pearl", "pebble", "pepper", "pilot", "pine",
    "pixel", "plain", "planet", "plant", "plaza", "plum", "pond", "portal", "prime",
    "prism", "pulse", "quartz", "quest", "quick", "quiet", "rabbit", "radar", "rain",
    "raven", "ready", "river", "robin", "rocket", "rose", "royal", "ruby", "sage",
    "salt", "sand", "scout", "shade", "shadow", "shamrock", "shape", "shard", "shark",
    "sheen", "shelf", "shield", "shine", "shore", "silk", "silver", "simple", "slate",
    "smart", "smoke", "snow", "solar", "solid", "spark", "speed", "spice", "spring",
    "sprout", "spruce", "stack", "star", "steam", "steel", "stellar", "stone", "storm",
    "stream", "summit", "sunny", "swift", "table", "thunder", "tiger", "timber",
    "topaz", "tower", "trail", "trend", "tribe", "true", "trust", "tulip", "valley",
    "vapor", "velvet", "vine", "violet", "vision", "vivid", "voyage", "water", "wave",
    "willow", "winter", "wolf", "wonder", "zephyr", "zone",
})


def _label(name: str, domain: str = "") -> str:
    """The registrable second-level label to score: lowercase, alnum only.

    Falls back to the domain's label when the name is empty (mirrors the slug
    shape used in llm.py / verify.py so scoring matches what actually ships).
    """
    base = (name or "").strip().lower().replace("&", "and")
    base = _NON_LABEL.sub("", base)
    if base:
        return base
    label = (domain or "").strip().lower().split(".")[0]
    return _NON_LABEL.sub("", label)


def _syllables(letters: str) -> int:
    """Cheap syllable estimate: count vowel groups, with a silent-trailing-e nudge."""
    if not letters:
        return 0
    groups = re.findall(r"[aeiouy]+", letters)
    count = len(groups)
    # A silent trailing "e" (e.g. "name", "globe") usually isn't its own syllable.
    if count > 1 and letters.endswith("e") and not letters.endswith(("le", "ye")):
        count -= 1
    return max(1, count)


def _length_score(length: int) -> float:
    """0-1: short-and-memorable is best; > 12 chars is penalized progressively."""
    if length <= 2:
        return 0.45  # too short to read as a brand
    if length <= 10:
        return 1.0
    if length <= 12:
        return 0.85
    return max(0.0, 0.85 - 0.08 * (length - 12))


def _syllable_score(syllables: int) -> float:
    """0-1: 1-3 syllables say it in one breath; beyond that gets harder."""
    if syllables <= 3:
        return 1.0
    if syllables == 4:
        return 0.7
    return max(0.0, 0.7 - 0.2 * (syllables - 4))


def _pronounceability(letters: str) -> float:
    """0-1 pronounceability. 0 when there are no vowels at all (unsayable).

    Penalizes long consonant clusters and extreme vowel ratios. Used both as a
    weighted component AND as a multiplicative gate in `score_name`.
    """
    if not letters:
        return 0.0
    vowels = sum(1 for ch in letters if ch in _VOWELS)
    if vowels == 0:
        return 0.0
    score = 1.0
    longest_cluster = max((len(run) for run in re.findall(r"[^aeiouy]+", letters)), default=0)
    if longest_cluster >= 5:
        score -= 0.7
    elif longest_cluster == 4:
        score -= 0.45
    elif longest_cluster == 3:
        score -= 0.2
    ratio = vowels / len(letters)
    if ratio < 0.2 or ratio > 0.75:
        score -= 0.2
    return max(0.0, score)


def _dictionary_score(letters: str) -> float:
    """0-1: a coined/blended root (more ownable) beats a plain dictionary word."""
    return 0.5 if letters in _DICT_WORDS else 1.0


def score_name(name: str, domain: str = "") -> float:
    """A 0-100 brandability score for a candidate name (higher = more brandable).

    Pure + deterministic. Blends length, syllable count, pronounceability, and a
    dictionary-word signal; pronounceability also gates the total so an unsayable
    name can't score well just because it's short.
    """
    letters = _label(name, domain)
    if not letters:
        return 0.0

    length_score = _length_score(len(letters))
    syllable_score = _syllable_score(_syllables(letters))
    pron = _pronounceability(letters)
    dict_score = _dictionary_score(letters)

    components = (
        length_score * 0.30
        + syllable_score * 0.20
        + pron * 0.35
        + dict_score * 0.15
    )
    # Pronounceability gates the whole score: a name you can't say is unusable no
    # matter how short or coined it is.
    gate = 0.35 + 0.65 * pron
    return round(max(0.0, min(100.0, 100.0 * components * gate)), 1)


def _collisions(candidates: list[NameCandidate], recon: ReconResult) -> set[tuple[str, str]]:
    """(name, domain) keys of candidates that collide with an incumbent's host.

    Reuses verify.names_collide_with_incumbents (the same idea the llm.py hook uses)
    so the collision rule stays in one place. Best-effort: a verifier hiccup yields
    no collisions rather than dropping anything.
    """
    try:
        colliding = verify.names_collide_with_incumbents(candidates, recon)
    except Exception:
        return set()
    return {(c.name, c.domain) for c in colliding}


def rank_candidates(
    candidates: list[NameCandidate], recon: ReconResult
) -> list[NameCandidate]:
    """Sort candidates best-first by `score_name`, DROPPING incumbent collisions.

    A colliding brand (slug equal/near an incumbent's registrable host) is removed
    so it can't win the TLD check; we always keep >=1 candidate (the most brandable
    survivor — or, if every candidate collides, the single best-scoring one) so the
    downstream availability loop never starves. Stable: ties keep the LLM's order.
    """
    cands = list(candidates or [])
    if not cands:
        return cands

    def _key(candidate: NameCandidate) -> float:
        return score_name(candidate.name, candidate.domain)

    bad = _collisions(cands, recon)
    kept = [c for c in cands if (c.name, c.domain) not in bad]
    if not kept:
        # Everything collided — keep the single most brandable so we never starve.
        kept = [max(cands, key=_key)]
    return sorted(kept, key=_key, reverse=True)


if __name__ == "__main__":
    if __package__ in (None, ""):
        from agent.schemas import Competitor
    else:
        from .schemas import Competitor

    # Pronounceability: a vowelless consonant pile is unusable, even though short.
    assert score_name("Lumo", "lumo.com") > score_name("Brrkkstrm", "brrkkstrm.com")
    assert score_name("Brrkkstrm", "brrkkstrm.com") < 40

    # Length: a tight 4-char brand beats a 20-char tongue-twister.
    assert score_name("Lumo", "lumo.com") > score_name(
        "Internationalization", "internationalization.com"
    )

    # Coined roots edge out exact dictionary words (more ownable).
    assert score_name("Zapier", "zapier.com") >= score_name("Apple", "apple.com")

    # Scores are bounded 0-100.
    for nm in ("Lumo", "Zapier", "Brrkkstrm", "Internationalization", ""):
        s = score_name(nm, f"{nm.lower()}.com")
        assert 0.0 <= s <= 100.0, (nm, s)

    # rank_candidates: drops the incumbent collision, keeps >=1, best name first.
    recon = ReconResult(
        idea="last-minute dog grooming",
        competitors=[
            Competitor(
                name="MoeGo",
                url="https://moego.pet",
                positioning="grooming software",
                source_url="https://moego.pet",
            )
        ],
    )
    cands = [
        NameCandidate(name="MoeGo", domain="moego.com"),       # collides -> dropped
        NameCandidate(name="Brrkkstrm", domain="brrkkstrm.com"),
        NameCandidate(name="Pawly", domain="pawly.com"),
    ]
    ranked = rank_candidates(cands, recon)
    assert ranked, "must always keep >=1 candidate"
    assert all(c.name != "MoeGo" for c in ranked), "incumbent collision must be dropped"
    assert ranked[0].name == "Pawly", [c.name for c in ranked]

    # Even if EVERY candidate collides, keep exactly one (never starve the loop).
    all_collide = [NameCandidate(name="MoeGo", domain="moego.com")]
    kept = rank_candidates(all_collide, recon)
    assert len(kept) == 1 and kept[0].name == "MoeGo"

    print("naming.py self-checks passed:")
    for c in ranked:
        print(f"  {score_name(c.name, c.domain):5.1f}  {c.name:<12} {c.domain}")
