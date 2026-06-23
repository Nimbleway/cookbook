"""Streamlit dashboard for Consumer Sentiment Monitor runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
SAMPLE_RUN = DATA_DIR / "sample_run"

SENTIMENT_COLORS = {
    "positive": "#22c55e",
    "negative": "#ef4444",
    "neutral": "#94a3b8",
    "mixed": "#f59e0b",
}

SENTIMENT_BG = {
    "positive": "#052e16",
    "negative": "#2d0a0a",
    "neutral": "#1e293b",
    "mixed": "#1c1207",
}


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def find_runs() -> List[Path]:
    runs = []
    for base in (DATA_DIR / "runs", DATA_DIR):
        if not base.exists():
            continue
        for report in base.glob("*/report.json"):
            runs.append(report.parent)
    if SAMPLE_RUN.exists():
        runs.append(SAMPLE_RUN)
    return sorted(
        set(runs),
        key=lambda p: (p / "report.json").stat().st_mtime if (p / "report.json").exists() else 0,
        reverse=True,
    )


def sentiment_badge(sentiment: str) -> str:
    icons = {"positive": "✅", "negative": "⚠️", "neutral": "➖"}
    return icons.get(sentiment, "•")


def source_link_md(url: str, label: str = "source") -> str:
    return f"[{label} ↗]({url})" if url else ""


def render_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }

        .metric-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 1.1rem 1.4rem;
            text-align: center;
        }
        .metric-card .label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #94a3b8;
            margin-bottom: 0.3rem;
        }
        .metric-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #f1f5f9;
            line-height: 1;
        }
        .metric-card .sub {
            font-size: 0.78rem;
            color: #64748b;
            margin-top: 0.3rem;
        }

        .positive-card {
            border-left: 3px solid #22c55e;
            background: #052e16;
            border-radius: 8px;
            padding: 0.7rem 1rem;
            margin-bottom: 0.4rem;
            font-size: 0.88rem;
            color: #bbf7d0;
        }
        .negative-card {
            border-left: 3px solid #ef4444;
            background: #2d0a0a;
            border-radius: 8px;
            padding: 0.7rem 1rem;
            margin-bottom: 0.4rem;
            font-size: 0.88rem;
            color: #fecaca;
        }
        .neutral-card {
            border-left: 3px solid #94a3b8;
            background: #1e293b;
            border-radius: 8px;
            padding: 0.7rem 1rem;
            margin-bottom: 0.4rem;
            font-size: 0.88rem;
            color: #e2e8f0;
        }

        .result-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.6rem;
        }
        .result-card .result-title {
            font-weight: 600;
            font-size: 0.95rem;
            color: #f1f5f9;
            margin-bottom: 0.3rem;
        }
        .result-card .result-meta {
            font-size: 0.73rem;
            color: #64748b;
            margin-bottom: 0.5rem;
        }
        .result-card .result-snippet {
            font-size: 0.85rem;
            color: #94a3b8;
            line-height: 1.5;
        }

        .section-header {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #64748b;
            margin: 1.6rem 0 0.6rem 0;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 0.4rem;
        }

        .tag {
            display: inline-block;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 0.15rem 0.5rem;
            font-size: 0.72rem;
            color: #94a3b8;
            margin-right: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {"<div class='sub'>" + sub + "</div>" if sub else ""}
    </div>
    """


def sentiment_donut(pos: int, neg: int, neutral: int) -> go.Figure:
    total = pos + neg + neutral or 1
    labels = ["Positive", "Negative", "Neutral"]
    values = [pos, neg, neutral]
    colors = ["#22c55e", "#ef4444", "#94a3b8"]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.65,
            marker_colors=colors,
            textinfo="none",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
    )
    pct = round(pos / total * 100)
    fig.update_layout(
        annotations=[dict(text=f"{pct}%<br><span style='font-size:11px;color:#94a3b8'>positive</span>", x=0.5, y=0.5, font_size=22, font_color="#f1f5f9", showarrow=False)],
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(color="#94a3b8", size=12)),
        margin=dict(t=10, b=10, l=10, r=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=180,
    )
    return fig


def source_bar(source_breakdown: list) -> go.Figure:
    if not source_breakdown:
        return None
    df = pd.DataFrame(source_breakdown).sort_values("result_count")
    fig = go.Figure(
        go.Bar(
            x=df["result_count"],
            y=df["source_type"],
            orientation="h",
            marker_color="#3b82f6",
            text=df["result_count"],
            textposition="outside",
            textfont=dict(color="#94a3b8", size=11),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(tickfont=dict(color="#94a3b8", size=12)),
        margin=dict(t=5, b=5, l=10, r=40),
        height=max(120, len(df) * 42),
    )
    return fig


def render_result_card(item: dict) -> None:
    sentiment = item.get("sentiment", "neutral")
    border = SENTIMENT_COLORS.get(sentiment, "#94a3b8")
    url = item.get("url", "")
    title = item.get("title", "Untitled")
    snippet = item.get("snippet") or item.get("content", "")
    source_type = item.get("source_type", "")
    query_label = item.get("query_label", "")
    link_html = f' &nbsp;<a href="{url}" target="_blank" style="color:#3b82f6;font-size:0.78rem;">↗</a>' if url else ""
    matched = item.get("matched_terms", [])
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in matched[:6])
    st.markdown(
        f"""
        <div class="result-card" style="border-left: 3px solid {border};">
            <div class="result-title">{title}{link_html}</div>
            <div class="result-meta">{source_type} &nbsp;·&nbsp; {query_label}</div>
            <div class="result-snippet">{snippet[:280]}{"…" if len(snippet) > 280 else ""}</div>
            {"<div style='margin-top:0.5rem;'>" + tags_html + "</div>" if tags_html else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---- Page setup ----
st.set_page_config(page_title="Consumer Sentiment Monitor", page_icon="📡", layout="wide")
render_css()

runs = find_runs()
if not runs:
    st.error("No runs found. Run `python3 collect.py --dry-run` first.")
    st.stop()

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## 📡 Sentiment Monitor")
    run_labels = [str(p.relative_to(APP_DIR)) for p in runs]
    selected = st.selectbox("Run", run_labels, index=0, label_visibility="collapsed")
    run_dir = APP_DIR / selected
    report = load_json(run_dir / "report.json")
    normalized_path = run_dir / "normalized_results.json"
    normalized = load_json(normalized_path) if normalized_path.exists() else report.get("representative_examples", [])

    st.markdown("---")
    st.markdown("**Run a fresh collection**")
    st.code("python3 collect.py --config config/mentiondrop_config.json")
    st.code("python3 collect.py --dry-run")
    st.markdown(f"`{run_dir}`")

# ---- Header ----
summary = report.get("executive_summary", {})
metrics = report.get("metrics", {})
product = report.get("product_name", "Product")
overall = str(summary.get("overall_sentiment", "mixed")).lower()
overall_color = SENTIMENT_COLORS.get(overall, "#f59e0b")

col_title, col_badge = st.columns([5, 1])
with col_title:
    st.markdown(f"## {product}")
    st.markdown(f"<span style='color:#64748b;font-size:0.9rem;'>{report.get('launch_context', '')}</span>", unsafe_allow_html=True)
with col_badge:
    st.markdown(
        f"<div style='margin-top:1.2rem;text-align:right;font-size:1.1rem;font-weight:700;color:{overall_color};'>{overall.upper()}</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

# ---- KPI row ----
sentiment_counts = metrics.get("sentiment_counts", {})
pos = sentiment_counts.get("positive", 0)
neg = sentiment_counts.get("negative", 0)
neutral = sentiment_counts.get("neutral", 0)
total = metrics.get("total_results", 0)
pct_pos = round(pos / total * 100) if total else 0

c1, c2, c3, c4, c5 = st.columns(5)
cards = [
    ("Total signals", str(total), ""),
    ("Positive", str(pos), f"{pct_pos}% of total"),
    ("Negative", str(neg), f"{round(neg/total*100) if total else 0}% of total"),
    ("Neutral", str(neutral), f"{round(neutral/total*100) if total else 0}% of total"),
    ("Sources", str(len(metrics.get("source_counts", {}))), "channel types"),
]
for col, (label, value, sub) in zip([c1, c2, c3, c4, c5], cards):
    col.markdown(metric_card(label, value, sub), unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ---- Summary + donut ----
left, right = st.columns([3, 2])
with left:
    st.markdown('<div class="section-header">Executive summary</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:#1e293b;border-radius:10px;padding:1rem 1.2rem;color:#cbd5e1;font-size:0.9rem;line-height:1.6;'>{summary.get('summary', 'No summary available.')}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    th_left, th_right = st.columns(2)
    with th_left:
        st.markdown('<div class="section-header">Positive themes</div>', unsafe_allow_html=True)
        for theme in summary.get("positive_themes", []):
            st.markdown(f'<div class="positive-card">✓ {theme}</div>', unsafe_allow_html=True)
    with th_right:
        st.markdown('<div class="section-header">Emerging risks</div>', unsafe_allow_html=True)
        for risk in summary.get("emerging_risks", []):
            st.markdown(f'<div class="negative-card">⚠ {risk}</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-header">Sentiment split</div>', unsafe_allow_html=True)
    st.plotly_chart(sentiment_donut(pos, neg, neutral), use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="section-header">By source</div>', unsafe_allow_html=True)
    fig_bar = source_bar(report.get("source_breakdown", []))
    if fig_bar:
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

# ---- Sentiment buckets ----
st.markdown('<div class="section-header">Sentiment buckets</div>', unsafe_allow_html=True)
buckets = report.get("sentiment_buckets", {})
tabs = st.tabs(["✅ Positive", "⚠️ Negative", "➖ Neutral"])
for tab, key in zip(tabs, ["positive", "negative", "neutral"]):
    with tab:
        items = buckets.get(key, [])
        if not items:
            st.caption(f"No {key} signals in this run.")
        else:
            for item in items[:10]:
                render_result_card(item)

# ---- Query summaries ----
st.markdown('<div class="section-header">Query summaries</div>', unsafe_allow_html=True)
for query in report.get("query_summaries", []):
    label = query.get("label", "")
    focus = query.get("focus", "")
    count = query.get("result_count", 0)
    answer = query.get("answer", "")
    raw_query = query.get("query", "")
    with st.expander(f"{label}  ·  {focus}  ·  {count} results"):
        st.code(raw_query, language=None)
        if answer:
            st.markdown(f"<div style='color:#94a3b8;font-size:0.88rem;line-height:1.6;'>{answer}</div>", unsafe_allow_html=True)

# ---- Follow-up + actions ----
bottom_left, bottom_right = st.columns(2)
with bottom_left:
    st.markdown('<div class="section-header">Recommended follow-up searches</div>', unsafe_allow_html=True)
    for search in report.get("recommended_follow_up_searches", []):
        st.markdown(f"<div style='color:#94a3b8;font-size:0.87rem;padding:0.25rem 0;'>→ {search}</div>", unsafe_allow_html=True)
with bottom_right:
    st.markdown('<div class="section-header">Product / marketing actions</div>', unsafe_allow_html=True)
    for action in report.get("product_marketing_actions", []):
        st.markdown(f"<div style='color:#94a3b8;font-size:0.87rem;padding:0.25rem 0;'>• {action}</div>", unsafe_allow_html=True)

# ---- Raw data expander ----
with st.expander("Raw normalized results (first 50)"):
    st.json(normalized[:50])
