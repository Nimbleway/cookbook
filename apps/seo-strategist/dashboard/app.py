#!/usr/bin/env python3
"""
SEO Strategy Dashboard — read-only report viewer.
Run: streamlit run dashboard/app.py
"""

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="SEO Strategy Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@400;600;700&display=swap');

/* ── Base typography ── */
html, body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stMarkdown, .stMarkdown p, .stMarkdown li,
.stAlert, .stMetric,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    letter-spacing: -0.01em;
    line-height: 1.6;
}

/* ── Headings ── */
h1, h2, h3, h4,
[data-testid="stHeading"],
.stTitle {
    font-family: 'Sora', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
}
h1 { font-size: 2rem !important; }
h2 { font-size: 1.45rem !important; }
h3 { font-size: 1.2rem !important; }

/* ── Sidebar heading ── */
[data-testid="stSidebar"] h3 {
    font-family: 'Sora', sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* ── Metric labels & values ── */
[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    opacity: 0.65;
}
[data-testid="stMetricValue"] {
    font-family: 'Sora', sans-serif !important;
    font-weight: 700 !important;
    font-size: 2rem !important;
    letter-spacing: -0.03em !important;
}

/* ── Tabs — larger, bolder ── */
[role="tablist"] {
    gap: 2px;
    padding-bottom: 2px;
    border-bottom: 1px solid #2a2a2a;
}
[role="tab"] {
    font-family: 'Sora', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    padding: 14px 22px !important;
    border-radius: 6px 6px 0 0 !important;
    letter-spacing: -0.01em !important;
    transition: color 0.15s ease !important;
}
[role="tab"][aria-selected="true"] {
    color: #edc602 !important;
    border-bottom: 2px solid #edc602 !important;
}
[role="tab"]:hover {
    color: #edc602cc !important;
    background: #1f1f1f !important;
}

/* ── Expander headers ── */
[data-testid="stExpander"] summary {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.92rem !important;
}

/* ── Caption / small text ── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.01em !important;
    opacity: 0.55 !important;
}

/* ── Selectbox / multiselect labels ── */
[data-testid="stWidgetLabel"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    opacity: 0.65 !important;
}
</style>
""", unsafe_allow_html=True)

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config/analysis_config.json"
RUNS_ROOT   = ROOT / ".nimble/seo_runs"

STATUS_COLORS = {
    "winning":         "#22c55e",
    "visible":         "#84cc16",
    "weak":            "#f59e0b",
    "absent":          "#ef4444",
    "wrong_page":      "#f97316",
    "intent_mismatch": "#a855f7",
}
THREAT_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
PRIORITY_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
IMPACT_COLORS = {"High": "#22c55e", "Medium": "#f59e0b"}
EFFORT_COLORS = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"}


# ── data loading ─────────────────────────────────────────────────

@st.cache_data
def load_data():
    config = json.loads(CONFIG_PATH.read_text())
    domain = urlparse(config["homepage_url"]).netloc.lstrip("www.")
    runs = sorted((RUNS_ROOT / domain).glob("*"))
    if not runs:
        st.error("No completed run found. Run phases 1–8 first.")
        st.stop()
    run_dir = runs[-1]

    def _load(name):
        p = run_dir / name
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    return {
        "run_dir":   str(run_dir),
        "run_name":  run_dir.name,
        "domain":    domain,
        "cu":        _load("company_understanding.json") or {},
        "terms":     _load("search_terms.json") or [],
        "serps":     _load("serp_results.json") or [],
        "pages":     _load("pages_extracted.json") or [],
        "comp_map":  _load("competitor_map.json") or {},
        "diagnosis": _load("diagnosis.json") or {},
        "recs":      _load("recommendations.json") or {},
        "report_md": (run_dir / "report.md").read_text(encoding="utf-8")
                     if (run_dir / "report.md").exists() else None,
    }


data      = load_data()
cu        = data["cu"]
terms     = data["terms"]
serps     = data["serps"]
pages     = data["pages"]
comp_map  = data["comp_map"]
diag      = data["diagnosis"]
recs      = data["recs"]

score     = diag.get("site_seo_score", {})
diagnoses = diag.get("term_diagnoses", [])
aggregate = comp_map.get("aggregate") or []

term_by_query = {t["search_term"]: t for t in terms}


# ── helpers ───────────────────────────────────────────────────────

def strip_domain(url: str) -> str:
    return (url or "").replace(f"https://{data['domain']}", "").replace(f"https://www.{data['domain']}", "") or "/"


def color_col(color_map: dict):
    def _fn(val):
        c = color_map.get(val, "")
        return f"color: {c}; font-weight: bold" if c else ""
    return _fn


def fmt_issue(s: str) -> str:
    return s.replace("_", " ").title()


def safe_style(df: pd.DataFrame, col_map: dict):
    styler = df.style
    for col, cmap in col_map.items():
        if col in df.columns:
            try:
                styler = styler.map(color_col(cmap), subset=[col])
            except AttributeError:
                styler = styler.applymap(color_col(cmap), subset=[col])
    return styler


# ── sidebar ───────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"### {cu.get('company_name', data['domain'])}")
    st.caption(f"Run: `{data['run_name']}`")
    st.caption(f"Site: `{data['domain']}`")
    if score:
        st.divider()
        st.metric("SEO Score", f"{score.get('total', '?')}/100")

# ── tabs ──────────────────────────────────────────────────────────

TAB_LABELS = [
    "📊 Overview",
    "🔍 SERP Rankings",
    "🏁 Competitors",
    "🩺 Diagnosis",
    "📄 Pages",
    "⚡ Quick Wins",
    "🗺️ Recommendations",
    "📋 Full Report",
]
tabs = st.tabs(TAB_LABELS)


# ══════════════════════════════════════════════════════════════════
# Tab 0 — Overview
# ══════════════════════════════════════════════════════════════════
with tabs[0]:
    st.title(f"SEO Strategy — {cu.get('company_name', data['domain'])}")
    st.caption(f"Run: {data['run_name']}  ·  {len(terms)} terms  ·  {len(pages)} pages crawled")

    # ── Score row ────────────────────────────────────────────────
    st.subheader("Site SEO Score")
    col_total, col_subs = st.columns([1, 4])

    with col_total:
        total = score.get("total", 0)
        colour = "#22c55e" if total >= 70 else ("#f59e0b" if total >= 50 else "#ef4444")
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total,
            gauge={
                "axis": {"range": [0, 100]},
                "bar":  {"color": colour},
                "steps": [
                    {"range": [0, 50],  "color": "#fef2f2"},
                    {"range": [50, 70], "color": "#fefce8"},
                    {"range": [70, 100],"color": "#f0fdf4"},
                ],
            },
            number={"suffix": "/100"},
            domain={"x": [0, 1], "y": [0, 1]},
        ))
        fig_gauge.update_layout(height=200, margin=dict(t=20, b=0, l=20, r=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_subs:
        dims = [
            ("Technical SEO",   score.get("technical_seo", 0),            20),
            ("Content Depth",   score.get("content_depth", 0),            20),
            ("Intent Align",    score.get("search_intent_alignment", 0),  20),
            ("Comp Coverage",   score.get("competitive_coverage", 0),     20),
            ("Int Linking",     score.get("internal_linking", 0),         10),
            ("Conversion",      score.get("conversion_readiness", 0),     10),
        ]
        df_dims = pd.DataFrame(dims, columns=["Dimension", "Score", "Max"])
        df_dims["Pct"] = (df_dims["Score"] / df_dims["Max"] * 100).round(0)
        df_dims["Label"] = df_dims.apply(lambda r: f"{int(r.Score)}/{int(r.Max)}", axis=1)

        fig_dims = px.bar(
            df_dims, x="Dimension", y="Pct",
            text="Label", range_y=[0, 100],
            color="Pct",
            color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#22c55e"]],
        )
        fig_dims.update_coloraxes(showscale=False)
        fig_dims.update_layout(
            height=260, margin=dict(t=30, b=10, l=0, r=0),
            yaxis_title="% of max", xaxis_title="",
            xaxis={"categoryorder": "array", "categoryarray": [d[0] for d in dims]},
        )
        fig_dims.update_traces(textposition="outside", textfont_size=12)
        st.plotly_chart(fig_dims, use_container_width=True)
        st.caption("Each bar = score earned out of that dimension's maximum. Labels show points/max. Red = needs work, green = strong.")

    # ── SERP status + executive summary ──────────────────────────
    st.divider()
    col_serp, col_exec = st.columns(2)

    with col_serp:
        st.subheader("SERP Status (30 terms)")
        status_counts = Counter(s.get("status", "absent") for s in serps)
        df_status = pd.DataFrame(status_counts.items(), columns=["Status", "Count"])
        df_status = df_status.sort_values("Count", ascending=False)
        fig_status = px.bar(
            df_status, x="Status", y="Count",
            color="Status", color_discrete_map=STATUS_COLORS,
            text="Count",
        )
        fig_status.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10))
        fig_status.update_traces(textposition="outside")
        st.plotly_chart(fig_status, use_container_width=True)
        st.caption("Winning = top 3  ·  Visible = positions 4–10  ·  Weak = 11–20  ·  Absent = not in top 20  ·  Wrong Page / Intent Mismatch = ranking with the wrong URL or content.")

    with col_exec:
        st.subheader("Executive Summary")
        summary = recs.get("executive_summary") or score.get("summary", "")
        if summary:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary) if s.strip()]
            bullets = "\n".join(f"- {s if s.endswith('.') else s + '.'}" for s in sentences)
            st.markdown(bullets)

    # ── Quick win preview ─────────────────────────────────────────
    st.subheader("Top Quick Wins")
    quick_wins = recs.get("quick_wins", [])
    if quick_wins:
        df_qw = pd.DataFrame([
            {
                "#":       w.get("rank"),
                "Action":  w.get("title", ""),
                "Impact":  w.get("impact", ""),
                "Effort":  w.get("effort", ""),
                "Page":    strip_domain(w.get("url", "")),
            }
            for w in quick_wins
        ])
        st.dataframe(
            safe_style(df_qw, {"Impact": IMPACT_COLORS, "Effort": EFFORT_COLORS}),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Ranked by impact-to-effort ratio. Expand any row in the Quick Wins tab for the full brief and affected terms.")


# ══════════════════════════════════════════════════════════════════
# Tab 1 — SERP Rankings
# ══════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("SERP Rankings — All 30 Terms")

    rows = []
    for s in serps:
        t = term_by_query.get(s.get("search_term", ""), {})
        d = next((x for x in diagnoses if x.get("search_term") == s.get("search_term")), {})
        rows.append({
            "Term":           s.get("search_term", ""),
            "Stripe Page":    strip_domain(s.get("mapped_page") or ""),
            "Rank":           str(s.get("stripe_rank")) if s.get("stripe_rank") else "—",
            "Status":         s.get("status", ""),
            "Top Competitor": d.get("top_competitor_for_term", ""),
            "Priority Score": (d.get("page_priority_score") or {}).get("total", 0),
            "Type":           t.get("term_type", ""),
            "Funnel":         t.get("funnel_stage", ""),
        })
    df_serp = pd.DataFrame(rows)

    f1, f2, f3 = st.columns(3)
    sf = f1.multiselect("Status",        df_serp["Status"].unique().tolist(),  default=[])
    tf = f2.multiselect("Term type",     df_serp["Type"].unique().tolist(),    default=[])
    ff = f3.multiselect("Funnel stage",  df_serp["Funnel"].unique().tolist(),  default=[])

    df_view = df_serp.copy()
    if sf: df_view = df_view[df_view["Status"].isin(sf)]
    if tf: df_view = df_view[df_view["Type"].isin(tf)]
    if ff: df_view = df_view[df_view["Funnel"].isin(ff)]

    df_view = df_view.sort_values("Priority Score", ascending=False)

    st.dataframe(
        safe_style(df_view, {"Status": STATUS_COLORS}),
        use_container_width=True,
        height=620,
        hide_index=True,
    )
    st.caption("Stripe Page = the URL Google is currently returning for that search (blank if absent). Rank = position in Google results (1 is top). Priority Score = how much fixing this term is worth, based on business value and ranking opportunity.")

    # ── SERP detail expander ──────────────────────────────────────
    st.divider()
    st.subheader("SERP Detail — Top 5 Results per Term")
    serp_by_term = {s["search_term"]: s for s in serps}
    pick = st.selectbox("Select term", [s["search_term"] for s in serps])
    if pick:
        picked = serp_by_term.get(pick, {})
        top = picked.get("top_results", [])[:10]
        if top:
            df_top = pd.DataFrame([
                {
                    "Rank":    str(r.get("rank", "")),
                    "Domain":  r.get("domain", ""),
                    "Title":   r.get("title", ""),
                    "Snippet": (r.get("snippet") or "")[:120],
                }
                for r in top
            ])
            st.dataframe(df_top, use_container_width=True, hide_index=True)
            st.caption("Live Google results for this search term — shows which domains are winning the page and what angle their content takes.")


# ══════════════════════════════════════════════════════════════════
# Tab 2 — Competitors
# ══════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Competitor Landscape")

    if not aggregate:
        st.warning("No competitor data found.")
    else:
        c1, c2, c3 = st.columns(3)
        threat_counts = Counter(c.get("threat_level", "?") for c in aggregate)
        c1.metric("High threat",   threat_counts.get("High", 0))
        c2.metric("Medium threat", threat_counts.get("Medium", 0))
        c3.metric("Low threat",    threat_counts.get("Low", 0))

        st.divider()
        col_chart, col_detail = st.columns([2, 3])

        with col_chart:
            st.markdown("**SERP Frequency**")
            df_agg = pd.DataFrame(aggregate)
            df_chart = df_agg.sort_values("appears_in_serps", ascending=True).tail(20)
            fig_comp = px.bar(
                df_chart, x="appears_in_serps", y="competitor_domain",
                orientation="h", color="threat_level",
                color_discrete_map=THREAT_COLORS,
                text="appears_in_serps",
            )
            fig_comp.update_layout(
                height=540, margin=dict(t=10, b=10),
                xaxis_title="SERPs appeared in", yaxis_title="",
                showlegend=True, legend_title="Threat",
            )
            st.plotly_chart(fig_comp, use_container_width=True)
            st.caption("How many of the 30 tracked searches each competitor appears in. A domain in 15+ SERPs is competing across your entire keyword landscape.")

        with col_detail:
            st.markdown("**Competitor Detail**")
            df_detail = pd.DataFrame([
                {
                    "★":          "★" if c.get("is_known_competitor") else "",
                    "Domain":     c.get("competitor_domain", ""),
                    "SERPs":      c.get("appears_in_serps", 0),
                    "Best Rank":  str(c.get("best_rank", "?")),
                    "Avg Rank":   str(c.get("avg_rank", "?")),
                    "Threat":     c.get("threat_level", ""),
                    "Positioning": c.get("main_inferred_positioning", ""),
                }
                for c in sorted(aggregate, key=lambda x: ({"High": 0, "Medium": 1, "Low": 2}.get(x.get("threat_level", "Low"), 3), -x.get("appears_in_serps", 0)))
            ])
            st.dataframe(
                safe_style(df_detail, {"Threat": THREAT_COLORS}),
                use_container_width=True,
                height=540,
                hide_index=True,
            )
            st.caption("★ = known competitor from your config. SERPs = searches they appear in. Best/Avg Rank = their typical Google position. Threat = how directly they compete with your core pages. Positioning = the angle they use to outrank you.")


# ══════════════════════════════════════════════════════════════════
# Tab 3 — Diagnosis
# ══════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("SEO Diagnosis")

    if not diagnoses:
        st.warning("No diagnosis data found.")
    else:
        all_page_issues     = Counter()
        all_strategy_issues = Counter()
        all_serp_issues     = Counter()
        for d in diagnoses:
            for i in d.get("page_issues", []):      all_page_issues[i] += 1
            for i in d.get("strategy_issues", []):  all_strategy_issues[i] += 1
            for i in d.get("serp_issues", []):       all_serp_issues[i] += 1

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Most Common Page Issues**")
            df_pi = pd.DataFrame(
                [(fmt_issue(i), c) for i, c in all_page_issues.most_common(10)],
                columns=["Issue", "Count"],
            )
            fig_pi = px.bar(
                df_pi, x="Count", y="Issue", orientation="h", text="Count",
                color_discrete_sequence=["#f59e0b"],
            )
            fig_pi.update_layout(
                height=380, margin=dict(t=10),
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig_pi, use_container_width=True)
            st.caption("Technical and on-page problems found on Stripe's own pages. Count = how many tracked terms are affected by that issue.")

        with c2:
            st.markdown("**Most Common Strategy Issues**")
            df_si = pd.DataFrame(
                [(fmt_issue(i), c) for i, c in all_strategy_issues.most_common(10)],
                columns=["Issue", "Count"],
            )
            fig_si = px.bar(
                df_si, x="Count", y="Issue", orientation="h", text="Count",
                color_discrete_sequence=["#ef4444"],
            )
            fig_si.update_layout(
                height=380, margin=dict(t=10),
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig_si, use_container_width=True)
            st.caption("Structural SEO gaps — e.g. missing comparison pages, content cannibalization. Count = how many tracked terms are impacted.")

        st.divider()
        st.subheader("Per-Term Diagnoses")

        df_diag = pd.DataFrame([
            {
                "Term":           d.get("search_term", ""),
                "Status":         d.get("status", ""),
                "Priority":       (d.get("page_priority_score") or {}).get("total", 0),
                "Mapped Page":    strip_domain(d.get("mapped_page") or ""),
                "Top Competitor": d.get("top_competitor_for_term", ""),
                "Summary":        d.get("diagnosis_summary", ""),
            }
            for d in sorted(
                diagnoses,
                key=lambda x: (x.get("page_priority_score") or {}).get("total", 0),
                reverse=True,
            )
        ])

        st.dataframe(
            safe_style(df_diag, {"Status": STATUS_COLORS}),
            use_container_width=True,
            height=600,
            hide_index=True,
        )
        st.caption("One row per tracked term, sorted by Priority (how much SEO value fixing it would unlock). Mapped Page = Stripe URL currently ranking for it. Select a term below for the full issue breakdown.")

        # ── Per-term expandable detail ────────────────────────────
        st.divider()
        st.subheader("Term Detail")
        pick_term = st.selectbox("Select term", [d.get("search_term") for d in diagnoses], key="diag_pick")
        if pick_term:
            d = next((x for x in diagnoses if x.get("search_term") == pick_term), {})
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Status:** `{d.get('status', '')}`")
            c2.markdown(f"**Priority Score:** `{(d.get('page_priority_score') or {}).get('total', 0)}/100`")
            c3.markdown(f"**Top Competitor:** `{d.get('top_competitor_for_term', '—')}`")

            st.markdown(f"**Diagnosis:** {d.get('diagnosis_summary', '')}")
            st.markdown(f"**Competitor winning angle:** {d.get('competitor_winning_angle', '—')}")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("**Page Issues**")
                for i in d.get("page_issues", []):
                    st.markdown(f"- {fmt_issue(i)}")
            with col_b:
                st.markdown("**Strategy Issues**")
                for i in d.get("strategy_issues", []):
                    st.markdown(f"- {fmt_issue(i)}")
            with col_c:
                st.markdown("**SERP Issues**")
                for i in d.get("serp_issues", []):
                    st.markdown(f"- {fmt_issue(i)}")

            ps = d.get("page_priority_score") or {}
            if ps:
                st.markdown("**Priority Score Breakdown**")
                ps_dims = [
                    ("Business Value",       ps.get("business_value", 0),       30),
                    ("Ranking Opportunity",  ps.get("ranking_opportunity", 0),  25),
                    ("Fixability",           ps.get("fixability", 0),           20),
                    ("Competitor Gap",       ps.get("competitor_gap", 0),       15),
                    ("Internal Link Lever.", ps.get("internal_link_leverage", 0), 10),
                ]
                df_ps = pd.DataFrame(ps_dims, columns=["Dimension", "Score", "Max"])
                df_ps["Pct"] = (df_ps["Score"] / df_ps["Max"] * 100).round(0)
                df_ps["Label"] = df_ps.apply(lambda r: f"{int(r.Score)}/{int(r.Max)}", axis=1)
                fig_ps = px.bar(df_ps, x="Pct", y="Dimension", orientation="h",
                                text="Label", range_x=[0, 100],
                                color_discrete_sequence=["#3b82f6"])
                fig_ps.update_layout(height=220, margin=dict(t=5, b=5),
                                     xaxis_title="% of max", yaxis_title="",
                                     yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_ps, use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# Tab 4 — Pages
# ══════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader(f"Page Inventory — {len(pages)} pages")

    page_type_counts = Counter(p.get("page_type", "unknown") for p in pages)
    cols = st.columns(min(len(page_type_counts), 5))
    for i, (pt, n) in enumerate(sorted(page_type_counts.items(), key=lambda x: -x[1])):
        cols[i % len(cols)].metric(pt, n)

    st.divider()

    df_pages = pd.DataFrame([
        {
            "URL":         strip_domain(p.get("url", "")),
            "Type":        p.get("page_type", ""),
            "SEO Value":   p.get("seo_value", ""),
            "Title":       p.get("title", ""),
            "H1":          p.get("h1", ""),
            "Topic":       p.get("primary_topic", ""),
            "Audience":    p.get("target_audience", ""),
        }
        for p in sorted(pages, key=lambda p: (p.get("page_type", ""), p.get("url", "")))
    ])

    type_filter = st.multiselect(
        "Filter by page type",
        options=sorted(df_pages["Type"].unique().tolist()),
        default=[],
    )
    if type_filter:
        df_pages = df_pages[df_pages["Type"].isin(type_filter)]

    st.dataframe(df_pages, use_container_width=True, height=600, hide_index=True)
    st.caption("All pages extracted from the site map. SEO Value = qualitative assessment of each page's organic traffic importance. H1 = the main heading Google uses as a relevance signal.")


# ══════════════════════════════════════════════════════════════════
# Tab 5 — Quick Wins
# ══════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("Quick Wins")
    quick_wins = recs.get("quick_wins", [])

    if not quick_wins:
        st.info("No quick wins data. Run phase8_recommendations.py first.")
    else:
        st.caption("Actions ranked by impact-to-effort ratio. High impact + Low effort = do first. Expand each for the specific page, affected search terms, and what to change.")
        for w in quick_wins:
            label = (
                f"#{w.get('rank')}  {w.get('title', '')}  —  "
                f"Impact: {w.get('impact')}  ·  Effort: {w.get('effort')}"
            )
            with st.expander(label):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Type:** `{w.get('type', '')}`")
                c2.markdown(f"**Impact:** `{w.get('impact', '')}`")
                c3.markdown(f"**Effort:** `{w.get('effort', '')}`")
                st.markdown(f"**Page:** `{strip_domain(w.get('url', ''))}`")
                st.markdown(w.get("description", ""))
                if w.get("terms_addressed"):
                    st.markdown(
                        "**Terms:** " + "  ·  ".join(f"`{t}`" for t in w["terms_addressed"])
                    )


# ══════════════════════════════════════════════════════════════════
# Tab 6 — Recommendations
# ══════════════════════════════════════════════════════════════════
with tabs[6]:
    rec_subtabs = st.tabs(["Page Optimisations", "New Pages", "Strategic Themes"])

    # ── Page optimisations ────────────────────────────────────────
    with rec_subtabs[0]:
        st.subheader("Page Optimisation Recommendations")
        page_recs = sorted(
            recs.get("page_recommendations", []),
            key=lambda x: -x.get("priority_score", 0),
        )

        st.caption("Each card is a Stripe page that needs work. Expand to see the suggested title, H1, H2s, keywords, and content additions. Sorted by priority score.")
        for pr in page_recs:
            url_short = strip_domain(pr.get("url", ""))
            with st.expander(f"{url_short}  —  Priority: {pr.get('priority_score', 0)}"):
                if pr.get("terms_addressed"):
                    st.caption("Terms: " + "  ·  ".join(pr["terms_addressed"]))

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Title**")
                    cur_t = pr.get("current_title") or "—"
                    sug_t = pr.get("suggested_title") or "—"
                    st.markdown(f"<span style='color:#9ca3af;text-decoration:line-through'>{cur_t}</span>", unsafe_allow_html=True)
                    st.markdown(f"**→ {sug_t}**")

                    st.markdown("**H1**")
                    cur_h = pr.get("current_h1") or "—"
                    sug_h = pr.get("suggested_h1") or "—"
                    st.markdown(f"<span style='color:#9ca3af;text-decoration:line-through'>{cur_h}</span>", unsafe_allow_html=True)
                    st.markdown(f"**→ {sug_h}**")

                with c2:
                    if pr.get("suggested_h2s"):
                        st.markdown("**H2s to add**")
                        for h in pr["suggested_h2s"]:
                            st.markdown(f"- {h}")
                    if pr.get("keywords_to_add"):
                        st.markdown("**Keywords to weave in**")
                        st.markdown("  ".join(f"`{k}`" for k in pr["keywords_to_add"]))

                if pr.get("content_additions"):
                    st.markdown("**Content additions**")
                    for item in pr["content_additions"]:
                        st.markdown(f"- {item}")

                if pr.get("faq_questions"):
                    st.markdown("**FAQ questions**")
                    for q in pr["faq_questions"]:
                        st.markdown(f"- {q}")

                if pr.get("internal_links_to_add"):
                    st.markdown("**Internal links to add**")
                    for lnk in pr["internal_links_to_add"]:
                        st.markdown(f"- `{strip_domain(lnk)}`")

                if pr.get("estimated_impact"):
                    st.success(pr["estimated_impact"])

    # ── New pages ─────────────────────────────────────────────────
    with rec_subtabs[1]:
        st.subheader("New Pages to Create")
        new_pages = recs.get("new_pages_needed", [])

        if not new_pages:
            st.info("No new page recommendations.")
        else:
            df_new = pd.DataFrame([
                {
                    "URL":        p.get("suggested_url", ""),
                    "Type":       p.get("page_type", ""),
                    "Priority":   p.get("priority", ""),
                    "Beat":       p.get("competitor_to_outrank", ""),
                    "Terms":      ", ".join((p.get("target_terms") or [])[:3]),
                }
                for p in new_pages
            ])
            st.dataframe(
                safe_style(df_new, {"Priority": PRIORITY_COLORS}),
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Pages that don't exist yet but should. Beat = the competitor currently winning that traffic. Terms = the search queries this page would capture.")

            st.divider()
            st.subheader("High-Priority Briefs")
            for p in [x for x in new_pages if x.get("priority") == "High"]:
                with st.expander(f"{p.get('suggested_url', '')} — {p.get('page_title', '')}"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Type:** `{p.get('page_type', '')}`")
                    c2.markdown(f"**Competitor to outrank:** `{p.get('competitor_to_outrank', '')}`")

                    st.markdown(f"**Brief:** {p.get('content_brief', '')}")
                    st.markdown(f"**Format rationale:** {p.get('format_rationale', '')}")

                    if p.get("target_terms"):
                        st.markdown(
                            "**Target terms:** " + "  ·  ".join(f"`{t}`" for t in p["target_terms"])
                        )

    # ── Strategic themes ──────────────────────────────────────────
    with rec_subtabs[2]:
        st.subheader("Strategic Themes")
        themes = recs.get("strategic_themes", [])

        if not themes:
            st.info("No strategic themes data.")
        else:
            st.caption("Broader patterns behind the term-level issues. Each theme groups several related problems and recommends a coordinated response.")
            for theme in themes:
                priority = theme.get("priority", "")
                p_color = PRIORITY_COLORS.get(priority, "#6b7280")
                with st.expander(
                    f"{theme.get('theme', '')}  —  "
                    f"{priority} priority  ·  {theme.get('terms_impacted', 0)} terms impacted"
                ):
                    st.markdown(theme.get("description", ""))
                    if theme.get("recommended_actions"):
                        st.markdown("**Recommended actions:**")
                        for action in theme["recommended_actions"]:
                            st.markdown(f"- {action}")


# ══════════════════════════════════════════════════════════════════
# Tab 7 — Full Report
# ══════════════════════════════════════════════════════════════════
with tabs[7]:
    report_md = data.get("report_md")
    if report_md:
        st.markdown(report_md)
    else:
        st.warning("report.md not found. Run phase8_recommendations.py first.")
