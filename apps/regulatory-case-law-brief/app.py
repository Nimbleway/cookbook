"""Regulatory & Case-Law Brief — Streamlit viewer. Reads structured data/briefs.json.
Run: streamlit run app.py"""
import html
import json
import re

import streamlit as st

import config as C

YELLOW = "#edc602"
st.set_page_config(page_title="Regulatory & Case-Law Brief", page_icon="⚖️", layout="wide")
st.markdown(f"""
<style>
  .stApp {{ background:#0e1117; }}
  .block-container {{ max-width:1000px; padding-top:2rem; }}   /* narrower = more readable text */
  h1,h2,h3 {{ color:#f5f5f2; }}
  a {{ color:{YELLOW} !important; }}
  .chip {{ display:inline-block; background:#1a1d24; border:1px solid #2b2f38; border-radius:999px;
           padding:3px 12px; font-size:.8rem; color:#c3c2b7; margin-bottom:.4rem; }}
  .disc {{ color:#8a94a6; font-size:.8rem; font-style:italic; }}
  div[data-testid="stExpander"] {{ border:1px solid #2b2f38; border-radius:10px; margin-bottom:6px; }}
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Regulatory & Case-Law Brief")
st.caption("Cited compliance briefs from primary sources · powered by Nimble Web Search Agents")

path = C.DATA / "briefs.json"
try:
    briefs = json.loads(path.read_text()) if path.exists() else []
except (json.JSONDecodeError, OSError) as e:
    st.error(f"Could not read {path.name} ({e}). Re-run `python run_brief.py`.")
    st.stop()
if not briefs:
    st.warning("No briefs yet. Run `python run_brief.py`.")
    st.stop()


def readable_summary(s: str) -> str:
    """Break the agent's dense summary into paragraphs: bold + newline before inline CAPS labels."""
    s = re.sub(r"^\s*RESEARCH,?\s*NOT LEGAL ADVICE\.?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+([A-Z][A-Z0-9 /&()-]{3,}:)", r"\n\n**\1** ", s)
    return s.strip()


# index by position (subjects can collide; a dict keyed on subject would drop briefs)
idx = st.selectbox("Topic", range(len(briefs)), format_func=lambda i: briefs[i]["subject"])
b = briefs[idx]

st.markdown(f'<span class="chip">📍 {html.escape(str(b.get("jurisdiction", "—")))}</span>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Regulations", len(b.get("regulations", [])))
c2.metric("Key cases", len(b.get("cases", [])))
c3.metric("Recent changes", len(b.get("changes", [])))
c4.metric("Sources", len(b.get("sources", [])))
st.markdown('<div class="disc">Research summary, not legal advice.</div>', unsafe_allow_html=True)

st.subheader("Summary")
st.markdown(readable_summary(b.get("summary", "")))

tabs = st.tabs([f"Regulations ({len(b.get('regulations',[]))})",
                f"Case law ({len(b.get('cases',[]))})",
                f"Recent changes ({len(b.get('changes',[]))})",
                f"Sources ({len(b.get('sources',[]))})"])

with tabs[0]:
    for r in b.get("regulations", []):
        title = r["name"] + (f"  ·  {r['jurisdiction']}" if r.get("jurisdiction") else "")
        with st.expander(title):
            if r.get("requirement"):
                st.write(r["requirement"])
            if r.get("url"):
                st.markdown(f"[Primary source ↗]({r['url']})")
    if not b.get("regulations"):
        st.info("None found.")

with tabs[1]:
    for c in b.get("cases", []):
        meta = ", ".join(x for x in [c.get("court"), c.get("date")] if x)
        title = c["case_name"] + (f"  ·  {meta}" if meta else "")
        with st.expander(title):
            if c.get("holding"):
                st.write(c["holding"])
            if c.get("url"):
                st.markdown(f"[Source ↗]({c['url']})")
    if not b.get("cases"):
        st.info("None found.")

with tabs[2]:
    for ch in b.get("changes", []):
        line = (f"**{ch['date']}** — " if ch.get("date") else "") + ch.get("change", "")
        if ch.get("url"):
            line += f"  [source]({ch['url']})"
        st.markdown(f"- {line}")
    if not b.get("changes"):
        st.info("None noted.")

with tabs[3]:
    for u in b.get("sources", []):
        st.markdown(f"- [{u}]({u})")
    if not b.get("sources"):
        st.info("None.")
