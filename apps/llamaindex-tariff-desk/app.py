"""Tariff Desk — a demo of the Nimble + LlamaIndex integration.

Ask a customs question; get an answer assembled from cited, dated facts. If the
corpus doesn't cover the lane, a Nimble Web Search Agent researches it and the
result joins the index, so the next question about it is free.

Three outcomes, and the UI always says which one you got:

    from corpus          covered and inside its TTL — free, instant
    stale -> researched  covered but past its TTL, so the guard withheld it
    not covered -> researched   new lane; the run's Document joins the corpus

The point being demonstrated: RAG fixes *private* data but not *stale* data. A
vector store built once relocates the model's staleness into your index, where
nobody notices. Here every fact is dated and the retrieval path refuses to answer
from an expired one.

    streamlit run app.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk import classify, ingest, router  # noqa: E402
from desk.freshness import assess, stale_report  # noqa: E402
from desk.models import configure_models  # noqa: E402
from desk.normalize import get_llm, normalize  # noqa: E402
from desk.research import (  # noqa: E402
    Lane, ResearchTask, TTL_DAYS, needs_research, open_jobs, read_job, use_live,
)

st.set_page_config(page_title="Tariff Desk", page_icon="🧾", layout="wide")

# Every state names the agent, because agent research is what produces every answer
# here — the only difference is whether it already happened. Framing a covered answer
# as "from corpus, nothing to run" sells the cache and buries the thing doing the work.
BADGE = {
    "corpus": ("✅", "researched by a Nimble Web Search Agent"),
    "stale": ("🕒", "research expired — a Nimble agent is re-checking"),
    "new": ("🔎", "not researched yet — a Nimble Web Search Agent is on it"),
}

FIELD_LABELS = {
    "additional_duties": "an extra duty",
    "exclusions_in_force": "an exclusion",
    "general_rate": "the base rate",
    "htsus_revision": "the schedule revision",
    "unverified": "unverified items",
    "confirmed_absent": "ruled-out items",
}


@st.cache_resource(show_spinner=False)
def _load_index():
    """Configure the models and load the index. Allowed to raise.

    Deliberately not catching here: Streamlit does not cache an exception, so a
    corrected `.env` takes effect on the next rerun. Catching inside the cached
    function stored `None` as the cached resource, which meant a reader who fixed
    their keys kept seeing the same error until they restarted the process.
    """
    configure_models()
    return ingest.load_index()


def _index():
    """The index, or None with the reason shown to the reader.

    `configure_models()` raises when a key is missing. The sidebar warns about it,
    but a warning is not control flow: without this, the first question after a bad
    `.env` is an uncaught Streamlit traceback rather than something actionable.
    Callers already handle None.
    """
    try:
        return _load_index()
    except RuntimeError as err:
        st.error(str(err), icon="🚫")
        return None


@st.cache_resource(show_spinner=False)
def _llm():
    return get_llm()


# --- formatting helpers ----------------------------------------------------


def friendly_lane(lane_key: str | None) -> str:
    """`8507.60.00|Vietnam|United States` -> `Vietnam → United States (HTS 8507.60.00)`."""
    if not lane_key:
        return "unknown route"
    parts = lane_key.split("|")
    if len(parts) == 3:
        code, origin, destination = parts
        return f"{origin} → {destination} (HTS {code})"
    if len(parts) == 2:
        code, destination = parts
        return f"base rate into {destination} (HTS {code})"
    return lane_key


def humanize_age(days: float | None) -> str:
    """'0.04d' means nothing to a reader. '1h ago' does."""
    if days is None:
        return "no date recorded"
    if days < 0.04:
        return "just now"
    if days < 1:
        return f"{max(1, int(round(days * 24)))}h ago"
    if days < 2:
        return "yesterday"
    return f"{int(round(days))}d ago"


# --- sidebar ---------------------------------------------------------------


def render_coverage(records: list[dict]) -> None:
    """Coverage grouped by product, in the shape a person reads it.

    Product name leads; the HTS code stays as supporting detail because the duty
    attaches to the code, not the product name — an answer you can't tie back to a
    code isn't checkable. An earlier version printed the raw storage key
    (`8507.60.00|China|United States [overlay] · 0.04d · high`), which is data, not
    information.
    """
    by_code: dict[str, dict] = {}
    for record in records:
        code = (record.get("lane") or {}).get("hts_code")
        if not code:
            continue
        entry = by_code.setdefault(code, {"rate": None, "overlays": [], "product": ""})
        entry["product"] = entry["product"] or (record.get("lane") or {}).get("product") or ""
        if record.get("kind") == "rate":
            entry["rate"] = record
        else:
            entry["overlays"].append(record)

    for code in sorted(by_code, key=lambda c: (by_code[c]["product"] or c).lower()):
        entry = by_code[code]
        st.caption(f"**{(entry['product'] or 'Unnamed product').capitalize()}**")

        rate = entry["rate"]
        if rate is None:
            st.caption(f"　🕒 HTS {code} · no base rate researched yet")
        else:
            verdict = assess({"kind": "rate", "researched_at": rate.get("researched_at")})
            content = ingest.parsed_content(rate) or {}
            st.caption(
                f"　{'🕒' if verdict.stale else '✅'} HTS {code} · base rate "
                f"**{content.get('general_rate') or '—'}** for any origin · "
                f"{humanize_age(verdict.age_days)}"
            )

        for overlay in sorted(entry["overlays"],
                              key=lambda r: (r.get("lane") or {}).get("origin") or ""):
            meta = ingest.node_metadata(overlay)
            verdict = assess({"kind": "overlay",
                              "researched_at": overlay.get("researched_at")})
            origin = (overlay.get("lane") or {}).get("origin") or "?"
            in_force = meta.get("duties_in_force", 0)
            gaps = len(meta.get("unverified") or [])

            if verdict.stale:
                detail = "expired — will be re-checked"
            elif in_force:
                detail = f"{in_force} extra dut{'y' if in_force == 1 else 'ies'}"
            else:
                detail = "no extra duties"
            if gaps:
                detail += f" · {gaps} unverified"

            st.caption(
                f"　{'🕒' if verdict.stale else '✅'} from **{origin}** · {detail} · "
                f"{humanize_age(verdict.age_days)}"
            )


def render_change_log() -> None:
    # Only substantive movement. Every refresh rewords the prose fields, so listing
    # those says "something changed" over and over and buries the line that matters.
    material = set(FIELD_LABELS)
    changes = [c for c in router.load_changes(limit=6) if c.get("changes")]
    st.subheader("What the corpus learned")
    st.caption(
        "Differences found the last time a fact was re-researched. Some are real "
        "changes in the world; some are simply a deeper answer than before."
    )
    if not changes:
        st.caption("No refreshes recorded yet.")
    for entry in changes:
        shown = [c for c in entry["changes"] if c.get("field") in material]
        st.caption(f"**{entry['at'][:10]}** · {friendly_lane(entry.get('lane_key'))}")
        if not shown:
            st.caption("　wording only — no duty or exclusion changed")
            continue
        for change in shown[:3]:
            label = FIELD_LABELS.get(change.get("field"),
                                     str(change.get("field", "")).replace("_", " "))
            if change["type"] == "added":
                st.caption(f"　now lists {label}: {str(change.get('after'))[:80]}")
            elif change["type"] == "removed":
                st.caption(f"　no longer lists: {str(change.get('before'))[:80]}")
            elif change["type"] == "coverage":
                st.caption(f"　{label}: {change.get('before')} → {change.get('after')}")
            else:
                st.caption(f"　{label}: {str(change.get('before'))[:40]} → "
                           f"{str(change.get('after'))[:40]}")


def sidebar() -> None:
    with st.sidebar:
        st.header("Corpus")
        records = ingest.load_records()
        cov = ingest.coverage(records)
        rows = stale_report(records)
        stale = [r for r in rows if r["stale"]]

        a, b = st.columns(2)
        a.metric("Facts", cov["records"])
        b.metric("Expired", len(stale))
        st.caption(
            f"{cov['rate_docs']} base rate(s) over {len(cov['hts_codes'])} tariff "
            f"code(s) · {cov['overlay_docs']} route(s)"
        )

        # Default is to show it: a reader must know when they are seeing replayed runs
        # rather than live research. `DESK_HIDE_DEMO_NOTICE` exists only so a recording
        # isn't dominated by a banner, and it is deliberately absent from .env.example
        # so it cannot ship switched on.
        hide_notice = os.environ.get("DESK_HIDE_DEMO_NOTICE", "").strip().lower() in {
            "1", "true", "yes"}
        if not use_live() and not hide_notice:
            st.warning("`USE_LIVE=false` — replaying cached runs. No new research.", icon="⚠️")
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("`OPENAI_API_KEY` missing — the index cannot be built.", icon="🚫")

        st.divider()
        st.subheader("Coverage")
        st.caption(
            "✅ inside its TTL · 🕒 expired, re-researched before it is used. "
            f"Base rates hold for {TTL_DAYS['rate']} days, duty overlays for "
            f"{TTL_DAYS['overlay']}."
        )
        render_coverage(records)

        jobs = [j for j in open_jobs() if j.get("status") in {"running", "timeout"}]
        if jobs:
            st.divider()
            st.subheader("Research in flight")
            for job in jobs:
                st.caption(f"⏳ {friendly_lane(job.get('lane_key'))} — {job.get('status')}")
            st.caption("Runs continue even if you close this tab.")

        st.divider()
        render_change_log()



# --- code lookup -----------------------------------------------------------
# Rough phase labels for the wait. The connector blocks for the whole run and exposes
# no progress events, so these are time-based narration, not real status — worded so
# they never claim to know more than they do.
LOOKUP_PHASES = (
    (0, "starting the research run"),
    (12, "searching the tariff schedule"),
    (40, "reading chapter documents and CBP rulings"),
    (95, "assembling candidates with citations"),
    (150, "still working — long runs happen"),
)


def _phase(elapsed: float) -> str:
    label = LOOKUP_PHASES[0][1]
    for after, text in LOOKUP_PHASES:
        if elapsed >= after:
            label = text
    return label


def _run_lookup(product: str) -> dict:
    """Look up codes, narrating the wait.

    A cached lookup returns instantly and gets no theatre. A live one takes ~2 minutes,
    which a bare spinner makes look hung — so the run goes on a thread and the status
    line ticks with elapsed seconds while it works.
    """
    hit = classify.cached(product)
    if hit and demo_replay():
        _replay_status(f"Looking up “{product}”…", hit.get("elapsed_s") or 90,
                       _phase, "Reading the official schedule and CBP's rulings.")
        return {**hit, "from_cache": True}
    if hit:
        return classify.find_candidates(product)

    from concurrent.futures import ThreadPoolExecutor

    with st.status(f"Looking up “{product}”…", expanded=True) as status:
        line = st.empty()
        st.caption(
            "Reading the official schedule and CBP's rulings. Typically 1–3 minutes."
        )
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(classify.find_candidates, product)
            while not future.done():
                elapsed = time.monotonic() - started
                line.write(f"⏳ {_phase(elapsed)} — {int(elapsed)}s elapsed")
                time.sleep(1)
            result = future.result()

        elapsed = int(time.monotonic() - started)
        if result.get("error"):
            line.write(f"❌ failed after {elapsed}s")
            status.update(label=f"Lookup failed after {elapsed}s", state="error")
        else:
            found = len(result.get("candidates") or [])
            line.write(f"✅ {found} candidate(s) in {elapsed}s")
            status.update(label=f"Found {found} candidate(s) in {elapsed}s",
                          state="complete", expanded=False)
        return result





def render_lookup() -> None:
    """Plain-language product -> candidate codes, so a reader can get started.

    An HTS subheading means nothing to most people, which makes the rest of the app
    unusable to them. This is the way in. It shows candidates with citations and never
    picks one — classification is a human decision, and a wrong code produces a
    confidently wrong duty for the wrong product.
    """
    with st.expander("🔍 Don't know the tariff code? Describe the product", expanded=False):
        st.caption(
            "A Web Search Agent reads the official schedule and CBP's rulings and comes "
            "back with candidates to choose between. About two minutes."
        )
        col_input, col_button = st.columns([4, 1])
        product = col_input.text_input(
            "Product", key="lookup_product", label_visibility="collapsed",
            placeholder="stainless steel insulated drinks bottle",
        )
        go = col_button.button("Find codes", use_container_width=True)

        if go and product:
            st.session_state["lookup_result"] = _run_lookup(product)

        result = st.session_state.get("lookup_result")
        if not result:
            return
        if result.get("error"):
            st.warning(result["error"], icon="⚠️")
            return

        candidates = result.get("candidates") or []
        source = "cached" if result.get("from_cache") else f"{result.get('elapsed_s')}s"
        usable = sum(1 for c in candidates
                     if (c.get("is_full_rate_line")
                         if c.get("is_full_rate_line") is not None
                         else sum(ch.isdigit() for ch in c.get("hts_code") or "") >= 8))
        st.caption(f"{len(candidates)} candidate(s) · {source} · {usable} usable as a "
                   "rate line · these are options to choose between, not an answer")
        if not usable:
            st.warning(
                "None of these is a full tariff line, so none can give you a duty rate. "
                "That usually means the description was too broad — say what the upper "
                "and sole are made of, or what the item actually is, and search again.",
                icon="🔢",
            )

        for idx, candidate in enumerate(candidates):
            code = candidate.get("hts_code") or "?"
            digits = sum(c.isdigit() for c in code)
            # Trust the agent's own flag when it set one, else fall back to the digit
            # count. A rate only exists on an 8- or 10-digit line, so handing a heading
            # to the question box gives the reader a code the app cannot answer.
            full_line = candidate.get("is_full_rate_line")
            if full_line is None:
                full_line = digits >= 8
            row, button = st.columns([5, 1])
            with row:
                st.markdown(f"**`{code}`** — {candidate.get('description') or ''}")
                if candidate.get("why_it_might_fit"):
                    st.caption(candidate["why_it_might_fit"])
                if not full_line:
                    need = candidate.get("narrowing_needed")
                    st.caption(
                        f"⚠️ {digits}-digit "
                        f"{'heading' if digits <= 4 else 'subheading'} — no duty rate at "
                        "this level."
                        + (f" Needed to narrow it: {need}" if need else
                           " Add material or type to your description and search again.")
                    )
                if candidate.get("citation_url"):
                    st.caption(f"[official source]({candidate['citation_url']})"
                               + (f" · confidence `{candidate['confidence']}`"
                                  if candidate.get("confidence") else ""))
            if full_line:
                button.button("Use this", key=f"use_{idx}_{code}",
                              on_click=_use_code, args=(code,),
                              use_container_width=True)
            else:
                button.caption("not a rate line")

        if result.get("what_would_settle_it"):
            st.info(f"**What still has to be decided:** {result['what_would_settle_it']}",
                    icon="🧑‍⚖️")


def _use_code(code: str) -> None:
    """Prefill the question. Runs as a callback, before the rerun, so setting the
    widget's session_state key is safe."""
    # Left deliberately open-ended for the reader to name the country. The app now
    # asks for it rather than failing, which it used to do: a question with a code
    # and no origin produced no Lane and no flag, and the button walked into it.
    st.session_state["question_box"] = (
        f"What's the duty on HTS {code} from <country>?"
    )


RESEARCH_PHASES = (
    (0, "starting the research run"),
    (15, "the agent is planning and searching"),
    (60, "reading official sources"),
    (150, "cross-checking and assembling the answer"),
    (260, "still working — a thorough run can take a while"),
)


def _research_phase(elapsed: float) -> str:
    label = RESEARCH_PHASES[0][1]
    for after, text in RESEARCH_PHASES:
        if elapsed >= after:
            label = text
    return label


def _run_research(lane: Lane, kinds: list[str], force: bool) -> bool:
    """Research missing facts, narrating the wait, then fold them into the index.

    The earlier version fired the threads and told the reader to come back later and
    run `build_index.py` by hand — true, but a poor demo of a corpus that extends
    itself. This waits with a ticking status and re-indexes on completion, so asking
    about something uncovered just works.

    Returns True if the index was updated.
    """
    threads = ResearchTask(lane=lane, kinds=list(kinds), force=force).start()
    with st.status(f"Researching {friendly_lane(lane.key)}\u2026", expanded=True) as status:
        line = st.empty()
        st.caption(
            "Each fact is a separate agent run against official sources. Runs continue "
            "server-side even if you close this tab — the ids are on disk, and "
            "`recover_runs.py` collects anything that outlives its deadline."
        )
        started = time.monotonic()
        while any(t.is_alive() for t in threads):
            elapsed = time.monotonic() - started
            states = " · ".join(
                f"{k}: {(read_job(lane, k) or {}).get('status', 'done')}" for k in kinds
            )
            line.write(f"⏳ {_research_phase(elapsed)} — {int(elapsed)}s · {states}")
            time.sleep(2)

        elapsed = int(time.monotonic() - started)
        failed = [k for k in kinds
                  if (read_job(lane, k) or {}).get("status") in
                  {"failed", "timeout", "ambiguous_create"}]
        if failed:
            details = "; ".join(
                f"{k}: {(read_job(lane, k) or {}).get('status')}" for k in failed
            )
            line.write(f"⚠️ finished in {elapsed}s with problems — {details}")
            status.update(label=f"Research incomplete after {elapsed}s", state="error")
            return False

        line.write(f"✅ researched in {elapsed}s — adding to the corpus")
        ingest.build_index(ingest.to_documents(ingest.load_records()))
        _load_index.clear()          # the cached index handle is now stale
        status.update(label=f"Researched and indexed in {elapsed}s",
                      state="complete", expanded=False)
    return True


def demo_replay() -> bool:
    """Replay cached runs through the live progress UI, for recording.

    `USE_LIVE=false` answers instantly from cached runs, which looks nothing like the
    real thing and makes a video misleading in the other direction. With this on, a
    covered question shows the same status panel and phase labels as a live run, ticking
    through the **actual elapsed time that run took**, on a faster clock — a sped-up
    recording rather than an invented one. The answers, citations and confidence shown
    are the genuine agent output.

    Off by default and absent from .env.example: it must never ship enabled.
    """
    return os.environ.get("DESK_DEMO_REPLAY", "").strip().lower() in {"1", "true", "yes"}


def demo_pause() -> float:
    """Seconds to hold the status panel before showing the result."""
    try:
        return max(0.5, float(os.environ.get("DESK_DEMO_PAUSE", "3")))
    except ValueError:
        return 3.0


def _replay_status(label: str, total_s: float, phase_fn, caption: str,
                   work=None):
    """Hold a status panel, do the remaining work inside it, then report the real time.

    No counting clock: a ticking number is hard to cut around in an edit, and the only
    figure worth showing is what the run actually took.

    `work` runs *before* the panel says completed. Writing the answer takes another
    10-15 seconds of LLM synthesis after retrieval, and declaring completion first left
    a silent gap with nothing on screen — the panel was lying about being finished.
    """
    total_s = max(1.0, float(total_s or 0))
    result = None
    with st.status(label, expanded=True) as status:
        line = st.empty()
        st.caption(caption)
        line.write(f"⏳ {phase_fn(total_s / 2)}…")
        time.sleep(demo_pause())
        if work is not None:
            line.write("⏳ writing the answer from the cited facts…")
            result = work()
        line.write(f"✅ completed in {int(total_s)}s")
        status.update(label=f"Completed in {int(total_s)}s", state="complete",
                      expanded=False)
    return result


# --- main pane -------------------------------------------------------------


def render_facts(nodes) -> None:
    """The facts behind an answer, with the agent's own trust payload shown as-is."""
    for nws in nodes:
        meta = nws.node.metadata or {}
        verdict = assess(meta)
        kind = "base rate" if meta.get("kind") == "rate" else "duty overlays"
        title = f"{'🕒' if verdict.stale else '✅'} {kind} · {verdict.describe()}"
        with st.expander(title, expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("Confidence", str(meta.get("confidence")))
            c2.metric("Primary sources", meta.get("primary_sources", 0))
            c3.metric("Unverified", len(meta.get("unverified") or []))

            if meta.get("duties_excluded"):
                st.caption(
                    f"{meta['duties_excluded']} duty(ies) filtered out — the agent "
                    "marked them not in force, or their window has closed."
                )
            # Given equal billing with the answer on purpose: a run can return `high`
            # confidence while leaving facts unverified. `confidence` grades what was
            # claimed, not what was covered.
            if meta.get("unverified"):
                st.warning("The agent could not verify:\n\n" + "\n".join(
                    f"- {u}" for u in meta["unverified"]), icon="❓")
            if meta.get("confirmed_absent"):
                st.info("Checked and confirmed NOT to apply:\n\n" + "\n".join(
                    f"- {a}" for a in meta["confirmed_absent"][:6]), icon="✔️")
            if meta.get("echoed_claims"):
                st.caption(
                    f"{meta['echoed_claims']} field(s) echo the question's own input "
                    "and are not researched facts."
                )
            urls = meta.get("source_urls") or []
            if urls:
                st.caption("Sources: " + " · ".join(
                    f"[{i + 1}]({u})" for i, u in enumerate(urls)))
            st.caption(f"run `{meta.get('run_id')}` · agent `{meta.get('agent_id')}` "
                       f"· effort `{meta.get('effort')}`")


def main() -> None:
    st.title("🧾 Tariff Desk")
    st.caption(
        "A demo of the Nimble + LlamaIndex integration: a knowledge base that "
        "researches what it doesn't know and tells you how old everything is. "
        "**Illustrative, not a compliance reference** — the figures are a snapshot of "
        "what the agents found on the dates shown, kept to demonstrate the mechanics."
    )

    sidebar()

    render_lookup()

    question = st.text_input(
        "Ask about a product and where it's coming from",
        key="question_box",
        placeholder="What's the duty on HTS 8507.60.00 from Vietnam?",
    )
    if not question:
        st.info(
            "Try: **What's the duty on HTS 8507.60.00 from China?** · "
            "**Is any exclusion in force for 7604.29.10 from Mexico?** · "
            "**What's out of date?**"
        )
        return

    parsed = normalize(question, llm=_llm())

    # Corpus questions never cost a run.
    if parsed.intent == "corpus":
        result = router.answer_corpus(question)
        st.success("answered from corpus metadata — no research run", icon="📇")
        st.markdown(result["answer"])
        return

    if parsed.needs_hts_code:
        st.warning(
            "That needs a tariff code. Duty attaches to the code rather than the "
            "product name, and classification is a human decision — so the app will "
            "not guess one.", icon="✋",
        )
        for note in parsed.notes:
            st.caption(note)
        if parsed.suggested_hts_code:
            st.caption(
                f"Possible match: `{parsed.suggested_hts_code}` "
                f"({parsed.suggestion_basis}). Confirm it, then ask again including "
                "the code."
            )
        return

    if parsed.partial_code and parsed.lane is not None:
        digits = sum(c.isdigit() for c in parsed.hts_code or "")
        kind = "heading" if digits <= 4 else "subheading"
        st.warning(
            f"`{parsed.hts_code}` is a {digits}-digit {kind}, not a full tariff line. "
            "A duty rate lives on an 8- or 10-digit statistical line, and a "
            f"{kind} covers many lines with very different rates — so there is no "
            "single rate to report for it.",
            icon="🔢",
        )
        st.caption(
            "Use the lookup above to find the full line for your product, then ask "
            "again. (Duty overlays are often described at this level, so a "
            "heading-level answer can still be partially useful — but it cannot give "
            "you a rate.)"
        )
        return

    if parsed.needs_origin or parsed.lane is None:
        st.warning(
            f"Which country is it coming from? Add it to the question — for example "
            f"“…HTS {parsed.hts_code or '8507.60.00'} from Vietnam”.", icon="🌍",
        )
        for note in parsed.notes:
            st.caption(note)
        return

    lane: Lane = parsed.lane
    index = _index()
    if index is None:
        st.error("No index yet. Run `python build_index.py --samples`.", icon="🚫")
        return

    rate_needed, rate_why = needs_research(lane, "rate")
    overlay_needed, overlay_why = needs_research(lane, "overlay")
    result = None

    if not rate_needed and not overlay_needed and demo_replay():
        records = {r.get("kind"): r for r in ingest.load_records()
                   if r.get("doc_key") in {lane.rate_key, lane.key}}
        longest = max((float(r.get("elapsed_s") or 0) for r in records.values()),
                      default=120.0)
        icon, label = BADGE["new"]
        st.info(f"{icon} {label}")
        result = _replay_status(
            f"Researching {friendly_lane(lane.key)}…", longest, _research_phase,
            "Each fact is a separate agent run against official sources.",
            work=lambda: router.answer_lane(index, lane, question, strict=True),
        )
    elif not rate_needed and not overlay_needed:
        icon, label = BADGE["corpus"]
        st.success(f"{icon} {label} — every figure below came from an agent run against "
                   "official sources, cited and dated")
    else:
        which = [k for k, needed in (("rate", rate_needed), ("overlay", overlay_needed))
                 if needed]
        stale_case = "stale" in rate_why or "stale" in overlay_why
        icon, label = BADGE["stale" if stale_case else "new"]
        if not use_live():
            st.warning(
                f"{icon} {label}, but `USE_LIVE=false` — cannot research. Answering "
                "from whatever is cached.", icon="⚠️",
            )
        else:
            st.info(f"{icon} {label} — reading official sources now "
                    f"({', '.join(which)}).")
            if _run_research(lane, which, force=stale_case):
                index = _index()

    if result is None:
        with st.spinner("Writing the answer from the cited facts…"):
            result = router.answer_lane(index, lane, question, strict=True)

    if not result["answered"]:
        if result["reason"] == "stale":
            st.warning(
                "The corpus holds this lane but every fact is past its TTL, so it was "
                "withheld rather than served as current.", icon="🕒",
            )
            render_facts(result["withheld"])
        else:
            st.info("Not in the corpus yet.", icon="🔎")
        return

    st.markdown("### Answer")
    st.markdown(result["answer"])
    if result["withheld"]:
        st.caption(f"{len(result['withheld'])} expired fact(s) were withheld from this "
                   "answer.")
    st.markdown("### The facts behind it")
    render_facts(result["nodes"])


if __name__ == "__main__":
    main()
