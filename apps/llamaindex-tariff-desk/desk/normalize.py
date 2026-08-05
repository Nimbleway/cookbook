"""Question → canonical lane key.

Why this file exists (DESIGN.md §5): free-text questions have no natural doc_id.
"duty on batteries from Vietnam" and "Vietnam battery tariff rate" are the same
lane, and if each spawns its own Document the corpus fills with near-duplicates
that never refresh cleanly. Normalizing to `<hts_code>|<origin>|<destination>`
before touching the index is what makes the corpus compound instead of rot.

Classification stays human (DESIGN.md §11.3). This module never invents an HTS
code: if the question doesn't carry one and the product isn't in the small local
hint table, it returns `needs_hts_code` and the UI asks. It may *suggest* a code,
always explicitly flagged as unconfirmed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .research import Lane

# Deliberately tiny. Not a classification database — just enough to recognise the
# demo lanes so a reader isn't forced to look up a code to try the app. Anything
# outside this table goes to the human.
KNOWN_PRODUCTS: dict[str, tuple[str, str]] = {
    "lithium-ion battery": ("8507.60.00", "lithium-ion battery packs"),
    "lithium ion battery": ("8507.60.00", "lithium-ion battery packs"),
    "li-ion battery": ("8507.60.00", "lithium-ion battery packs"),
    "aluminum extrusion": ("7604.29.10", "aluminum extrusions"),
    "aluminium extrusion": ("7604.29.10", "aluminum extrusions"),
    "cotton t-shirt": ("6109.10.00", "cotton knit t-shirts"),
    "cotton tshirt": ("6109.10.00", "cotton knit t-shirts"),
    "cotton t shirt": ("6109.10.00", "cotton knit t-shirts"),
    "printed book": ("4901.99.00", "printed books"),
    "solar panel": ("8541.43.00", "photovoltaic modules"),
    "solar module": ("8541.43.00", "photovoltaic modules"),
}

# 4-to-10 digit HTS notation: 8507, 8507.60, 8507.60.00, 8507.60.0020
HTS_RE = re.compile(r"\b(\d{4}(?:\.\d{2}){0,3}(?:\d{2})?)\b")

COUNTRY_HINTS = (
    "Vietnam", "China", "Mexico", "Canada", "India", "Bangladesh", "Thailand",
    "Taiwan", "South Korea", "Korea", "Japan", "Germany", "France", "Italy",
    "United Kingdom", "UK", "Brazil", "Indonesia", "Malaysia", "Philippines",
    "Turkey", "Poland", "Czech Republic", "Netherlands", "Spain", "Cambodia",
)

_COUNTRY_CANON = {"uk": "United Kingdom", "korea": "South Korea"}

DEFAULT_DESTINATION = "United States"

SYSTEM = """You extract a trade lane from a question. Return JSON only.

Fields:
  hts_code    — the HTS subheading if the question states one, else null. NEVER invent one.
  product     — the product in plain words, else null.
  origin      — the country of origin as a full country name, else null.
  destination — the importing country as a full country name. Default "United States".
  intent      — "lane" for a question about a specific lane's duty treatment;
                "corpus" for a question about the knowledge base itself
                (what changed, what is stale, what do you cover);
                "other" for anything else.

Rules:
  Never guess or derive an HTS code from a product description. That is a human
  classification decision. If the question has no code, leave hts_code null.
  Normalise country names ("VN" -> "Vietnam", "the UK" -> "United Kingdom").
  Return only a JSON object, no prose and no code fences."""


@dataclass
class Normalized:
    intent: str = "lane"
    lane: Lane | None = None
    product: str | None = None
    origin: str | None = None
    destination: str = DEFAULT_DESTINATION
    hts_code: str | None = None
    needs_hts_code: bool = False
    needs_origin: bool = False
    partial_code: bool = False
    suggested_hts_code: str | None = None
    suggestion_basis: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.lane is not None


def _canon_country(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = name.strip().strip(".,")
    return _COUNTRY_CANON.get(cleaned.lower(), cleaned)


def _product_hint(text: str) -> tuple[str | None, str | None]:
    low = text.lower()
    for phrase, (code, label) in KNOWN_PRODUCTS.items():
        if phrase in low:
            return code, label
    return None, None


def heuristic(question: str) -> Normalized:
    """LLM-free path. Used as a fallback and to keep tests offline and cheap."""
    out = Normalized()
    low = question.lower()

    if any(p in low for p in ("what changed", "which lanes", "stale", "what do you cover",
                              "coverage", "how fresh", "refresh")):
        out.intent = "corpus"
        return out

    match = HTS_RE.search(question)
    if match:
        out.hts_code = match.group(1)

    for country in COUNTRY_HINTS:
        if re.search(rf"\b{re.escape(country)}\b", question, re.IGNORECASE):
            canon = _canon_country(country)
            if re.search(rf"(?:into|to)\s+(?:the\s+)?{re.escape(country)}\b", question, re.IGNORECASE):
                out.destination = canon or DEFAULT_DESTINATION
            elif out.origin is None:
                out.origin = canon
    hint_code, hint_label = _product_hint(question)
    out.product = hint_label

    if out.hts_code is None and hint_code:
        out.suggested_hts_code = hint_code
        out.suggestion_basis = "matched a known demo product; unconfirmed"

    _finalize(out)
    return out


def digits_in(code: str | None) -> int:
    return sum(c.isdigit() for c in str(code or ""))


def _finalize(out: Normalized) -> None:
    if out.intent != "lane":
        return
    # A base rate lives on a full statistical line (8 or 10 digits). A 4-digit heading
    # or 6-digit subheading spans many lines with very different rates — footwear under
    # heading 6404 runs from free to over 30% — so there is no single rate to report.
    # Worth saying before spending runs on an unanswerable question.
    if out.hts_code and digits_in(out.hts_code) < 8:
        out.partial_code = True
    if out.hts_code and out.origin:
        out.lane = Lane(
            hts_code=out.hts_code,
            origin=out.origin,
            destination=out.destination or DEFAULT_DESTINATION,
            product=out.product or "",
        )
        return
    if not out.hts_code:
        out.needs_hts_code = True
        out.notes.append(
            "No HTS code in the question. Classification is a human decision — "
            "supply a code to continue."
        )
    if not out.origin:
        # Its own flag, not just a note. The "Use this" button prefills
        # "…from " with the country left blank, so a question with a code and no
        # origin is the *expected* intermediate state, not a malformed one.
        out.needs_origin = True
        out.notes.append("No country of origin in the question.")


def normalize(question: str, llm: Any | None = None) -> Normalized:
    """Normalize with an LLM when one is available, else fall back to heuristics."""
    if llm is None:
        return heuristic(question)

    try:
        raw = llm.complete(f"{SYSTEM}\n\nQuestion: {question}\nJSON:").text.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 — a bad key must not take the app down
        out = heuristic(question)
        out.notes.append("LLM normalization unavailable; used heuristics.")
        return out

    out = Normalized(
        intent=(data.get("intent") or "lane").strip().lower(),
        hts_code=(data.get("hts_code") or None),
        product=(data.get("product") or None),
        origin=_canon_country(data.get("origin")),
        destination=_canon_country(data.get("destination")) or DEFAULT_DESTINATION,
    )
    # Trust the model to read a code that is present, never to derive one.
    if out.hts_code and not HTS_RE.fullmatch(out.hts_code.strip()):
        out.notes.append(f"Discarded malformed hts_code from the model: {out.hts_code!r}")
        out.hts_code = None
    if out.hts_code is None and out.product:
        hint_code, _ = _product_hint(out.product)
        if hint_code:
            out.suggested_hts_code = hint_code
            out.suggestion_basis = "matched a known demo product; unconfirmed"
    _finalize(out)
    return out


def get_llm() -> Any | None:
    """The Anthropic LLM used for normalization and response synthesis."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from llama_index.llms.anthropic import Anthropic
    except ImportError:
        return None
    # claude-sonnet-5 verified against llama-index-llms-anthropic 0.11.10:
    # completes, and metadata resolves (1M context). Override with DESK_LLM_MODEL.
    return Anthropic(model=os.environ.get("DESK_LLM_MODEL", "claude-sonnet-5"),
                     max_tokens=2048)
