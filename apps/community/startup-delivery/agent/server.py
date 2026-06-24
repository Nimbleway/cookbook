"""Local FastAPI bridge: SvelteKit API route -> the Python agent.

Two surfaces over the same pipeline (`orchestrator.deliver_startup`):

    POST /deliver           one-shot; returns the final DeliveryPackage (camelCase)
    GET  /deliver/stream    Server-Sent Events of the 4 steps (see -> think -> check -> build)

Tower is OFF the critical path in prod. Persisting to the Tower-managed Iceberg
`deliveries` table is opt-in (`TOWER_PERSIST=1`) and best-effort; the always-local
JSONL log (deliveries_store) is the system of record everything here reads from.
Run it with:

    source agent/.venv/bin/activate
    uvicorn agent.server:app --port 8787 --reload

The SvelteKit route (web/src/routes/api/deliver/...) proxies here via AGENT_URL.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import deliveries_store, jobs_store
from ._env import env_int
from .clients import namecom
from .orchestrator import build_landing_only, deliver_startup, new_tracking_id, refine_names
from .schemas import (
    Competitor,
    DeliveryPackage,
    DomainOption,
    DomainStrategy,
    LakehouseIntel,
    MarketHeat,
    NameCandidate,
    Outcome,
    Verdict,
)

# Tower persist is OPT-IN and OFF by default (dev AND prod). The local JSONL log
# (deliveries_store) is the system of record; Tower is only an optional mirror, so
# the deployed bridge never depends on it. Set TOWER_PERSIST=1 to also mirror.
PERSIST_TO_TOWER = os.getenv("TOWER_PERSIST", "0") == "1"
TOWER_APP = os.getenv("TOWER_APP", "startup-delivery-orchestrator")

# Shared secret guarding both delivery surfaces. Empty => local dev, no check.
# The only real caller is the server-side SvelteKit route, which sends x-bridge-secret.
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")

# Global cap on concurrent pipeline runs so a flood can't spawn unlimited work.
MAX_CONCURRENCY = env_int("MAX_CONCURRENCY", 4)
_PIPELINE_SLOTS = threading.Semaphore(MAX_CONCURRENCY)

# Hard cap on the landing HTML we return for the hostless srcdoc preview. The
# string is LLM-generated/untrusted and only fed to a fully-sandboxed iframe,
# but we still bound the payload so a runaway generation can't bloat responses.
MAX_LANDING_HTML_BYTES = 250 * 1024  # ~250 KB

# New tracking IDs use 8 suffix chars; 4-char legacy IDs remain readable for
# already-shared demo links.
TRACKING_ID_RE = re.compile(r"^DEL-[0-9]{8}-(?:[A-Z0-9]{4}|[A-Z0-9]{8})$", re.IGNORECASE)


def _valid_tracking_id(value: str) -> bool:
    return bool(TRACKING_ID_RE.fullmatch((value or "").strip()))


# ---- structured, request-scoped logging (additive; replaces bare print()) ----
# Lightweight key=value lines on stdout. Level from LOG_LEVEL (default INFO).
# Each delivery is stamped with its trackingId and step/lifecycle boundaries log
# elapsed_ms where it's cheap. Never logs secrets — only names/presence elsewhere.

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("agent.bridge")
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("ts=%(asctime)s level=%(levelname)s logger=%(name)s %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False  # don't double-log through the root handler
    return logger


log = _setup_logger()


def _kv(**fields: Any) -> str:
    """Render context fields as a `key=value` suffix. None values are dropped and
    values with whitespace/`=` are JSON-quoted so each line stays parseable."""
    parts: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value)
        if text == "" or any(ch in text for ch in (" ", "=", '"')):
            text = json.dumps(text, ensure_ascii=False)
        parts.append(f"{key}={text}")
    return " ".join(parts)


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)

# Env vars the bridge can't actually serve a delivery without. /ready checks their
# PRESENCE only (never their value, never a live provider call) so a deploy that is
# missing a secret fails its health gate instead of going live broken.
_REQUIRED_ENV = (
    "NIMBLE_API_KEY",
    "OPENROUTER_API_KEY",
    "NAMECOM_USERNAME",
    "NAMECOM_API_TOKEN",
    "BRIDGE_SECRET",
)


def _free_slots() -> int:
    """Best-effort count of idle pipeline slots (informational only)."""
    return getattr(_PIPELINE_SLOTS, "_value", MAX_CONCURRENCY)


def _log_dir_writable() -> tuple[str, bool]:
    """Resolve the deliveries-log dir and whether we can write into it.

    Cheap and side-effect-free: we create the parent dir if missing (the store does
    this lazily anyway) and probe with os.access — no provider/network calls."""
    log_path = deliveries_store._path()
    log_dir = log_path.parent
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return str(log_path), False
    return str(log_path), os.access(log_dir, os.W_OK)


def _env_presence() -> dict[str, bool]:
    """Map each required env var name -> present?(non-empty). Values never leak."""
    return {name: bool(os.environ.get(name, "").strip()) for name in _REQUIRED_ENV}


def require_secret(x_bridge_secret: str = Header(default="")) -> None:
    """Reject calls without the shared secret (only enforced when one is set)."""
    if BRIDGE_SECRET and x_bridge_secret != BRIDGE_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")


def _run_domain_control_check() -> None:
    """Boot-time control-check of the configured name.com backend (best-effort).

    Runs in a daemon thread off the startup path so boot is never blocked by a
    name.com round-trip (or its timeout). On a SANDBOX classification it logs a
    LOUD warning — the sandbox reports registered domains as buyable, which would
    be a credibility-ending lie if it surfaced as 'live availability'. The result
    is cached in-memory in namecom and read (no I/O) by /health and /debug.

    Never logs secret values — only the base url + classification."""
    try:
        status = namecom.run_control_check()
    except Exception as exc:  # run_control_check is already fail-safe; belt + braces
        log.warning("domain.control_check error " + _kv(error=repr(exc)))
        return

    env = status.get("env")
    base = status.get("base")
    if env == "sandbox":
        log.warning(
            "!!! name.com SANDBOX DETECTED — prices are NOT real availability; "
            "registered domains report as buyable. Configure production "
            "(NAMECOM_API_BASE=https://api.name.com + a non -test username) "
            "before trusting domain results. "
            + _kv(domainSourceEnv=env, namecomApiBase=base, trustworthy=status.get("trustworthy"))
        )
    elif env == "production":
        log.info(
            "domain.control_check ok "
            + _kv(domainSourceEnv=env, namecomApiBase=base, trustworthy=status.get("trustworthy"))
        )
    else:  # unconfigured / unverified
        log.warning(
            "domain.control_check unverified "
            + _kv(
                domainSourceEnv=env,
                namecomApiBase=base,
                trustworthy=status.get("trustworthy"),
                detail=status.get("detail"),
            )
        )


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Startup hook: kick the name.com control-check off-thread so boot is never
    blocked, then yield (no shutdown work)."""
    threading.Thread(
        target=_run_domain_control_check, name="domain-control-check", daemon=True
    ).start()
    yield


app = FastAPI(title="Startup.Delivery agent bridge", lifespan=_lifespan)

# The real caller is the server-side SvelteKit route, not a browser, so cross-origin
# browser access is off by default. Only enable CORS when CORS_ORIGINS is set.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "x-bridge-secret"],
    )


class DeliverRequest(BaseModel):
    idea: str = Field(min_length=1, max_length=300)  # 300 == MAX_IDEA_CHARS
    buildLanding: bool = False


class RefineRequest(BaseModel):
    idea: str = Field(min_length=1, max_length=300)
    gap: str = Field(default="", max_length=2000)
    angle: str | None = Field(default=None, max_length=600)
    excludeDomains: list[str] = Field(default_factory=list)


class BuildLandingRequest(BaseModel):
    idea: str = Field(min_length=1, max_length=300)  # 300 == MAX_IDEA_CHARS
    brand: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=253)  # max DNS name length


class OutcomeRequest(BaseModel):
    """The outcome-capture body. All optional; the route rejects an all-empty body
    (400) and a bad decision (400). camelCase to match the web proxy / contract.
    note is capped here AND again in the store before persisting."""

    verdictHelpful: bool | None = None  # thumbs on the verdict
    decision: str | None = Field(default=None, max_length=40)  # built|building|passed|considering|dead
    note: str = Field(default="", max_length=500)  # <=500 chars
    source: str | None = Field(default=None, max_length=40)  # where captured: "unbox" (weak) | "permalink" (strong); else "web"


# ---- serialization: snake_case pydantic -> the camelCase shapes web/lib/types.ts expects ----

def _competitor(c: Competitor) -> dict:
    return {
        "name": c.name,
        "url": c.url,
        "positioning": c.positioning,
        "pricing": c.pricing,
        "sourceUrl": c.source_url,
        "kind": c.kind,
    }


def _domain_option(o: DomainOption) -> dict:
    return {
        "domain": o.domain,
        "tld": o.tld,
        "available": o.available,
        "priceUsd": o.price_usd,
        "renewalPriceUsd": o.renewal_price_usd,
        "premium": o.premium,
    }


def _candidate(c: NameCandidate) -> dict:
    return {
        "name": c.name,
        "domain": c.domain,
        "available": c.available,
        "priceUsd": c.price_usd,
        "reasoning": c.reasoning,
        "variants": [_domain_option(v) for v in c.variants],
    }


def _verdict(v: Verdict | None) -> dict | None:
    if v is None:
        return None
    return {
        "call": v.call,
        "score": v.score,
        "confidence": v.confidence,
        "reconConfidence": v.recon_confidence,
        "headline": v.headline,
        "risks": v.risks,
        "nextSteps": v.next_steps,
        # The cited, signed factors that SUM to the score — one chip per factor on
        # the frontend (verdict.scoreBreakdown). Default [] keeps old records valid.
        "scoreBreakdown": [
            {
                "signal": f.signal,
                "label": f.label,
                "points": f.points,
                "evidence": f.evidence,
                "sourceUrl": f.source_url,
                "reliability": f.reliability,
            }
            for f in (v.score_breakdown or [])
        ],
    }


def _market_heat(h: MarketHeat | None) -> dict | None:
    if h is None:
        return None
    return {
        "niche": h.niche,
        "competitorCount": h.competitor_count,
        "crowded": h.crowded,
        "refreshedAt": h.refreshed_at,
    }


def _lakehouse_intel(li: LakehouseIntel | None) -> dict | None:
    if li is None:
        return None
    return {
        "deliveriesInTheme": li.deliveries_in_theme,
        "comTakenPct": li.com_taken_pct,
        "contestedThemes": li.contested_themes,
        "totalDelivered": li.total_delivered,
        "steerNote": li.steer_note,
    }


def _domain_strategy(s: DomainStrategy | None) -> dict | None:
    if s is None:
        return None
    return {
        "thesis": s.thesis,
        "renewalNote": s.renewal_note,
        "premiumWarning": s.premium_warning,
        "comVsDelivery": s.com_vs_delivery,
        "defensiveNote": s.defensive_note,
        "recommendation": s.recommendation,
    }


def _outcome(o: Outcome | None) -> dict | None:
    """The folded-in latest outcome (camelCase). None when none captured."""
    if o is None:
        return None
    return {
        "verdictHelpful": o.verdict_helpful,
        "decision": o.decision,
        "note": o.note,
        "capturedAt": o.captured_at,
        "source": o.source,
    }


def _package(p: DeliveryPackage) -> dict:
    return {
        "idea": p.idea,
        "brand": p.brand,
        "domain": p.domain,
        "priceUsd": p.price_usd,
        "positioningGap": p.positioning_gap,
        "marketSummary": p.market_summary,
        "competitors": [_competitor(c) for c in p.competitors],
        "landingUrl": p.landing_url,
        "reconAt": p.recon_at,
        "reconFromCache": p.recon_from_cache,
        "marketHeat": _market_heat(p.market_heat),
        "domainOptions": [_domain_option(o) for o in p.domain_options],
        "trackingId": p.tracking_id,
        "verdict": _verdict(p.verdict),
        "suggestions": [_domain_option(o) for o in p.suggestions],
        "complaints": p.complaints,
        "launchKit": [_domain_option(o) for o in p.launch_kit],
        "learnedFrom": [
            {"brand": x.brand, "domain": x.domain, "trackingId": x.tracking_id} for x in p.learned_from
        ],
        "lakehouseIntel": _lakehouse_intel(p.lakehouse_intel),
        "domainStrategy": _domain_strategy(p.domain_strategy),
        # Deepened recon-time signals (Agent A). camelCase, optional — the frontend
        # renders them only if present and degrades gracefully on the defaults.
        # getattr keeps this safe for any older package object missing the fields.
        "complaintSeverity": getattr(p, "complaint_severity", None),
        "pricedCompetitorCount": getattr(p, "priced_competitor_count", 0),
        "pricingBand": getattr(p, "pricing_band", None),
        "reconConfidence": getattr(p, "recon_confidence", None),
        # The LATEST captured outcome (thumbs + build/pass decision), folded in by
        # deliveries_store. camelCase, null when none captured — CAPTURE-ONLY, not
        # fed into the score. getattr keeps older package objects safe.
        "outcome": _outcome(getattr(p, "outcome", None)),
    }


def _jsonable(value: Any) -> Any:
    """Make orchestrator event payloads JSON-safe (they carry pydantic objects)."""
    if isinstance(value, Competitor):
        return _competitor(value)
    if isinstance(value, DomainOption):
        return _domain_option(value)
    if isinstance(value, MarketHeat):
        return _market_heat(value)
    if isinstance(value, Verdict):
        return _verdict(value)
    if isinstance(value, DomainStrategy):
        return _domain_strategy(value)
    if isinstance(value, NameCandidate):
        return _candidate(value)
    if isinstance(value, DeliveryPackage):
        return _package(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _persist(pkg: DeliveryPackage) -> None:
    """Optionally mirror the delivery into the Tower Iceberg `deliveries` table.

    OFF by default (PERSIST_TO_TOWER): Tower is never on the critical path. The
    local JSONL log (deliveries_store) is the system of record. The Iceberg catalog
    is only configured inside the Tower runtime, so when enabled we hand the exact
    package to the deployed Tower app (detached) rather than writing from this
    process. Best-effort: a Tower hiccup never fails the user's request."""
    if not PERSIST_TO_TOWER:
        return
    try:
        proc = subprocess.Popen(
            [
                "tower", "run", TOWER_APP, "-d",
                "-p", "mode=persist",
                "-p", f"package_json={pkg.model_dump_json()}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # `-d` returns quickly, so reap the child off-thread to avoid zombies
        # piling up over a demo session. Daemon thread: never blocks the request.
        threading.Thread(target=proc.wait, daemon=True).start()
    except Exception as exc:  # never fail the request because Tower hiccuped
        log.warning("tower.persist skipped " + _kv(error=repr(exc)))


class RemixRequest(BaseModel):
    idea: str = Field(min_length=1, max_length=300)
    gap: str = Field(default="", max_length=2000)


@app.get("/health")
def health() -> dict:
    """Liveness: always 200 while the process is up. Fly's probe + load balancers
    rely on this staying light, so do NO I/O and NO provider calls here. The
    `env` summary is a cheap present/absent map (never values) for a quick glance;
    use /ready for the gating readiness check.

    `domainSource` is the cached verdict of the boot name.com control-check — a
    pure in-memory read (NO provider I/O here), so the UI can honestly badge
    sandbox vs production availability."""
    return {
        "ok": True,
        "persist": PERSIST_TO_TOWER,
        "env": _env_presence(),
        "domainSource": namecom.domain_source_status(),
    }


@app.get("/ready")
def ready():
    """Readiness gate (what Fly health-checks): 200 only when every load-bearing
    env var is PRESENT and the deliveries-log dir is writable; otherwise 503 with a
    JSON list of what's missing. Cheap by design — presence + a writable probe only,
    NO live provider APIs and NO name.com quota burned here."""
    presence = _env_presence()
    missing = [name for name, present in presence.items() if not present]

    log_path, writable = _log_dir_writable()
    if not writable:
        missing.append("deliveries-log-dir-writable")

    body = {
        "ready": not missing,
        "missing": missing,
        "deliveriesLogPath": log_path,
        "deliveriesLogWritable": writable,
    }
    if missing:
        return JSONResponse(body, status_code=503)
    return body


@app.get("/debug", dependencies=[Depends(require_secret)])
def debug() -> dict:
    """Secret-gated, NON-SECRET config snapshot for confirming prod config at a
    glance (e.g. from the browser via the SvelteKit /api/debug proxy). NEVER returns
    a secret value — only names/presence, the active model, and the name.com base
    (so you can tell dev vs prod), the boot control-check verdict (domainSource),
    persist flag, concurrency, free slots, and the deliveries-log path + line
    count + writable bool."""
    log_path, writable = _log_dir_writable()
    try:
        line_count = deliveries_store.count_all()
    except Exception:
        line_count = -1
    return {
        "openrouterModel": os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4"),
        "namecomApiBase": os.getenv("NAMECOM_API_BASE", "https://api.dev.name.com"),
        "persist": PERSIST_TO_TOWER,
        "towerApp": TOWER_APP,
        "maxConcurrency": MAX_CONCURRENCY,
        "freePipelineSlots": _free_slots(),
        "agentLoop": os.getenv("AGENT_LOOP", "0").strip() == "1",
        "envPresent": _env_presence(),
        "domainSource": namecom.domain_source_status(),
        "deliveriesLogPath": log_path,
        "deliveriesLogLineCount": line_count,
        "deliveriesLogWritable": writable,
    }


@app.post("/remix", dependencies=[Depends(require_secret)])
def remix(req: RemixRequest) -> dict:
    """Three adjacent idea variants to branch this delivery into (one LLM call)."""
    from .clients import llm

    try:
        return {"variants": llm.adjacent_angles(req.idea, req.gap)}
    except Exception as exc:
        log.warning("remix failed " + _kv(error=repr(exc)))
        return {"variants": []}


@app.post("/refine", dependencies=[Depends(require_secret)])
def refine(req: RefineRequest):
    """Founder-steered re-naming for a different angle (reuses cached recon)."""
    if not _PIPELINE_SLOTS.acquire(blocking=False):
        log.info("refine rejected " + _kv(reason="busy", freeSlots=_free_slots()))
        return JSONResponse({"error": "busy"}, status_code=429)
    start = time.monotonic()
    try:
        gap, candidates = refine_names(
            req.idea, gap=req.gap, angle=req.angle, exclude_domains=req.excludeDomains[:50]
        )
        log.info(
            "refine done " + _kv(candidates=len(candidates), elapsedMs=_elapsed_ms(start))
        )
        return {"gap": gap, "candidates": [_candidate(c) for c in candidates]}
    except ValueError as exc:
        log.warning(
            "refine invalid input " + _kv(error=str(exc), elapsedMs=_elapsed_ms(start))
        )
        return JSONResponse({"error": "invalid input"}, status_code=400)
    except Exception as exc:
        log.error("refine failed " + _kv(error=repr(exc), elapsedMs=_elapsed_ms(start)))
        return JSONResponse({"error": "refine failed"}, status_code=502)
    finally:
        _PIPELINE_SLOTS.release()


@app.get("/deliveries")
def deliveries(limit: int = 24) -> dict:
    """Recent deliveries for the public 'Loading Dock' gallery.

    Reads the local deliveries log (the always-available mirror of the Tower
    Iceberg table). Best-effort: a malformed record is skipped, never fatal."""
    limit = max(1, min(60, limit))
    out: list[dict] = []
    for raw in deliveries_store.recent(limit=limit):
        try:
            out.append(_package(DeliveryPackage.model_validate(raw)))
        except Exception:
            continue
    return {"deliveries": out}


@app.get("/deliveries/stats")
def deliveries_stats() -> dict:
    """Aggregate market intelligence over the whole lakehouse (Dock stats panel)."""
    return deliveries_store.stats()


@app.get("/deliveries/{tracking_id}")
def delivery_by_id(tracking_id: str):
    """A single delivery by tracking id — backs the shareable /d/{id} permalink."""
    if not _valid_tracking_id(tracking_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    tracking_id = tracking_id.strip().upper()
    raw = deliveries_store.get(tracking_id)
    if not raw:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        return _package(DeliveryPackage.model_validate(raw))
    except Exception:
        return JSONResponse({"error": "not found"}, status_code=404)


@app.post("/deliveries/{tracking_id}/outcome", dependencies=[Depends(require_secret)])
def record_delivery_outcome(tracking_id: str, req: OutcomeRequest):
    """Capture what a founder DID with a verdict (thumbs + build/pass decision).

    SECRET-GATED. Validates the tracking id (404 on a malformed id), rejects an
    all-empty body and a bad decision enum (400), then appends the outcome to the
    durable sibling outcomes log (latest-wins). CAPTURE-ONLY: stored as a label
    for future calibration, NOT fed into the score. No provider calls.

    Returns { ok: true, outcome: { verdictHelpful, decision, note, capturedAt,
    source } } (camelCase) on success."""
    if not _valid_tracking_id(tracking_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    tracking_id = tracking_id.strip().upper()

    # Early all-empty guard for a clear 400 (the store also rejects, returning None).
    if req.verdictHelpful is None and not (req.decision or "").strip() and not req.note.strip():
        return JSONResponse({"error": "empty outcome"}, status_code=400)

    stamped = deliveries_store.record_outcome(
        tracking_id,
        {
            "verdict_helpful": req.verdictHelpful,
            "decision": req.decision,
            "note": req.note,
            # Provenance: distinguish the weak unbox thumbs from the stronger
            # permalink return-path label (for future outcome calibration).
            "source": req.source if req.source in ("unbox", "permalink") else "web",
        },
    )
    if stamped is None:
        # Invalid (bad decision enum) or empty after normalization.
        return JSONResponse({"error": "invalid outcome"}, status_code=400)

    log.info(
        "outcome captured "
        + _kv(
            trackingId=tracking_id,
            verdictHelpful=stamped.get("verdict_helpful"),
            decision=stamped.get("decision"),
            hasNote=bool(stamped.get("note")),
        )
    )
    return {"ok": True, "outcome": _outcome(Outcome.model_validate(stamped))}


@app.post("/deliver", dependencies=[Depends(require_secret)])
def deliver(req: DeliverRequest):
    if not _PIPELINE_SLOTS.acquire(blocking=False):
        log.info("deliver rejected " + _kv(reason="busy", freeSlots=_free_slots()))
        return JSONResponse({"error": "busy"}, status_code=429)
    start = time.monotonic()
    log.info("deliver start " + _kv(buildLanding=req.buildLanding, freeSlots=_free_slots()))
    try:
        pkg = deliver_startup(req.idea, build_landing=req.buildLanding)
        _persist(pkg)
        verdict = pkg.verdict.call if pkg.verdict else None
        log.info(
            "deliver done "
            + _kv(
                trackingId=pkg.tracking_id,
                domain=pkg.domain,
                verdict=verdict,
                elapsedMs=_elapsed_ms(start),
            )
        )
        return _package(pkg)
    except ValueError as exc:  # bad idea from _normalize_idea
        log.warning(
            "deliver invalid input " + _kv(error=str(exc), elapsedMs=_elapsed_ms(start))
        )
        return JSONResponse({"error": "invalid input"}, status_code=400)
    except Exception as exc:  # never leak provider/internal detail to the client
        log.error("deliver failed " + _kv(error=repr(exc), elapsedMs=_elapsed_ms(start)))
        return JSONResponse({"error": "delivery failed"}, status_code=502)
    finally:
        _PIPELINE_SLOTS.release()


def _cap_landing_html(html: str) -> str:
    """Bound the LLM-generated landing HTML to MAX_LANDING_HTML_BYTES (utf-8).

    Truncates on a UTF-8 boundary so the returned string is always valid for the
    sandboxed srcdoc preview. A truncated page may render slightly cut off, but
    that beats unbounded payloads; in practice generations are well under the cap.
    """
    if not html:
        return ""
    encoded = html.encode("utf-8")
    if len(encoded) <= MAX_LANDING_HTML_BYTES:
        return html
    return encoded[:MAX_LANDING_HTML_BYTES].decode("utf-8", errors="ignore")


@app.post("/build-landing", dependencies=[Depends(require_secret)])
def build_landing(req: BuildLandingRequest):
    """Build ONLY the landing page for an already-delivered package.

    The cheap counterpart to /deliver: it reuses the cached recon and the
    brand/domain the founder already claimed, so it mints NO tracking id and
    writes NO deliveries-log row. Returns {"landingHtml": html, "landingUrl": url}
    on success (landingHtml drives a hostless sandboxed srcdoc preview; landingUrl
    stays for back-compat where file hosting works) or a graceful JSON error —
    never crashes the bridge."""
    if not _PIPELINE_SLOTS.acquire(blocking=False):
        log.info("build-landing rejected " + _kv(reason="busy", freeSlots=_free_slots()))
        return JSONResponse({"error": "busy"}, status_code=429)
    start = time.monotonic()
    try:
        result = build_landing_only(req.idea, req.brand, req.domain)
        html = _cap_landing_html(result.landing_html)
        log.info(
            "build-landing done "
            + _kv(
                domain=req.domain,
                hasUrl=bool(result.landing_url),
                htmlBytes=len(html.encode("utf-8")),
                elapsedMs=_elapsed_ms(start),
            )
        )
        return {"landingHtml": html, "landingUrl": result.landing_url}
    except ValueError as exc:  # bad idea/brand/domain
        log.warning(
            "build-landing invalid input " + _kv(error=str(exc), elapsedMs=_elapsed_ms(start))
        )
        return JSONResponse({"error": "invalid input"}, status_code=400)
    except Exception as exc:  # never leak provider/internal detail to the client
        log.error("build-landing failed " + _kv(error=repr(exc), elapsedMs=_elapsed_ms(start)))
        return JSONResponse({"error": "build landing failed"}, status_code=502)
    finally:
        _PIPELINE_SLOTS.release()


@app.get("/deliver/stream", dependencies=[Depends(require_secret)])
async def deliver_stream(
    request: Request,
    idea: str = Query(..., min_length=1, max_length=300),  # 300 == MAX_IDEA_CHARS
    buildLanding: bool = False,
):
    """Stream the 4 steps as SSE. The blocking pipeline runs in a worker thread;
    its events are pushed onto a queue the async generator drains as `data:` lines.
    The async consumer heartbeats while idle and bails if the client disconnects.

    The run is also recorded in jobs_store so the client can resume polling via
    GET /jobs/{trackingId} even after disconnecting from this stream."""
    if not _PIPELINE_SLOTS.acquire(blocking=False):
        log.info("deliver.stream rejected " + _kv(reason="busy", freeSlots=_free_slots()))
        return JSONResponse({"error": "busy"}, status_code=429)

    # Pre-mint the tracking id and register the job before spawning the thread so
    # any poller that receives the id can immediately query GET /jobs/{id}.
    tid = new_tracking_id()
    jobs_store.start(tid, idea, build_landing=buildLanding)

    events: "queue.Queue[tuple[str, Any]]" = queue.Queue()
    _DONE = object()
    # Request-scoped context shared with the worker so each step/lifecycle line can
    # carry the trackingId (pre-minted above; also surfaced on `start` event).
    ctx: dict[str, Any] = {"trackingId": tid, "start": time.monotonic()}

    def on_event(kind: str, data: dict) -> None:
        if kind == "start" and isinstance(data, dict) and data.get("trackingId"):
            ctx["trackingId"] = data["trackingId"]
        payload = _jsonable(data)
        events.put((kind, payload))
        jobs_store.apply_event(ctx["trackingId"], kind, payload)
        # Step boundary at DEBUG so INFO stays a clean lifecycle view.
        log.debug(
            "deliver.stream step "
            + _kv(trackingId=ctx["trackingId"], step=kind, elapsedMs=_elapsed_ms(ctx["start"]))
        )

    def worker() -> None:
        log.info("deliver.stream start " + _kv(trackingId=tid, buildLanding=buildLanding, freeSlots=_free_slots()))
        try:
            pkg = deliver_startup(idea, build_landing=buildLanding, on_event=on_event, tracking_id=tid)
            _persist(pkg)
            pkg_payload = _package(pkg)
            events.put(("package", pkg_payload))
            jobs_store.finish(tid, pkg_payload)
            verdict = pkg.verdict.call if pkg.verdict else None
            log.info(
                "deliver.stream done "
                + _kv(
                    trackingId=pkg.tracking_id,
                    domain=pkg.domain,
                    verdict=verdict,
                    elapsedMs=_elapsed_ms(ctx["start"]),
                )
            )
        except Exception as exc:  # generic to the client; real detail stays server-side
            log.error(
                "deliver.stream failed "
                + _kv(
                    trackingId=ctx["trackingId"],
                    error=repr(exc),
                    elapsedMs=_elapsed_ms(ctx["start"]),
                )
            )
            events.put(("error", {"message": "delivery failed"}))
            jobs_store.fail(tid, "delivery failed")
        finally:
            events.put((_DONE, None))  # type: ignore[arg-type]
            _PIPELINE_SLOTS.release()  # free the slot even if the client vanished

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            if await request.is_disconnected():
                break  # client is gone; stop draining (worker finishes + releases)
            try:
                kind, data = await run_in_threadpool(events.get, True, 1.0)
            except queue.Empty:
                yield ": keep-alive\n\n"  # heartbeat so proxies don't time us out
                continue
            if kind is _DONE:
                break
            yield f"event: {kind}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"x-tracking-id": tid})


@app.post("/jobs", dependencies=[Depends(require_secret)])
def create_job(req: DeliverRequest) -> JSONResponse:
    """Start a durable background delivery job and return immediately.

    Unlike ``POST /deliver`` (which blocks until done) or ``GET /deliver/stream``
    (which ties progress to the browser connection), this endpoint spawns a daemon
    thread and returns a ``trackingId`` the client can poll via ``GET /jobs/{id}``.
    The job runs to completion server-side regardless of whether the client stays
    connected, and the final package is stored in both ``jobs_store`` and
    ``deliveries_store``."""
    if not _PIPELINE_SLOTS.acquire(blocking=False):
        log.info("jobs.create rejected " + _kv(reason="busy", freeSlots=_free_slots()))
        return JSONResponse({"error": "busy"}, status_code=429)

    tid = new_tracking_id()
    jobs_store.start(tid, req.idea, build_landing=req.buildLanding)
    start_time = time.monotonic()

    def worker() -> None:
        log.info(
            "jobs.worker start "
            + _kv(trackingId=tid, buildLanding=req.buildLanding, freeSlots=_free_slots())
        )
        try:
            pkg = deliver_startup(
                req.idea,
                build_landing=req.buildLanding,
                on_event=lambda k, d: jobs_store.apply_event(tid, k, _jsonable(d)),
                tracking_id=tid,
            )
            _persist(pkg)
            jobs_store.finish(tid, _package(pkg))
            verdict = pkg.verdict.call if pkg.verdict else None
            log.info(
                "jobs.worker done "
                + _kv(
                    trackingId=tid,
                    domain=pkg.domain,
                    verdict=verdict,
                    elapsedMs=_elapsed_ms(start_time),
                )
            )
        except ValueError as exc:
            log.warning(
                "jobs.worker invalid input "
                + _kv(trackingId=tid, error=str(exc), elapsedMs=_elapsed_ms(start_time))
            )
            jobs_store.fail(tid, "invalid input")
        except Exception as exc:
            log.error(
                "jobs.worker failed "
                + _kv(trackingId=tid, error=repr(exc), elapsedMs=_elapsed_ms(start_time))
            )
            jobs_store.fail(tid, "delivery failed")
        finally:
            _PIPELINE_SLOTS.release()

    threading.Thread(target=worker, daemon=True).start()
    return JSONResponse({"trackingId": tid, "status": "running"}, status_code=202)


@app.get("/jobs/{tracking_id}")
def get_job(tracking_id: str):
    """Poll a durable job by tracking id.

    Returns the full job envelope (including ``package`` when done). Not
    secret-gated — parity with ``GET /deliveries/{id}`` (the frontend proxy
    adds the secret anyway). Cheap by design: no provider calls, ~1 disk read
    per cold poll.

    Falls back to ``deliveries_store`` for completed jobs that were delivered
    before the jobs_store existed or whose job file has been pruned."""
    if not _valid_tracking_id(tracking_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    tracking_id = tracking_id.strip().upper()

    job = jobs_store.get(tracking_id)
    if job is not None:
        return job

    # Cold fallback: delivery completed but no job file (pre-existing delivery
    # or pruned entry).  Synthesise a done envelope from the deliveries log.
    raw = deliveries_store.get(tracking_id)
    if raw:
        try:
            model = DeliveryPackage.model_validate(raw)
            return {
                "status": "done",
                "trackingId": tracking_id.upper(),
                "idea": model.idea,
                "buildLanding": False,
                "phase": "done",
                "steps": [],
                "partial": None,
                "package": _package(model),
                "error": None,
                "createdAt": None,
                "updatedAt": None,
            }
        except Exception:
            pass

    return JSONResponse({"error": "not found"}, status_code=404)
