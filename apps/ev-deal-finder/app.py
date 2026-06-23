"""
EV Deal Finder — Streamlit dashboard
Powered by Nimble Web Search Agents + eBay Motors data

Usage:
    streamlit run app.py
    streamlit run app.py -- --export  # write results to CSV
"""

import sys
import json
import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from score import score_listings

# ── Config ─────────────────────────────────────────────────────────────
DATA_FILE = Path(__file__).parent / "data" / "listings.json"
GAS_PRICE = 4.229   # National average, AAA April 2026
BRAND_YELLOW = "#edc602"
COLORS = px.colors.qualitative.Bold

st.set_page_config(
    page_title="EV Deal Finder",
    page_icon="⚡",
    layout="wide",
)

# ── CLI: --export flag ──────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--export", action="store_true", help="Export results to CSV and exit")
args, _ = parser.parse_known_args()


# ── Load & score data ───────────────────────────────────────────────────
def load_data():
    with open(DATA_FILE) as f:
        listings = json.load(f)
    listings = score_listings(listings)
    df = pd.DataFrame(listings)
    df["year"] = df["year"].astype("Int64")
    df["mileage"] = pd.to_numeric(df["mileage"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["deal_score_pct"] = (df["deal_score"] * 100).round(1)
    df["price_score_pct"] = (df["price_score"] * 100).round(1)
    df["mileage_score_pct"] = (df["mileage_score"] * 100).round(1)
    df["year_score_pct"] = (df["year_score"] * 100).round(1)
    df["condition_score_pct"] = (df["condition_score"] * 100).round(1)
    df["safety_score_pct"] = (df["safety_score"] * 100).round(1)
    df["label"] = df["year"].astype(str) + " " + df["make"] + " " + df["model"]
    return df


df = load_data()

# ── Export mode ─────────────────────────────────────────────────────────
if args.export:
    out = Path(__file__).parent / "ev_deals_export.csv"
    export_cols = [
        "item_id", "label", "year", "make", "model", "price", "mileage",
        "condition", "title_status", "city", "state",
        "deal_score", "price_score", "mileage_score", "year_score",
        "condition_score", "safety_score", "url"
    ]
    df[export_cols].sort_values("deal_score", ascending=False).to_csv(out, index=False)
    print(f"Exported {len(df)} listings to {out}")
    sys.exit(0)


# ── Header ──────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='background:#1a1a2e;padding:1.2rem 1.5rem;border-radius:8px;margin-bottom:1rem'>
        <span style='font-size:1.5rem;font-weight:700;color:{BRAND_YELLOW}'>⚡ EV Deal Finder</span>
        &nbsp;&nbsp;
        <span style='color:#aaa;font-size:0.95rem'>Powered by Nimble Web Search Agents · eBay Motors</span>
        <span style='float:right;color:#ff6b6b;font-size:0.95rem'>
            ⛽ National avg gas: <strong>${GAS_PRICE}/gal</strong> — highest since Aug 2022
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar filters ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    models = sorted(df["model"].dropna().unique())
    sel_models = st.multiselect("Model", models, default=models)

    years = sorted(df["year"].dropna().unique())
    year_range = st.slider("Year", int(min(years)), int(max(years)), (int(min(years)), int(max(years))))

    price_range = st.slider(
        "Max Price ($)",
        int(df["price"].min()), int(df["price"].max()),
        int(df["price"].max()),
        step=500,
    )

    max_miles = st.slider(
        "Max Mileage",
        0, int(df["mileage"].max()), int(df["mileage"].max()),
        step=5000,
    )

    min_score = st.slider("Min Deal Score", 0, 100, 0, step=5)


# ── Filter data ─────────────────────────────────────────────────────────
fdf = df[
    df["model"].isin(sel_models)
    & df["year"].between(year_range[0], year_range[1])
    & (df["price"] <= price_range)
    & (df["mileage"] <= max_miles)
    & (df["deal_score_pct"] >= min_score)
].copy()


# ── KPI row ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Listings", len(fdf), f"{len(df)} total")
c2.metric("Avg Price", f"${fdf['price'].mean():,.0f}" if len(fdf) else "—")
c3.metric("Avg Mileage", f"{fdf['mileage'].mean():,.0f} mi" if len(fdf) else "—")
c4.metric("Top Deal Score", f"{fdf['deal_score_pct'].max():.0f}%" if len(fdf) else "—")

st.divider()


# ── Helper: ranking bar chart ────────────────────────────────────────────
def ranking_chart(data, score_col, raw_col, raw_label, title, lower_is_better=False):
    """Bar chart of all listings ranked by score_col, annotated with raw_col value."""
    ranked = data.sort_values(score_col, ascending=False).copy()
    ranked["rank"] = range(1, len(ranked) + 1)
    ranked["bar_label"] = ranked[raw_col].apply(
        lambda x: f"${x:,.0f}" if raw_label == "price"
        else f"{x:,.0f} mi" if raw_label == "mileage"
        else str(x)
    )

    fig = px.bar(
        ranked,
        x=score_col,
        y="label",
        color="model",
        orientation="h",
        text="bar_label",
        hover_data=["year", "city", "state", score_col],
        labels={score_col: "Score (%)", "label": ""},
        color_discrete_sequence=COLORS,
        height=max(400, len(ranked) * 28),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        showlegend=True,
        xaxis=dict(range=[0, 110], title="Score (%)"),
        yaxis=dict(autorange="reversed"),
        margin=dict(t=10, b=10, l=10, r=80),
    )
    return fig


# ── Helper: deal card ─────────────────────────────────────────────────────
def deal_card(row):
    score_color = "#4caf50" if row["deal_score_pct"] >= 75 else "#edc602" if row["deal_score_pct"] >= 55 else "#ff6b6b"
    return f"""
    <div style='border:1px solid #333;border-radius:10px;padding:1rem;background:#111;height:100%'>
        <div style='font-size:1.1rem;font-weight:700;color:#fff;margin-bottom:0.3rem'>{row["label"]}</div>
        <div style='font-size:2rem;font-weight:800;color:{score_color}'>{row["deal_score_pct"]:.0f}<span style='font-size:1rem'>%</span></div>
        <div style='color:#aaa;font-size:0.85rem;margin-bottom:0.6rem'>Deal Score</div>
        <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;font-size:0.9rem'>
            <div><span style='color:#888'>Price</span><br><strong style='color:#fff'>${row["price"]:,.0f}</strong></div>
            <div><span style='color:#888'>Mileage</span><br><strong style='color:#fff'>{int(row["mileage"]):,} mi</strong></div>
            <div><span style='color:#888'>Condition</span><br><strong style='color:#fff'>{row["condition"] or "—"}</strong></div>
            <div><span style='color:#888'>Location</span><br><strong style='color:#fff'>{row["city"]}, {row["state"]}</strong></div>
        </div>
        <div style='margin-top:0.8rem'>
            <a href='{row["url"]}' target='_blank' style='color:{BRAND_YELLOW};font-size:0.9rem;text-decoration:none'>View on eBay →</a>
        </div>
    </div>
    """


# ── Tabs ─────────────────────────────────────────────────────────────────
tab_overview, tab_top, tab_price, tab_mileage, tab_year, tab_condition, tab_safety = st.tabs([
    "📊 Overview",
    "🏆 Top Deals",
    "💰 Price",
    "📍 Mileage",
    "📅 Year",
    "🔧 Condition",
    "🛡️ Safety",
])


# ── Overview tab ─────────────────────────────────────────────────────────
with tab_overview:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Deal Score by Model")
        fig1 = px.box(
            fdf, x="model", y="deal_score_pct", color="model",
            labels={"deal_score_pct": "Deal Score (%)", "model": ""},
            color_discrete_sequence=COLORS,
        )
        fig1.update_layout(showlegend=False, height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.subheader("Price vs Mileage")
        fig2 = px.scatter(
            fdf, x="mileage", y="price", color="model", size="deal_score_pct",
            hover_data=["label", "year", "city", "state", "deal_score_pct"],
            labels={"mileage": "Mileage", "price": "Price ($)", "model": ""},
            color_discrete_sequence=COLORS,
        )
        fig2.update_layout(height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Listings by Year")
        year_counts = fdf.groupby(["year", "model"]).size().reset_index(name="count")
        fig3 = px.bar(
            year_counts, x="year", y="count", color="model",
            labels={"count": "Listings", "year": "Year"},
            color_discrete_sequence=COLORS,
        )
        fig3.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.subheader("Score Breakdown — Top Deal")
        if len(fdf):
            top = fdf.sort_values("deal_score", ascending=False).iloc[0]
            fig4 = go.Figure(go.Bar(
                x=[top["price_score_pct"], top["mileage_score_pct"], top["year_score_pct"],
                   top["condition_score_pct"], top["safety_score_pct"]],
                y=["Price (30%)", "Mileage (25%)", "Year (20%)", "Condition (15%)", "Safety (10%)"],
                orientation="h",
                marker_color=BRAND_YELLOW,
                text=[f"{v:.0f}" for v in [top["price_score_pct"], top["mileage_score_pct"],
                      top["year_score_pct"], top["condition_score_pct"], top["safety_score_pct"]]],
                textposition="outside",
            ))
            fig4.update_layout(
                title=dict(text=top["label"], font=dict(size=13)),
                height=300, margin=dict(t=40, b=10),
                xaxis=dict(range=[0, 115], title="Score (0–100)"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig4, use_container_width=True)

    st.subheader(f"All Listings ({len(fdf)})")
    table_cols = ["deal_score_pct", "label", "year", "price", "mileage", "condition", "city", "state", "url"]
    display = fdf.sort_values("deal_score", ascending=False)[table_cols].rename(columns={
        "deal_score_pct": "Score %", "label": "Vehicle", "year": "Year",
        "price": "Price", "mileage": "Miles", "condition": "Condition",
        "city": "City", "state": "State", "url": "eBay Link",
    })
    display["Price"] = display["Price"].apply(lambda x: f"${x:,.0f}")
    display["Miles"] = display["Miles"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    st.dataframe(
        display, use_container_width=True, hide_index=True,
        column_config={
            "eBay Link": st.column_config.LinkColumn("eBay Link", display_text="View →"),
            "Score %": st.column_config.ProgressColumn("Score %", min_value=0, max_value=100, format="%.0f%%"),
        },
    )


# ── Top Deals tab ─────────────────────────────────────────────────────────
with tab_top:
    st.subheader("Top 4 Overall Deals")
    st.caption("Ranked by weighted deal score: Price (30%) · Mileage (25%) · Year (20%) · Condition (15%) · Safety (10%)")

    top4 = fdf.sort_values("deal_score", ascending=False).head(4)

    if len(top4) == 0:
        st.info("No listings match current filters.")
    else:
        cols = st.columns(min(len(top4), 4))
        for i, (_, row) in enumerate(top4.iterrows()):
            with cols[i]:
                st.markdown(deal_card(row), unsafe_allow_html=True)

    st.divider()
    st.subheader("Score Breakdown — Top 4")

    if len(top4):
        metrics = ["Price", "Mileage", "Year", "Condition", "Safety"]
        score_cols = ["price_score_pct", "mileage_score_pct", "year_score_pct", "condition_score_pct", "safety_score_pct"]

        fig_breakdown = go.Figure()
        for _, row in top4.iterrows():
            fig_breakdown.add_trace(go.Bar(
                name=row["label"],
                x=metrics,
                y=[row[c] for c in score_cols],
            ))
        fig_breakdown.update_layout(
            barmode="group",
            height=350,
            yaxis=dict(range=[0, 110], title="Score (%)"),
            margin=dict(t=10, b=10),
            legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig_breakdown, use_container_width=True)


# ── Metric tabs (shared logic) ────────────────────────────────────────────
# (sort_col, sort_asc, primary_col, primary_label, fmt, caption)
METRIC_CONFIG = {
    "price":     ("price",        True,  "price",        "Price",      "price",    "Sorted cheapest first — best price across all models scores 100%"),
    "mileage":   ("mileage",      True,  "mileage",      "Mileage",    "mileage",  "Sorted lowest mileage first — least wear scores 100%"),
    "year":      ("year",         False, "year",         "Year",       "year",     "Sorted newest first — most recent model year scores 100%"),
    "condition": ("condition_score_pct", False, "condition", "Condition", "text",  "Sorted by condition label — Certified Pre-Owned scores highest"),
    "safety":    ("safety_score_pct",    False, "title_status", "Title",  "text",  "Sorted by title status — Clean title scores 100%, Salvage scores 20%"),
}

def render_metric_tab(key, tab):
    sort_col, sort_asc, primary_col, primary_label, fmt, caption = METRIC_CONFIG[key]
    with tab:
        if len(fdf) == 0:
            st.info("No listings match current filters.")
            return

        ranked = fdf.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)
        ranked.index += 1  # 1-based rank

        # Build display table
        score_col = f"{key}_score_pct" if key in ("price", "mileage", "year") else sort_col

        table = pd.DataFrame()
        table["#"] = ranked.index
        table["Vehicle"] = ranked["label"]
        table["Year"] = ranked["year"]

        if fmt == "price":
            table[primary_label] = ranked[primary_col].apply(lambda x: f"${x:,.0f}")
        elif fmt == "mileage":
            table[primary_label] = ranked[primary_col].apply(lambda x: f"{x:,.0f} mi" if pd.notna(x) else "—")
        else:
            table[primary_label] = ranked[primary_col].fillna("—").astype(str)

        table["Score %"] = ranked[score_col]
        table["City"] = ranked["city"]
        table["State"] = ranked["state"]
        table["eBay Link"] = ranked["url"]

        st.caption(caption)
        st.dataframe(
            table, use_container_width=True, hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn("#", width="small"),
                "eBay Link": st.column_config.LinkColumn("eBay Link", display_text="View →"),
                "Score %": st.column_config.ProgressColumn("Score %", min_value=0, max_value=100, format="%.0f%%"),
            },
        )


render_metric_tab("price",     tab_price)
render_metric_tab("mileage",   tab_mileage)
render_metric_tab("year",      tab_year)
render_metric_tab("condition", tab_condition)
render_metric_tab("safety",    tab_safety)


# ── Footer ───────────────────────────────────────────────────────────────
st.caption(
    f"Data sourced from eBay Motors via Nimble Web Search Agents · "
    f"{len(df)} listings collected · Gas price: AAA national average April 2026"
)
