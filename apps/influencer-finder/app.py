"""Influencer Finder — Streamlit dashboard. Reads from Supabase, falls back to the
local cache (data/influencers.json). Run: streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

import config as C
import supabase_store

st.set_page_config(page_title="Influencer Finder", page_icon="📣", layout="wide")
st.markdown("<style>.stApp{background:#0e1117} a{color:#edc602 !important}</style>", unsafe_allow_html=True)

st.title("📣 Influencer Finder")

rows = supabase_store.fetch_all()
source = "Supabase"
if rows is None:
    p = C.DATA / "influencers.json"
    rows = json.loads(p.read_text()) if p.exists() else []
    source = "local cache"
st.caption(f"Outreach-ready influencer dataset · source: {source} · powered by Nimble Web Search Agents")

if not rows:
    st.warning("No data yet. Run `python discover.py`.")
    st.stop()

df = pd.DataFrame(rows)
for col in ["platform", "handle", "category", "niche", "location", "followers_display", "engagement_rate",
            "contact", "profile_url", "follower_count_num"]:
    if col not in df:
        df[col] = None

c1, c2, c3 = st.columns(3)
c1.metric("Influencers", len(df))
c2.metric("Platforms", df["platform"].nunique())
c3.metric("Categories", df["category"].dropna().nunique())

f1, f2, f3 = st.columns([1, 1, 1])
plats = f1.multiselect("Platform", sorted(df["platform"].dropna().unique()))
cats = f2.multiselect("Category", sorted(df["category"].dropna().unique()))
_mx = df["follower_count_num"].max()
max_k = max(1, int(_mx / 1000) + 1 if pd.notna(_mx) else 1)   # guard all-null -> NaN
min_k = f3.slider("Min followers (K)", min_value=0, max_value=max_k, value=0, step=5)

v = df.copy()
if plats:
    v = v[v["platform"].isin(plats)]
if cats:
    v = v[v["category"].isin(cats)]
v = v[v["follower_count_num"].fillna(0).astype("int64") >= min_k * 1000]
v = v.sort_values("follower_count_num", ascending=False, na_position="last")

cols = ["handle", "platform", "category", "followers_display", "engagement_rate", "niche", "location", "contact", "profile_url"]
show = v[cols].rename(columns={
    "handle": "Handle", "platform": "Platform", "category": "Category", "followers_display": "Followers",
    "engagement_rate": "Engagement", "niche": "Niche", "location": "Location",
    "contact": "Contact", "profile_url": "Profile"})
st.dataframe(show, use_container_width=True, hide_index=True, height=460,
             column_config={"Profile": st.column_config.LinkColumn("Profile", display_text="open")})

def _csv_safe(df):
    """Prevent CSV/formula injection: prefix cells that start with = + - @ with a quote."""
    def s(x):
        return "'" + x if isinstance(x, str) and x[:1] in ("=", "+", "-", "@") else x
    return df.applymap(s)


st.download_button("Download CSV", _csv_safe(v[cols]).to_csv(index=False).encode(),
                   file_name="influencers.csv", mime="text/csv")
