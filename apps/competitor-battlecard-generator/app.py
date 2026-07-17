"""
app.py - Competitor Battlecard Generator Streamlit dashboard.

Launch:
    streamlit run app.py

Defaults to the bundled sample_run when no run directory is selected.
Supports dry-run generation from the UI without any API key.
Live generation requires NIMBLE_API_KEY in .env or environment.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
SAMPLE_RUN = APP_DIR / "data" / "sample_run"

sys.path.insert(0, str(APP_DIR))
from collect import (
    build_query_plan,
    domain_from_url,
    load_json,
    make_report,
    normalize_results,
    run_collection,
    write_json,
    DEFAULT_CONFIG,
)

# ---- page setup --------------------------------------------------------------

st.set_page_config(
    page_title="Competitor Battlecard Generator",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .main { background-color: #0e1117; }
  .stMetric label { font-size: 0.85rem; color: #9ea3b0; }
  .evidence-card {
    background: #1a1d27;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 12px;
  }
  .evidence-card a { color: #7c9eff; text-decoration: none; }
  .confidence-high { color: #4caf50; font-weight: 600; }
  .confidence-medium { color: #ff9800; font-weight: 600; }
  .confidence-low { color: #9ea3b0; font-weight: 600; }
  .tag {
    display: inline-block;
    background: #2d3148;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
    margin-right: 6px;
    color: #9ea3b0;
  }
  [data-testid="stAppDeployButton"] { display: none !important; }
  [data-testid="stToolbar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ---- helpers -----------------------------------------------------------------


def available_runs() -> list[Path]:
    candidates = []
    runs_dir = DATA_DIR / "runs"
    if runs_dir.exists():
        for d in runs_dir.iterdir():
            if d.is_dir() and (d / "report.json").exists():
                candidates.append(d)
    dry = DATA_DIR / "dry_run"
    if dry.exists() and (dry / "report.json").exists():
        candidates.append(dry)
    # Sort all real runs newest-first by report.json mtime; sample_run always last
    candidates.sort(key=lambda p: (p / "report.json").stat().st_mtime, reverse=True)
    if SAMPLE_RUN.exists() and (SAMPLE_RUN / "report.json").exists():
        candidates.append(SAMPLE_RUN)
    return candidates


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    report = load_json(run_dir / "report.json")
    evidence_path = run_dir / "normalized_evidence.json"
    evidence = load_json(evidence_path) if evidence_path.exists() else report.get("evidence", [])
    return report, evidence


def badge(text: str, cls: str = "") -> str:
    return f'<span class="tag {cls}">{text}</span>'


def confidence_badge(c: str) -> str:
    return f'<span class="confidence-{c}">{c}</span>'


def render_evidence_popover(eids: list, ev_map: dict, label: str = "Evidence") -> None:
    """Render each evidence ID as a small popover button showing the evidence card."""
    if not eids:
        return
    cols = st.columns(len(eids), gap="small")
    for col, eid in zip(cols, eids):
        e = ev_map.get(eid, {})
        if not e:
            col.caption(eid)
            continue
        with col.popover(eid, use_container_width=False):
            url = e.get("url", "")
            title = e.get("title") or url or "(no title)"
            snippet = e.get("snippet") or ""
            answer = e.get("answer") or ""
            conf = e.get("confidence", "low")
            sig = e.get("signal_type", "")
            dry = e.get("dry_run", False)
            st.caption(f"{sig} | {conf} confidence")
            if url and not dry:
                st.markdown(f"**[{title}]({url})**")
            else:
                st.markdown(f"**{title}**")
            if answer:
                st.info(answer[:300])
            elif snippet:
                st.markdown(snippet[:300])


def render_evidence_card(e: dict) -> None:
    url = e.get("url", "")
    title = e.get("title") or url or "(no title)"
    snippet = e.get("snippet") or e.get("content") or ""
    answer = e.get("answer") or ""
    conf = e.get("confidence", "low")
    sig = e.get("signal_type", "")
    side = e.get("company_side", "")
    eid = e.get("evidence_id", "")

    st.markdown(f"""
<div class="evidence-card">
  <div style="margin-bottom:6px">
    {badge(eid)} {badge(sig)} {badge(side)} {confidence_badge(conf)}
  </div>
  <strong><a href="{url}" target="_blank">{title}</a></strong>
  <p style="color:#c5c8d8; font-size:0.9rem; margin:6px 0 0 0">{snippet[:300] if snippet else ''}</p>
  {f'<p style="color:#7c9eff; font-size:0.85rem; margin:6px 0 0 0"><em>Nimble answer: {answer[:200]}</em></p>' if answer else ''}
</div>
""", unsafe_allow_html=True)


# ---- sidebar -----------------------------------------------------------------


with st.sidebar:
    st.title("Competitor Battlecard")
    st.caption("Powered by Nimble Search API")
    st.divider()

    runs = available_runs()
    def _run_label(r: Path) -> str:
        if r == SAMPLE_RUN:
            return "Sample run (bundled)"
        if r.name == "dry_run":
            meta = load_json(r / "report.json").get("metadata", {})
            co = meta.get("company_name", "")
            cx = meta.get("competitor_name", "")
            suffix = f" ({co} vs {cx})" if co and cx else ""
            return f"Dry run{suffix}"
        # Timestamped dirs: "20260625T145200-nimble-vs-tavily" -> "Nimble vs Tavily  25 Jun 14:52"
        name = r.name
        ts_part = name[:13] if len(name) >= 13 else name
        slug_part = name[14:].replace("-vs-", " vs ").replace("-", " ").title().replace(" Vs ", " vs ") if len(name) > 14 else ""
        try:
            dt = datetime.strptime(ts_part, "%Y%m%dT%H%M")
            date_str = dt.strftime("%d %b %H:%M")
        except ValueError:
            date_str = ts_part
        return f"{slug_part}  {date_str}" if slug_part else date_str

    run_labels = [_run_label(r) for r in runs]

    if not runs:
        run_labels = ["Sample run (bundled)"]
        selected_run_dir = SAMPLE_RUN
    else:
        selected_label = st.selectbox("Run", run_labels, index=0)
        selected_run_dir = runs[run_labels.index(selected_label)]

    st.divider()
    st.subheader("Generate new battlecard")

    api_key = os.getenv("NIMBLE_API_KEY", "")

    with st.form("generate_form"):
        company_name = st.text_input("Your company name", value="Nimble")
        company_url = st.text_input("Your company URL", value="https://nimbleway.com")
        competitor_name = st.text_input("Competitor name", value="Tavily")
        competitor_url = st.text_input("Competitor URL", value="https://tavily.com")

        if api_key:
            generate_btn = st.form_submit_button("Generate Battlecard", use_container_width=True, type="primary")
        else:
            generate_btn = st.form_submit_button("Generate Battlecard", use_container_width=True, disabled=True)

    if not api_key:
        st.warning("Set NIMBLE_API_KEY to generate a live battlecard.")

    if generate_btn and api_key:
        cfg = {
            "company_name": company_name,
            "company_url": company_url,
            "competitor_name": competitor_name,
            "competitor_url": competitor_url,
            "country": "US",
            "locale": "en-US",
            "search_depth": "lite",
            "include_answer": True,
            "max_results": 8,
        }
        from collect import slugify as _slugify
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
        slug = f"{_slugify(company_name)}-vs-{_slugify(competitor_name)}"
        out_dir = DATA_DIR / "runs" / f"{ts}-{slug}"

        with st.spinner(f"Researching {company_name} vs {competitor_name}..."):
            try:
                raw_responses = run_collection(cfg, out_dir, dry_run=False, api_key=api_key)
                now = datetime.now(timezone.utc).isoformat()
                all_evidence = []
                id_offset = 0
                for query, raw in raw_responses:
                    items = normalize_results(raw, query, now, id_offset)
                    all_evidence.extend(items)
                    id_offset += len(items)
                make_report(cfg, all_evidence, out_dir)
                st.success(f"Done. {len(all_evidence)} evidence records.")
                st.rerun()
            except Exception as exc:
                st.error(f"Collection failed: {exc}")


# ---- load selected run -------------------------------------------------------

if not (selected_run_dir / "report.json").exists():
    st.warning("No report found. Generate a battlecard from the sidebar.")
    st.stop()

report, evidence = load_run(selected_run_dir)
meta = report.get("metadata", {})
ev_map = {e["evidence_id"]: e for e in evidence}
company = meta.get("company_name", "Company")
competitor = meta.get("competitor_name", "Competitor")
ev_count = meta.get("evidence_count", len(evidence))
generated_at = meta.get("generated_at", "")

# Compute strength_scores from evidence if missing from report (handles old runs and stale module cache)
if not report.get("strength_scores") and evidence:
    def _ev(sig_types, sides=None):
        return [e for e in evidence
                if e.get("signal_type") in sig_types
                and (sides is None or e.get("company_side") in sides)]
    def _score(items, cap=5):
        pts = sum(2 if e.get("confidence") == "high" else 1 for e in items[:cap])
        return round(min(pts / (cap * 2) * 10, 10), 1)
    co_sides = ["company", "both"]
    cx_sides = ["competitor", "both"]
    mkt_sides = ["company", "both", "market"]
    cx_mkt = ["competitor", "both", "market"]
    ss = {
        "dimensions": ["Positioning", "Pricing clarity", "Reviews", "Recent launches", "Funding momentum", "Market presence"],
        "company": [
            _score(_ev(["positioning"], co_sides)),
            _score(_ev(["pricing"], co_sides)),
            _score(_ev(["review"], co_sides)),
            _score(_ev(["launch"], co_sides)),
            _score(_ev(["funding"], co_sides)),
            _score(_ev(["market"], mkt_sides)),
        ],
        "competitor": [
            _score(_ev(["positioning"], cx_sides)),
            _score(_ev(["pricing"], cx_sides)),
            _score(_ev(["review"], cx_sides)),
            _score(_ev(["launch"], cx_sides)),
            _score(_ev(["funding"], cx_sides)),
            _score(_ev(["market"], cx_mkt)),
        ],
    }
    ss["company_total"] = round(sum(ss["company"]) / len(ss["dimensions"]), 1)
    ss["competitor_total"] = round(sum(ss["competitor"]) / len(ss["dimensions"]), 1)
    ss["verdict"] = (company if ss["company_total"] > ss["competitor_total"]
                     else competitor if ss["competitor_total"] > ss["company_total"] else "Tied")
    report["strength_scores"] = ss


# ---- header ------------------------------------------------------------------

st.title(f"{company} vs {competitor}")
st.caption(f"Generated: {generated_at[:19].replace('T', ' ')} UTC | {ev_count} evidence records")

c1, c2, c3 = st.columns(3)
c1.metric("Evidence records", ev_count)
c2.metric("High confidence", sum(1 for e in evidence if e.get("confidence") == "high"))
c3.metric("Medium confidence", sum(1 for e in evidence if e.get("confidence") == "medium"))

st.divider()


# ---- tabs --------------------------------------------------------------------

tab_overview, tab_pos_price, tab_moves, tab_reviews, tab_swot, tab_evidence = st.tabs([
    "Overview",
    "Positioning & Pricing",
    "Recent Moves",
    "Review Themes",
    "SWOT",
    "Evidence",
])


with tab_overview:
    scores = report.get("strength_scores", {})
    if scores:
        dims = scores.get("dimensions", [])
        co_scores = scores.get("company", [])
        cx_scores = scores.get("competitor", [])
        co_total = scores.get("company_total", 0)
        cx_total = scores.get("competitor_total", 0)
        verdict = scores.get("verdict", "")

        st.subheader("Competitive Strength")
        vcol1, vcol2, vcol3 = st.columns([1, 1, 1])
        vcol1.metric(company, f"{co_total}/10")
        vcol2.metric(competitor, f"{cx_total}/10")
        delta = round(co_total - cx_total, 1)
        delta_label = f"{company} +{delta}" if delta > 0 else (f"{competitor} +{abs(delta)}" if delta < 0 else "Tied")
        vcol3.metric("Edge", delta_label)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=company,
            x=dims,
            y=co_scores,
            marker_color="#4c8df5",
        ))
        fig.add_trace(go.Bar(
            name=competitor,
            x=dims,
            y=cx_scores,
            marker_color="#f5724c",
        ))
        fig.update_layout(
            barmode="group",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#c5c8d8",
            yaxis=dict(range=[0, 10], gridcolor="#2d3148"),
            xaxis=dict(gridcolor="#2d3148"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=30, b=10, l=0, r=0),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.divider()

    st.subheader("Executive Summary")
    for bullet in report.get("executive_summary", []):
        st.markdown(f"- {bullet}")

    st.divider()
    st.subheader("Battlecard Quick View")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        st.markdown("**Lead with**")
        for item in report.get("battlecard", {}).get("lead_with", []):
            point = item.get("point") if isinstance(item, dict) else item
            eids = item.get("evidence_ids", []) if isinstance(item, dict) else []
            st.markdown(f"- {point}")
            render_evidence_popover(eids, ev_map)

        st.markdown("**Discovery questions**")
        for q in report.get("battlecard", {}).get("discovery_questions", []):
            st.markdown(f"- {q}")

    with bcol2:
        st.markdown("**Watch out for**")
        for item in report.get("battlecard", {}).get("watch_out_for", []):
            point = item.get("point") if isinstance(item, dict) else item
            st.markdown(f"- {point}")

        st.markdown("**Do not claim**")
        for item in report.get("battlecard", {}).get("do_not_claim", []):
            st.markdown(f"- {item}")

    st.divider()
    st.subheader("Objection Responses")
    for obj in report.get("battlecard", {}).get("objection_responses", []):
        with st.expander(f"Objection: {obj.get('objection', '')}"):
            st.markdown(f"**Response:** {obj.get('response', '')}")
            eids = obj.get("evidence_ids", [])
            render_evidence_popover(eids, ev_map)


def _answer_for_eids(eids: list, evidence: list) -> tuple[str, list]:
    """Return (answer_text, citation_urls) for the first evidence ID that has an answer."""
    ev_map = {e["evidence_id"]: e for e in evidence}
    for eid in eids:
        e = ev_map.get(eid, {})
        if e.get("answer"):
            return e["answer"], e.get("answer_citation_urls", [])
    return "", []


with tab_pos_price:
    pos = report.get("positioning", {})
    st.subheader("Positioning")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown(f"**{company}**")
        co_eids = pos.get("company", {}).get("evidence_ids", [])
        answer, cite_urls = _answer_for_eids(co_eids, evidence)
        display = answer or pos.get("company", {}).get("summary", "No signal found.")
        st.info(display)
        if cite_urls:
            st.caption("Sources: " + " | ".join(f"[{i+1}]({u})" for i, u in enumerate(cite_urls)))
        elif co_eids:
            render_evidence_popover(co_eids, ev_map)
    with pcol2:
        st.markdown(f"**{competitor}**")
        cx_eids = pos.get("competitor", {}).get("evidence_ids", [])
        answer, cite_urls = _answer_for_eids(cx_eids, evidence)
        display = answer or pos.get("competitor", {}).get("summary", "No signal found.")
        st.info(display)
        if cite_urls:
            st.caption("Sources: " + " | ".join(f"[{i+1}]({u})" for i, u in enumerate(cite_urls)))
        elif cx_eids:
            render_evidence_popover(cx_eids, ev_map)

    diff = pos.get("difference", "")
    if diff:
        st.markdown(f"**Key difference:** {diff}")

    st.divider()

    pricing = report.get("pricing", {})
    st.subheader("Pricing")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown(f"**{company} pricing signals**")
        co_p_eids = pricing.get("company", {}).get("evidence_ids", [])
        p_answer, p_cites = _answer_for_eids(co_p_eids, evidence)
        if p_answer:
            st.info(p_answer)
            if p_cites:
                st.caption("Sources: " + " | ".join(f"[{i+1}]({u})" for i, u in enumerate(p_cites)))
        else:
            for s in pricing.get("company", {}).get("signals", ["No signal found."]):
                st.markdown(f"- {s}")
        if co_p_eids and not p_answer:
            render_evidence_popover(co_p_eids, ev_map)
    with pcol2:
        st.markdown(f"**{competitor} pricing signals**")
        cx_p_eids = pricing.get("competitor", {}).get("evidence_ids", [])
        p_answer, p_cites = _answer_for_eids(cx_p_eids, evidence)
        if p_answer:
            st.info(p_answer)
            if p_cites:
                st.caption("Sources: " + " | ".join(f"[{i+1}]({u})" for i, u in enumerate(p_cites)))
        else:
            for s in pricing.get("competitor", {}).get("signals", ["No signal found."]):
                st.markdown(f"- {s}")
        if cx_p_eids and not p_answer:
            render_evidence_popover(cx_p_eids, ev_map)

    angle = pricing.get("sales_angle", "")
    if angle:
        st.success(f"Sales angle: {angle}")


def _move_link(src: str | None, is_dry: bool) -> str:
    if not src or is_dry:
        return ""
    return f" [(source)]({src})"


with tab_moves:
    moves = report.get("recent_moves", {})
    is_dry = meta.get("dry_run", False)

    st.subheader("Recent Launches")
    for item in moves.get("launches", []):
        sig = item.get("signal", "")
        eid = item.get("evidence_id")
        link = _move_link(item.get("source"), is_dry)
        st.markdown(f"- {sig}{link}")
        if eid:
            render_evidence_popover([eid], ev_map)

    st.subheader("Funding Signals")
    for item in moves.get("funding", []):
        sig = item.get("signal", "")
        eid = item.get("evidence_id")
        link = _move_link(item.get("source"), is_dry)
        st.markdown(f"- {sig}{link}")
        if eid:
            render_evidence_popover([eid], ev_map)

    st.subheader("Leadership Moves")
    for item in moves.get("leadership", []):
        sig = item.get("signal", "")
        eid = item.get("evidence_id")
        link = _move_link(item.get("source"), is_dry)
        st.markdown(f"- {sig}{link}")
        if eid:
            render_evidence_popover([eid], ev_map)


with tab_reviews:
    reviews = report.get("review_themes", {})

    rcol1, rcol2 = st.columns(2)
    with rcol1:
        st.subheader("Praise signals")
        for p in reviews.get("praise", ["No signal found."]):
            st.markdown(f"- {p}")
    with rcol2:
        st.subheader("Complaint signals")
        for c in reviews.get("complaints", ["No signal found."]):
            st.markdown(f"- {c}")

    st.subheader("Switching triggers")
    for t in reviews.get("switching_triggers", ["No signal found."]):
        st.markdown(f"- {t}")


with tab_swot:
    swot = report.get("swot", {})

    scol1, scol2 = st.columns(2)
    with scol1:
        st.markdown("**Strengths**")
        for item in swot.get("strengths", []):
            point = item.get("point") if isinstance(item, dict) else item
            eids = item.get("evidence_ids", []) if isinstance(item, dict) else []
            st.markdown(f"- {point}")
            render_evidence_popover(eids, ev_map)

        st.markdown("**Opportunities**")
        for item in swot.get("opportunities", []):
            point = item.get("point") if isinstance(item, dict) else item
            eids = item.get("evidence_ids", []) if isinstance(item, dict) else []
            st.markdown(f"- {point}")
            render_evidence_popover(eids, ev_map)

    with scol2:
        st.markdown("**Weaknesses**")
        for item in swot.get("weaknesses", []):
            point = item.get("point") if isinstance(item, dict) else item
            eids = item.get("evidence_ids", []) if isinstance(item, dict) else []
            st.markdown(f"- {point}")
            render_evidence_popover(eids, ev_map)

        st.markdown("**Threats**")
        for item in swot.get("threats", []):
            point = item.get("point") if isinstance(item, dict) else item
            eids = item.get("evidence_ids", []) if isinstance(item, dict) else []
            st.markdown(f"- {point}")
            render_evidence_popover(eids, ev_map)


with tab_evidence:
    st.subheader(f"Evidence ({len(evidence)} records)")

    if evidence:
        df = pd.DataFrame(evidence)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download evidence CSV",
            data=csv,
            file_name=f"battlecard_evidence_{company.lower()}_{competitor.lower()}.csv",
            mime="text/csv",
        )

    filter_signal = st.selectbox(
        "Filter by signal type",
        ["all"] + sorted({e.get("signal_type", "") for e in evidence}),
    )
    filter_conf = st.selectbox("Filter by confidence", ["all", "high", "medium", "low"])

    filtered = evidence
    if filter_signal != "all":
        filtered = [e for e in filtered if e.get("signal_type") == filter_signal]
    if filter_conf != "all":
        filtered = [e for e in filtered if e.get("confidence") == filter_conf]

    st.caption(f"Showing {len(filtered)} of {len(evidence)} records")
    for e in filtered:
        render_evidence_card(e)
