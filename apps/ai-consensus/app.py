"""
app.py — AI Consensus Dashboard
"""

import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
from dotenv import load_dotenv
from nimble_python import Nimble

sys.path.insert(0, str(Path(__file__).parent))
from analyze import analyze_with_haiku

load_dotenv()

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY")
ANALYSIS_DIR   = Path(__file__).parent / "data" / "analysis"
AGENTS         = ["chatgpt", "perplexity", "gemini"]
AGENT_LABELS   = {"chatgpt": "ChatGPT", "perplexity": "Perplexity", "gemini": "Gemini"}

CONSENSUS = {
    "strong":   {"label": "Strong Consensus",   "color": "#22c55e", "dot": "🟢"},
    "moderate": {"label": "Moderate Consensus", "color": "#f59e0b", "dot": "🟡"},
    "split":    {"label": "Split",              "color": "#ef4444", "dot": "🔴"},
}

st.set_page_config(page_title="AI Consensus Dashboard", page_icon="🤝", layout="wide")

st.markdown("""
<style>
  .stat-block { text-align: center; padding: 20px 0 10px 0; }
  .stat-num   { font-size: 48px; font-weight: 700; line-height: 1; }
  .stat-label { font-size: 13px; color: #888; margin-top: 4px; letter-spacing: 0.04em; text-transform: uppercase; }
  .agree-bar  { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 20px 0 8px 0; }
  .cat-card   { border: 1px solid #2a2a2a; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; }
  .cat-name   { font-weight: 600; font-size: 14px; margin-bottom: 2px; }
  .cat-meta   { font-size: 12px; color: #666; margin-bottom: 8px; }
  .mini-bar   { display: flex; height: 4px; border-radius: 2px; overflow: hidden; }
  .q-table    { width: 100%; border-collapse: collapse; font-size: 13px; }
  .q-table th { padding: 7px 12px; text-align: left; border-bottom: 1px solid #2a2a2a;
                font-size: 11px; font-weight: 500; color: #666;
                text-transform: uppercase; letter-spacing: 0.05em; }
  .q-table td { padding: 9px 12px; border-bottom: 1px solid #1e1e1e; vertical-align: top; }
  .q-table tr:hover td { background: rgba(255,255,255,0.02); }
  .q-text     { max-width: 280px; line-height: 1.4; }
  .verdict    { color: #bbb; font-style: italic; max-width: 180px; line-height: 1.4; }
  .con-pill   { display: inline-block; padding: 2px 8px; border-radius: 20px;
                font-size: 11px; font-weight: 500; white-space: nowrap; }
  .live-bar   { border-left: 4px solid; padding: 10px 14px; border-radius: 4px; margin: 12px 0 20px 0; }
</style>
""", unsafe_allow_html=True)


# ── Data ──────────────────────────────────────────────────────────────────────

@st.cache_data
def load_all():
    return [json.loads(p.read_text()) for p in sorted(ANALYSIS_DIR.glob("q_*.json"))]


# ── Helpers ───────────────────────────────────────────────────────────────────

def pct(n, total):
    return n / total * 100 if total else 0

def bar_seg(color, width):
    return f'<div style="width:{width:.1f}%;background:{color}"></div>'

def agree_bar(strong, moderate, split, total, height="8px", radius="4px"):
    s, m, d = pct(strong, total), pct(moderate, total), pct(split, total)
    return (
        f'<div style="display:flex;height:{height};border-radius:{radius};overflow:hidden">'
        f'{bar_seg("#22c55e", s)}{bar_seg("#f59e0b", m)}{bar_seg("#ef4444", d)}'
        f'</div>'
    )

def live_prompt(question):
    return (
        f"{question}\n\n"
        "Reply in exactly this format — no other text:\n"
        "VERDICT: [your answer in 5 words or fewer]\n"
        "REASON: [one sentence only]"
    )

def fetch_agent(nimble, agent, prompt):
    result  = nimble.agent.run(agent=agent, params={"prompt": prompt})
    parsing = result.data.parsing
    if not isinstance(parsing, dict):
        raise ValueError("Unexpected response format")
    text = (
        (parsing.get("markdown") or parsing.get("answer") or "").strip()
        if agent == "gemini"
        else (parsing.get("answer") or parsing.get("markdown") or "").strip()
    )
    if not text:
        raise ValueError("Empty response")
    return text


# ── Page header ───────────────────────────────────────────────────────────────

st.markdown(
    "## 🤝 AI Consensus Dashboard  "
    "<span style='font-size:14px;color:#888;font-weight:400'>"
    "Same question. Three AIs. Do they agree?</span>",
    unsafe_allow_html=True,
)

st.markdown(
    '<p style="color:#999;font-size:14px;max-width:680px;line-height:1.7;margin-bottom:4px">'
    "Nimble's Web Search Agents fetch live responses from ChatGPT, Perplexity, and Gemini simultaneously — "
    "no API keys for each model, one unified call. Claude then reads all three answers and judges whether "
    "they agree. Browse 100 pre-loaded questions across tech, finance, health, and more, or ask your own "
    "in the live tab."
    "</p>",
    unsafe_allow_html=True,
)

tab_browse, tab_live = st.tabs(["📊  Browse Questions", "⚡  Ask Your Own"])


# ─────────────────────────────── Browse tab ───────────────────────────────────

with tab_browse:
    all_data = load_all()

    if not all_data:
        st.info("No analysis data yet. Run `python3 analyze.py` after adding your ANTHROPIC_API_KEY.")
        st.stop()

    total  = len(all_data)
    counts = {lbl: sum(1 for d in all_data if d["consensus"]["label"] == lbl)
              for lbl in ("strong", "moderate", "split")}

    # ── Hero stats ────────────────────────────────────────────────────────────

    s, m, d = counts["strong"], counts["moderate"], counts["split"]

    st.markdown(
        f'<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;margin:8px 0 4px 0">'
        f'<div style="flex:{s};background:#22c55e"></div>'
        f'<div style="flex:{m};background:#f59e0b"></div>'
        f'<div style="flex:{d};background:#ef4444"></div>'
        f'</div>'
        f'<div style="font-size:12px;color:#555;margin-bottom:20px">'
        f'<span style="color:#22c55e">■</span> Strong &nbsp;&nbsp;'
        f'<span style="color:#f59e0b">■</span> Moderate &nbsp;&nbsp;'
        f'<span style="color:#ef4444">■</span> Split'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="stat-block">'
            f'<div class="stat-num" style="color:#22c55e">{s}</div>'
            f'<div class="stat-label">Strong Consensus</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-block">'
            f'<div class="stat-num" style="color:#f59e0b">{m}</div>'
            f'<div class="stat-label">Moderate Consensus</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="stat-block">'
            f'<div class="stat-num" style="color:#ef4444">{d}</div>'
            f'<div class="stat-label">Split</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # ── Category breakdown ────────────────────────────────────────────────────

    categories = sorted({d["category"] for d in all_data})
    cat_cols   = st.columns(3)

    for i, cat in enumerate(categories):
        items = [d for d in all_data if d["category"] == cat]
        n     = len(items)
        cs    = {lbl: sum(1 for d in items if d["consensus"]["label"] == lbl)
                 for lbl in ("strong", "moderate", "split")}

        with cat_cols[i % 3]:
            st.markdown(
                f'<div class="cat-card">'
                f'<div class="cat-name">{cat}</div>'
                f'<div class="cat-meta">'
                f'<span style="color:#22c55e">●</span> {cs["strong"]} &nbsp;'
                f'<span style="color:#f59e0b">●</span> {cs["moderate"]} &nbsp;'
                f'<span style="color:#ef4444">●</span> {cs["split"]}'
                f'</div>'
                + agree_bar(cs["strong"], cs["moderate"], cs["split"], n, height="4px", radius="2px") +
                f'</div>',
                unsafe_allow_html=True,
            )

    st.write("")

    # ── Filters & sort ────────────────────────────────────────────────────────

    f1, f2, f3, f4 = st.columns([2, 2, 2, 3])
    cat_sel = f1.selectbox("Category", ["All"] + categories, label_visibility="collapsed")
    con_sel = f2.selectbox("Consensus", ["All", "Strong", "Moderate", "Split"], label_visibility="collapsed")
    sort_by = f3.selectbox("Sort by", ["Default", "Question A–Z", "Strong first", "Split first"], label_visibility="collapsed")
    search  = f4.text_input("Search", placeholder="Search questions…", label_visibility="collapsed")

    shown = all_data
    if cat_sel != "All":
        shown = [d for d in shown if d["category"] == cat_sel]
    if con_sel != "All":
        shown = [d for d in shown if d["consensus"]["label"] == con_sel.lower()]
    if search:
        shown = [d for d in shown if search.lower() in d["question"].lower()]

    LABEL_ORDER = {"strong": 0, "moderate": 1, "split": 2}
    if sort_by == "Question A–Z":
        shown = sorted(shown, key=lambda d: d["question"].lower())
    elif sort_by == "Strong first":
        shown = sorted(shown, key=lambda d: LABEL_ORDER[d["consensus"]["label"]])
    elif sort_by == "Split first":
        shown = sorted(shown, key=lambda d: -LABEL_ORDER[d["consensus"]["label"]])

    st.caption(f"{len(shown)} of {total} questions")

    # ── Question table (grouped by category) ─────────────────────────────────

    def make_row(d):
        lbl   = d["consensus"]["label"]
        color = CONSENSUS[lbl]["color"]
        q     = d["question"].replace("<", "&lt;").replace(">", "&gt;")
        gpt   = d["models"]["chatgpt"]["verdict"].replace("<", "&lt;")
        perp  = d["models"]["perplexity"]["verdict"].replace("<", "&lt;")
        gem   = d["models"]["gemini"]["verdict"].replace("<", "&lt;")
        pill  = (
            f'<span class="con-pill" style="background:{color}22;color:{color}">'
            f'{CONSENSUS[lbl]["label"]}</span>'
        )
        return (
            f'<tr>'
            f'<td style="width:130px">{pill}</td>'
            f'<td class="q-text">{q}</td>'
            f'<td class="verdict">{gpt}</td>'
            f'<td class="verdict">{perp}</td>'
            f'<td class="verdict">{gem}</td>'
            f'</tr>'
        )

    def cat_header(cat):
        return (
            f'<tr><td colspan="5" style="'
            f'padding:18px 12px 6px;font-size:11px;font-weight:600;'
            f'color:#555;text-transform:uppercase;letter-spacing:0.08em;'
            f'border-bottom:1px solid #2a2a2a">'
            f'{cat}</td></tr>'
        )

    # Group by category preserving current sort order within each group
    from collections import OrderedDict
    grouped: dict = OrderedDict()
    for d in shown:
        grouped.setdefault(d["category"], []).append(d)

    rows = []
    for cat, items in grouped.items():
        rows.append(cat_header(cat))
        rows.extend(make_row(d) for d in items)

    st.markdown(
        f'<table class="q-table">'
        f'<thead><tr>'
        f'<th></th><th>Question</th>'
        f'<th>ChatGPT</th><th>Perplexity</th><th>Gemini</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────── Live tab ─────────────────────────────────────

with tab_live:
    st.markdown(
        "Type any question and get **live** answers from ChatGPT, Perplexity, and Gemini "
        "simultaneously — each response takes ~60s via Nimble's browser agents."
    )
    st.write("")

    question = st.text_input(
        "Your question",
        placeholder="e.g. Is Python better than JavaScript for web development?",
        label_visibility="collapsed",
    )
    ask = st.button("⚡ Ask all three AIs", type="primary", disabled=not question)

    if ask and question:
        if not NIMBLE_API_KEY:
            st.error("NIMBLE_API_KEY is not set. Add it to your .env file.")
            st.stop()
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
            st.stop()

        nimble  = Nimble(api_key=NIMBLE_API_KEY)
        prompt  = live_prompt(question)
        results = {}
        errors  = {}

        with st.status("Asking the AIs… (each takes ~60s)", expanded=True) as status:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(fetch_agent, nimble, agent, prompt): agent
                    for agent in AGENTS
                }
                for future in as_completed(futures):
                    agent = futures[future]
                    try:
                        results[agent] = future.result()
                        st.write(f"✓ **{AGENT_LABELS[agent]}** responded")
                    except Exception as e:
                        errors[agent] = str(e)
                        st.write(f"✗ **{AGENT_LABELS[agent]}** failed: {e}")
            status.update(
                label=f"{len(results)}/3 responses received",
                state="complete" if results else "error",
            )

        if not results:
            st.error("All three agents failed. Check your API key and try again.")
        else:
            st.divider()

            with st.spinner("Claude is reading all three responses…"):
                responses = {agent: {"raw": raw} for agent, raw in results.items()}
                analysis  = analyze_with_haiku(question, responses)

            con   = analysis["consensus"]
            color = CONSENSUS[con["label"]]["color"]
            lbl   = CONSENSUS[con["label"]]["label"]
            st.markdown(
                f'<div class="live-bar" style="border-color:{color};background:{color}18">'
                f'<strong style="color:{color}">{lbl}</strong>'
                f'&nbsp;&nbsp;·&nbsp;&nbsp;{con["summary"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

            cols = st.columns(3)
            for i, agent in enumerate(AGENTS):
                with cols[i]:
                    st.markdown(f"**{AGENT_LABELS[agent]}**")
                    if agent in analysis["models"]:
                        m = analysis["models"][agent]
                        st.markdown(f"*{m['verdict']}*")
                        if m["reason"]:
                            st.caption(m["reason"])
                        with st.expander("Full response"):
                            st.write(m["raw"])
                    else:
                        st.error(errors.get(agent, "unknown error"))
