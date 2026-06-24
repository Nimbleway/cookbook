"""The agent: idea sentence -> DeliveryPackage, in 4 steps.

    see (Nimble) -> think (OpenRouter) -> check (name.com) -> build (OpenRouter+deploy)

Step 4 is still optional/bonus, but the Day-4 pipeline now runs end-to-end:
    python -m agent.orchestrator "an app that books last-minute dog groomers"
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Optional

from . import deliveries_store, naming
from .clients import llm, namecom, nimble
from .landing import publish_landing_page
from .schemas import (
    DeliveryPackage,
    DomainOption,
    DomainStrategy,
    LakehouseIntel,
    NameCandidate,
    PriorDelivery,
    ReconResult,
)

MAX_NAME_ROUNDS = 3  # retry guard so we never loop forever
MAX_IDEA_CHARS = 300


# Lightweight, request-scoped logging mirroring the bridge's format. Level from
# LOG_LEVEL (default INFO). Additive observability only — no behavior changes,
# no secrets logged. Configured here too (not just in server.py) so the CLI /
# Tower entrypoints get structured lines without importing the bridge.
def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("agent.orchestrator")
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("ts=%(asctime)s level=%(levelname)s logger=%(name)s %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    return logger


log = _setup_logger()


def _kv(**fields: object) -> str:
    """`key=value` context suffix; drops None and quotes values with spaces/`=`."""
    parts: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value)
        if text == "" or any(ch in text for ch in (" ", "=", '"')):
            text = '"' + text.replace('"', '\\"') + '"'
        parts.append(f"{key}={text}")
    return " ".join(parts)

# Off-by-default feature flag for the REAL tool-calling agent loop (agent_loop.py).
# "1" => try the agentic loop, but fall back to the deterministic pipeline below on
# ANY error/timeout/budget-exceeded. Default "0" => today's exact behavior, so the
# live demo is unbreakable. Read at call time so it can be toggled per-process.
def _agent_loop_enabled() -> bool:
    return os.getenv("AGENT_LOOP", "0").strip() == "1"

# The product's thesis TLD. `.delivery` IS the pitch — the agent doesn't suggest a
# startup, it *delivers* one onto its own namesake TLD. So every name is checked on
# `.delivery` first, it leads the TLD grid, and the winner is secured on `.delivery`
# whenever it's available (it almost always is — that's the whole move).
HERO_TLD = "delivery"

# TLDs we check every name against. `.delivery` leads (the thesis); `.com` follows so
# the "taken on .com, open on .delivery" contrast reads at a glance; then the rest.
# Order doubles as the winner-promotion preference: first AVAILABLE here is secured.
VARIANT_TLDS = (HERO_TLD, "com", "app", "ai", "io", "co")

# A step event sink. The bridge (agent/server.py) passes one in to stream
# see -> think -> check -> build to the UI; None means "just return the package"
# (the path tower_app.run and the CLI use).
EventSink = Optional[Callable[[str, dict], None]]


def _emit(on_event: EventSink, kind: str, data: dict) -> None:
    if on_event is not None:
        on_event(kind, data)


def _tracking_id() -> str:
    """A shipment tracking number for this delivery, e.g. DEL-20260603-A3F7C9B2."""
    return f"DEL-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(4).upper()}"


def new_tracking_id() -> str:
    """Public alias for ``_tracking_id()`` — lets callers pre-mint an id before
    starting a pipeline run (e.g. ``POST /jobs`` needs the id before spawning the
    thread so it can return it to the client immediately)."""
    return _tracking_id()


def _normalize_idea(idea: str) -> str:
    idea = " ".join((idea or "").split())
    if not idea:
        raise ValueError("Idea must be non-empty")
    if len(idea) > MAX_IDEA_CHARS:
        raise ValueError(f"Idea must be {MAX_IDEA_CHARS} characters or fewer")
    return idea


def _variant_tlds(chosen: str) -> list[str]:
    """The TLD order for one name: `.delivery` always leads (the thesis), then the
    rest of the set in desirability order, then the LLM's own pick if it's exotic.

    This order is also the winner-promotion preference, so an available `.delivery`
    is what gets secured — the signature move — while `.com`/`.app`/… still render
    in the grid (showing the taken-vs-open contrast).
    """
    tlds: list[str] = [HERO_TLD]
    for tld in VARIANT_TLDS:
        if tld not in tlds:
            tlds.append(tld)
    if chosen and chosen not in tlds:
        tlds.append(chosen)
    return tlds


def _label_and_tld(domain: str) -> tuple[str, str]:
    parts = [p for p in domain.strip().lower().split(".") if p]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if len(parts) == 1:
        return parts[0], "com"
    return "", "com"


# name.com rejects >50 domains per request. We batch well under that so future
# TLD additions (which widen each candidate's variant set) keep a safe margin, and
# so a single agent round proposing many candidates can't overflow one request.
_NAMECOM_BATCH = 45


def _chunked(items: list[str], size: int) -> list[list[str]]:
    """Split `items` into consecutive chunks of at most `size` (order preserved)."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _check_domains_batched(domains: list[str]) -> dict[str, "namecom.DomainStatus"]:
    """Availability for any number of domains, chunk-safe under name.com's 50 cap.

    Splits into <=45-domain batches and merges the per-batch status dicts. For the
    common (<=45) case this is exactly one call — unchanged from the prior behavior.
    name.com's own 50-guard stays intact as a backstop.
    """
    statuses: dict[str, "namecom.DomainStatus"] = {}
    for batch in _chunked(domains, _NAMECOM_BATCH):
        statuses.update(namecom.check_domains(batch))
    return statuses


def _check_candidates(
    candidates: list[NameCandidate], on_event: EventSink = None
) -> list[NameCandidate]:
    """Check every candidate name across several TLDs in one batched name.com call.

    Each returned candidate carries `variants` (.com/.app/.ai/...) and has its
    primary domain promoted to the most desirable AVAILABLE TLD, so the winner is
    a real, buyable domain rather than whatever TLD the LLM happened to suggest.
    """
    # Build the full (label, tld) -> domain map, then one deduped batch request.
    plans: list[tuple[NameCandidate, str, list[str]]] = []
    all_domains: list[str] = []
    for candidate in candidates:
        label, chosen = _label_and_tld(candidate.domain)
        if not label:
            plans.append((candidate, "", []))
            continue
        tlds = _variant_tlds(chosen)
        domains = [f"{label}.{tld}" for tld in tlds]
        plans.append((candidate, label, tlds))
        all_domains.extend(domains)

    unique_domains = list(dict.fromkeys(d.lower() for d in all_domains))
    statuses = _check_domains_batched(unique_domains) if unique_domains else {}

    checked: list[NameCandidate] = []
    for candidate, label, tlds in plans:
        variants: list[DomainOption] = []
        for tld in tlds:
            domain = f"{label}.{tld}"
            available, price, renewal, premium = statuses.get(
                domain.lower(), (False, None, None, False)
            )
            variants.append(
                DomainOption(
                    domain=domain,
                    tld=tld,
                    available=available,
                    price_usd=price,
                    renewal_price_usd=renewal,
                    premium=bool(premium),
                )
            )

        # Primary = first AVAILABLE NON-PREMIUM variant in desirability order, so the
        # winner secured on stage is the cheap thesis pick (`.delivery`) and never an
        # eye-watering premium/aftermarket name (e.g. a $199 .ai) just because it
        # happened to be the first available variant. Only if NO non-premium variant
        # is available do we fall back to a premium one; else keep the LLM's original
        # domain (marked unavailable) so the row still renders.
        primary = next((v for v in variants if v.available and not v.premium), None)
        if primary is None:
            primary = next((v for v in variants if v.available), None)
        if primary is not None:
            update = {
                "domain": primary.domain,
                "available": True,
                "price_usd": primary.price_usd,
                "variants": variants,
            }
        else:
            update = {"available": False, "variants": variants}

        result = candidate.model_copy(update=update)
        checked.append(result)
        # One event per candidate — the HERO moment (TLD grid: taken ❌ vs open ✅ + price).
        _emit(on_event, "check", {"candidate": result})
    return checked


def _launch_kit(pick: NameCandidate) -> list[DomainOption]:
    """Defensive domains to lock the brand: the .com plus get-/try- prefixes.

    A curated bundle (distinct from the TLD grid and name.com's suggestions) that
    a founder would register to protect the name. Only available ones are returned.
    Best-effort: a name.com hiccup just yields an empty kit."""
    label, chosen = _label_and_tld(pick.domain)
    if not label:
        return []
    candidates: list[str] = []
    if chosen != "com":
        candidates.append(f"{label}.com")
    candidates.append(f"get{label}.com")
    candidates.append(f"try{label}.com")

    # Dedupe (case-insensitive) and drop the pick itself.
    uniq = [
        d for d in dict.fromkeys(c.lower() for c in candidates) if d != pick.domain.strip().lower()
    ]
    if not uniq:
        return []
    try:
        statuses = namecom.check_domains(uniq)
    except Exception:
        return []

    kit: list[DomainOption] = []
    for domain in uniq:
        available, price, renewal, premium = statuses.get(domain.lower(), (False, None, None, False))
        if available:
            kit.append(
                DomainOption(
                    domain=domain,
                    tld=domain.rsplit(".", 1)[-1],
                    available=True,
                    price_usd=price,
                    renewal_price_usd=renewal,
                    premium=bool(premium),
                )
            )
    return kit


def deliver_startup(
    idea: str,
    *,
    build_landing: bool = False,
    on_event: EventSink = None,
    tracking_id: str | None = None,
) -> DeliveryPackage:
    # Pre-mint (or accept) the tracking id now so callers that already recorded a
    # jobs_store entry (e.g. POST /jobs, GET /deliver/stream) can correlate events.
    # The deterministic path and the agent-loop path both receive it so only ONE id
    # is ever used for the whole run, even across a fallback.
    tracking_id = (tracking_id or "").strip() or _tracking_id()

    # OPT-IN agentic path (AGENT_LOOP=1): let the LLM drive a real tool-calling
    # loop. It emits the SAME see/think/verdict/check/secured events (plus optional
    # `step` narration) and returns an equivalent DeliveryPackage. On ANY failure
    # (error, timeout, budget) we fall straight through to the deterministic body
    # below — the guaranteed, unbreakable fallback. Imported lazily to avoid any
    # import cost/cycle when the flag is off.
    if _agent_loop_enabled():
        try:
            from .agent_loop import run_agent_loop

            return run_agent_loop(
                idea,
                build_landing=build_landing,
                on_event=on_event,
                tracking_id=tracking_id,
            )
        except Exception as exc:  # noqa: BLE001 — never let the loop sink a delivery
            log.warning("agent_loop fell back to deterministic pipeline " + _kv(error=repr(exc)))
            # Intentional fall-through to the deterministic pipeline below.

    _started = time.monotonic()
    idea = _normalize_idea(idea)
    log.info("deliver_startup start " + _kv(trackingId=tracking_id, buildLanding=build_landing))
    # Emit the tracking number up front so the UI can stamp it on the shipment
    # the moment the run starts, not just at the end.
    _emit(on_event, "start", {"idea": idea, "trackingId": tracking_id})

    # STEP 1 — SEE: live competitor recon (Nimble)
    recon: ReconResult = nimble.research_idea(idea)
    _emit(
        on_event,
        "see",
        {
            "competitors": recon.competitors,
            "marketSummary": recon.market_summary,
            "reconAt": recon.recon_at,
            "reconFromCache": recon.recon_from_cache,
            "marketHeat": recon.market_heat,
            "complaints": recon.complaints,
        },
    )

    # STEP 2 — THINK: find the gap + propose names (OpenRouter)
    # Cross-idea learning: avoid brands already delivered for overlapping ideas, so
    # the lakehouse makes naming smarter over time (a moat prompt-only tools lack).
    prior = deliveries_store.for_niche(idea)
    avoid = [
        NameCandidate(name=str(p.get("brand", "")), domain=str(p.get("domain", "")))
        for p in prior
        if p.get("brand") and p.get("domain")
    ]
    learned_from = [
        PriorDelivery(
            brand=str(p.get("brand", "")),
            domain=str(p.get("domain", "")),
            tracking_id=p.get("tracking_id"),
        )
        for p in prior
        if p.get("brand") and p.get("domain")
    ]
    # Aggregate lakehouse intelligence for this niche — the "data-to-AI" loop.
    # Composed from the local deliveries mirror (never the Tower Iceberg table, which
    # isn't installed in prod). Fed BACK INTO the LLM prompts below as grounding AND
    # surfaced on the package. Best-effort: a read hiccup never sinks a delivery.
    niche_intel: dict | None = None
    try:
        niche_intel = deliveries_store.niche_intel(idea)
    except Exception:
        niche_intel = None
    recon.positioning_gap, candidates = llm.find_gap_and_names(
        recon, avoid=avoid, niche_intel=niche_intel
    )
    # Deterministic brandability re-rank (pure, offline): reorder so the most
    # brandable, NON-colliding name leads — that's the one the .delivery-first TLD
    # check below tends to secure. Drops any incumbent-host collision (keeps >=1).
    candidates = naming.rank_candidates(candidates, recon)
    _emit(
        on_event,
        "think",
        {
            "positioningGap": recon.positioning_gap,
            "candidates": candidates,
            "learnedFrom": len(avoid),
        },
    )

    # VERDICT — build/pivot/pass decision grounded in the recon + gap. Emitted
    # as its own event so the UI can lead the box with the actual decision.
    verdict = llm.assess_opportunity(recon, niche_intel=niche_intel)
    _emit(on_event, "verdict", {"verdict": verdict})

    # STEP 3 — CHECK: keep only buyable domains (name.com), loop if all taken
    winners: list[NameCandidate] = []
    tried: list[NameCandidate] = []
    for _round in range(MAX_NAME_ROUNDS):
        checked = _check_candidates(candidates, on_event=on_event)
        tried.extend(checked)
        winners = [c for c in checked if c.available]
        if winners:
            break
        if _round < MAX_NAME_ROUNDS - 1:
            # Only regenerate if there's another round to spend the names on.
            # If the LLM fails here, stop retrying and fall through to the clean
            # "no domains" RuntimeError below rather than leaking an LLM stack.
            try:
                candidates = llm.more_names(recon, exclude=tried)
            except Exception:
                break

    if not winners:
        raise RuntimeError("No available domains found after retries")

    pick = winners[0]
    _emit(on_event, "secured", {"candidate": pick})

    # name.com's OWN suggestions for the winning brand (alternative TLDs/variants)
    # — uses name.com as an active suggester, not just an availability check.
    # Best-effort; never blocks the delivery.
    # name.com's own alternates + a defensive bundle for the winner. Both ride out
    # on the final package (the UI renders them in the unbox), so no live event.
    pick_label, _pick_tld = _label_and_tld(pick.domain)
    suggestions = namecom.suggest_domains(pick_label) if pick_label else []
    suggestions = [s for s in suggestions if s.domain.lower() != pick.domain.lower()]
    launch_kit = _launch_kit(pick)

    # DOMAIN STRATEGIST — the prize-aligned reasoning layer. Reasons OVER the real
    # name.com data just secured for the winner (the renewal cliff, premium traps,
    # exact-match .com vs the .delivery thesis, the defensive kit) and narrates a
    # per-delivery strategy. Best-effort: every callout is deterministic from real
    # fields and the one LLM line has its own fallback, but we still guard the whole
    # thing so a hiccup here can never sink the delivery.
    domain_strategy: DomainStrategy | None = None
    try:
        domain_strategy = llm.domain_strategy(
            pick,
            launch_kit=launch_kit,
            hero_tld=HERO_TLD,
            idea=idea,
            positioning_gap=recon.positioning_gap or "",
        )
    except Exception as exc:  # noqa: BLE001 — strategy is a bonus, never a blocker
        log.warning(
            "domain_strategy skipped " + _kv(trackingId=tracking_id, error=repr(exc))
        )
        domain_strategy = None

    # OWNABILITY — "the verdict sharpens once we secure the real domain" beat.
    # The streamed `verdict` event (above, pre-ownership) is left UNTOUCHED. Here,
    # AFTER the winner is secured, we fold the REAL secured-domain economics
    # (`pick.variants` — the TLD grid with available/premium/renewal/price) into a
    # COPY of the verdict as one more cited ownability ScoreFactor, nudging the
    # score but NEVER the call (clamped to the call band + anchor band). GATED on
    # name.com trustworthiness: in the sandbox availability is a lie, so we add no
    # factor and the verdict is returned unchanged. Pure + fail-safe in llm.py.
    try:
        _trustworthy = bool(namecom.domain_source_status().get("trustworthy"))
    except Exception:
        _trustworthy = False
    package_verdict = llm.augment_verdict_with_ownability(
        verdict, pick, trustworthy=_trustworthy
    )

    # STEP 4 — BUILD: landing page grounded in real recon (static artifact, no DNS/TLS bet)
    landing_url: str | None = None
    if build_landing:
        _emit(on_event, "build", {"domain": pick.domain})
        landing_html = llm.write_landing_page(pick, recon)
        landing_url = publish_landing_page(pick.domain, landing_html)

    # Attach the lakehouse intelligence summary so the result can show the same
    # aggregate signal the prompts were grounded in. Only when there's real niche
    # history (deliveries_in_theme > 0) so the panel stays focused; None otherwise.
    lakehouse_intel: LakehouseIntel | None = None
    if niche_intel and niche_intel.get("deliveries_in_theme"):
        try:
            lakehouse_intel = LakehouseIntel(**niche_intel)
        except Exception:
            lakehouse_intel = None

    package = DeliveryPackage(
        idea=idea,
        brand=pick.name,
        domain=pick.domain,
        price_usd=pick.price_usd,
        positioning_gap=recon.positioning_gap or "",
        market_summary=recon.market_summary,
        competitors=recon.competitors,
        landing_url=landing_url,
        recon_at=recon.recon_at,
        recon_from_cache=recon.recon_from_cache,
        market_heat=recon.market_heat,
        domain_options=pick.variants,
        tracking_id=tracking_id,
        verdict=package_verdict,
        suggestions=suggestions,
        complaints=recon.complaints,
        launch_kit=launch_kit,
        learned_from=learned_from,
        lakehouse_intel=lakehouse_intel,
        domain_strategy=domain_strategy,
    )

    # Mirror into the local deliveries log (powers the Loading Dock + cross-idea
    # learning). Best-effort: never fail a delivery because the log write hiccuped.
    try:
        deliveries_store.record(package.model_dump(mode="json"))
    except Exception as exc:
        log.warning("deliveries_store.record skipped " + _kv(trackingId=tracking_id, error=repr(exc)))

    log.info(
        "deliver_startup done "
        + _kv(
            trackingId=tracking_id,
            domain=pick.domain,
            verdict=verdict.call if verdict else None,
            priorInNiche=len(learned_from),
            elapsedMs=int((time.monotonic() - _started) * 1000),
        )
    )
    return package


def refine_names(
    idea: str,
    *,
    gap: str = "",
    angle: str | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[str, list[NameCandidate]]:
    """Re-run naming for a founder-steered angle, without re-burning live recon.

    Recon is cached, so this is cheap: we reuse it, set the gap to the founder's
    `angle` (or the existing `gap`), generate a fresh batch of names avoiding
    `exclude_domains`, and check them across TLDs. Returns (effective_gap, checked).
    """
    idea = _normalize_idea(idea)
    recon: ReconResult = nimble.research_idea(idea)  # cached -> cheap
    effective_gap = (angle or gap or recon.positioning_gap or "").strip()
    recon.positioning_gap = effective_gap

    exclude = [
        NameCandidate(name="", domain=d.strip())
        for d in (exclude_domains or [])
        if d and d.strip()
    ]
    candidates = llm.more_names(recon, exclude=exclude)
    return effective_gap, _check_candidates(candidates)


@dataclass(frozen=True)
class LandingBuild:
    """Result of `build_landing_only`: the generated HTML always; the published
    URL best-effort.

    `landing_html` is the raw LLM-generated landing-page HTML — the frontend can
    render it directly in a hostless sandboxed `<iframe srcdoc>` preview, which
    works even on Vercel (no file hosting needed). `landing_url` is the legacy
    same-origin file path from `publish_landing_page`; it is None when file
    hosting is unavailable (e.g. hosted Vercel can't see files the Fly bridge
    wrote), but the HTML is never lost on that path."""

    landing_html: str
    landing_url: str | None


def build_landing_only(idea: str, brand: str, domain: str) -> LandingBuild:
    """Build ONLY the landing page for an already-delivered package — cheap.

    This is the dedicated path behind the UI's "Also build a live landing page"
    action. Unlike `deliver_startup`, it does NOT mint a tracking id, does NOT
    record a deliveries-log row, and does NOT re-derive the brand/domain — it
    reuses the brand/domain the founder already claimed and the CACHED recon
    (nimble.research_idea is cached on the /data volume, so no quota is burned).

    Returns a `LandingBuild` carrying the generated HTML (always) and the
    best-effort published URL. Publishing is wrapped so a file-write failure
    (the common case on hosted Vercel) does NOT lose the HTML — the srcdoc
    preview only needs the string.

    Best-effort by contract for the caller, but we raise on a genuine failure
    (bad input, LLM error) so the bridge can surface a graceful 502.
    """
    idea = _normalize_idea(idea)
    recon: ReconResult = nimble.research_idea(idea)  # cached -> cheap, no quota burn
    pick = NameCandidate(name=brand, domain=domain)
    html = llm.write_landing_page(pick, recon)
    landing_url: str | None = None
    try:
        landing_url = publish_landing_page(domain, html)
    except Exception as exc:  # file hosting may be unavailable (hosted Vercel) — keep the html
        log.warning("build_landing_only publish skipped " + _kv(domain=domain, error=repr(exc)))
    return LandingBuild(landing_html=html, landing_url=landing_url)


if __name__ == "__main__":
    idea = " ".join(sys.argv[1:]) or "an app that books last-minute dog groomers"
    print(deliver_startup(idea).model_dump_json(indent=2))
