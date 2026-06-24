import html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Amazon Price Tracker", layout="wide", page_icon="📦")

ZIP_LABELS = {
    "10001": "New York, NY",
    "33101": "Miami, FL",
    "60601": "Chicago, IL",
    "77001": "Houston, TX",
    "90001": "Los Angeles, CA",
    "58601": "Bismarck, ND",
    "59501": "Great Falls, MT",
    "69201": "Valentine, NE",
    "41501": "Pikeville, KY",
    "38930": "Greenwood, MS",
}

ZIP_COLORS = [
    "#edc602", "#e05c2a", "#4ab8e8", "#7ec66a",
    "#c97de0", "#e84a7f", "#4ae8c9", "#e8a84a",
    "#a0a0ff", "#ff8080",
]

STORY_CALLOUTS = {
    "B09ND9NGTC": r"🔁 **Algorithmic repricing detected.** This product oscillates between ~\$8 and ~\$25 repeatedly — crashing 67% multiple times across the window, then inflating back. A textbook example of why continuous monitoring matters.",
    "B0FHLPS8ZF": r"🎧 **Launch price correction.** Started at full MSRP (\$199.95) in the first run and dropped \$90 within hours — a common pattern when a product goes live before promotional pricing kicks in.",
}

ROW_CSS = """<style>
.nft{overflow-y:auto;border:1px solid #2a2a3e;border-radius:6px;font-size:14px;}
.nft-hdr{display:flex;padding:8px 14px;color:#888;font-size:11px;
    text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid #2a2a3e;}
a.nft-row{display:flex;align-items:center;border-bottom:1px solid #1a1f2e;
    color:#e0e0e0;text-decoration:none;}
a.nft-row:hover{background:#1a1f2e;}
a.nft-row span{padding:10px 14px;overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap;min-width:0;}
.pname{font-weight:500;}
.brand{color:#aaa!important;font-size:13px;}
.cat{color:#888!important;font-size:12px;}
.pos{color:#edc602!important;font-weight:600;}
.zero{color:#444!important;}
.green{color:#7ec66a!important;font-weight:600;}
.red{color:#e05c2a!important;font-weight:600;}
</style>"""


def _nft_span(text, flex, cls, align):
    # Replace bare $ with &#36; but don't touch already-encoded &#36;
    text = str(text).replace("&#36;", "\x00").replace("$", "&#36;").replace("\x00", "&#36;")
    s = f"flex:{flex};min-width:0;" + ("text-align:right;" if align == "right" else "")
    return f'<span class="{cls}" style="{s}">{text}</span>'


def nft_header(cells):
    """cells: [(label, flex, align)]"""
    return '<div class="nft-hdr">' + "".join(_nft_span(t, f, "", a) for t, f, a in cells) + "</div>"


def nft_row(href, cells):
    """cells: [(text, flex, cls, align)]"""
    return f'<a href="{href}" class="nft-row">' + "".join(_nft_span(t, f, c, a) for t, f, c, a in cells) + "</a>\n"


def nft_render(content_html, height=500):
    st.markdown(
        ROW_CSS + f'<div class="nft" style="max-height:{height}px;">{content_html}</div>',
        unsafe_allow_html=True,
    )


# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    ph = pd.read_parquet("data/price_history.parquet")
    ph["zip_code"] = ph["zip_code"].astype(str).str.zfill(5)
    ph["zip_label"] = ph["zip_code"].map(ZIP_LABELS).fillna(ph["zip_code"])
    ph["timestamp"] = pd.to_datetime(ph["timestamp"])

    swings = pd.read_parquet("data/asin_swings.parquet")
    swings["product_title"] = swings["product_title"].fillna("Unknown")
    swings["brand"] = swings["brand"].fillna("—")
    swings["category"] = swings["best_sellers_category_1_name"].fillna("—")

    meta = pd.read_parquet("data/asin_meta.parquet")

    zip_stats = pd.read_parquet("data/zip_stats.parquet")
    zip_stats["zip_code"] = zip_stats["zip_code"].astype(str).str.zfill(5)
    zip_stats["zip_label"] = zip_stats["zip_code"].map(ZIP_LABELS).fillna(zip_stats["zip_code"])

    try:
        sig_hist = pd.read_parquet("data/signals_history.parquet")
        sig_hist["timestamp"] = pd.to_datetime(sig_hist["timestamp"])
        title_chg = pd.read_parquet("data/title_changes.parquet")
        oos_sum = pd.read_parquet("data/oos_summary.parquet")
        sig_alerts = pd.read_parquet("data/signal_alerts.parquet")
        if len(sig_alerts) > 0 and "timestamp" in sig_alerts.columns:
            sig_alerts["timestamp"] = pd.to_datetime(sig_alerts["timestamp"])
    except FileNotFoundError:
        sig_hist = pd.DataFrame()
        title_chg = pd.DataFrame()
        oos_sum = pd.DataFrame()
        sig_alerts = pd.DataFrame()

    return ph, swings, meta, zip_stats, sig_hist, title_chg, oos_sum, sig_alerts


ph, swings, meta, zip_stats, sig_hist, title_chg, oos_sum, sig_alerts = load_data()

zip_gap = (
    zip_stats.groupby("asin")
    .agg(zip_min=("price_median", "min"), zip_max=("price_median", "max"))
    .reset_index()
)
zip_gap["gap_abs"] = (zip_gap["zip_max"] - zip_gap["zip_min"]).round(3)
zip_gap["gap_pct"] = (zip_gap["gap_abs"] / zip_gap["zip_min"] * 100).round(2)


# ── URL-based routing ────────────────────────────────────────────────────────
query_asin = st.query_params.get("asin")
query_page = st.query_params.get("page", "overview")
current_page = "product" if query_asin else query_page


def nav(page, asin=None, from_page=None):
    st.query_params.clear()
    if asin:
        st.query_params["asin"] = asin
        if from_page:
            st.query_params["from"] = from_page
    else:
        st.query_params["page"] = page
    st.rerun()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 Amazon Price Tracker")
    st.markdown("*96-hour study · May 2026*")
    st.divider()

    if current_page == "product":
        back_page = st.query_params.get("from", "swings")
        if st.button("← Back", use_container_width=True):
            nav(back_page)
        st.divider()

    page_labels = {"overview": "Overview", "swings": "Price Swings", "zip": "Zip Comparison", "signals": "Signals"}
    nav_display = list(page_labels.values())
    nav_keys = list(page_labels.keys())
    active = back_page if current_page == "product" else current_page
    active_idx = nav_keys.index(active) if active in nav_keys else 0

    chosen = st.radio("", nav_display, index=active_idx, label_visibility="collapsed")
    chosen_key = nav_keys[nav_display.index(chosen)]
    if chosen_key != current_page and current_page != "product":
        nav(chosen_key)

    st.divider()
    st.caption("Data: May 10–14, 2026")
    st.caption("500 products · 10 zip codes · 96 runs")


# ════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
if current_page == "overview":
    st.markdown("# Amazon Price Intelligence")
    st.markdown("### A 96-hour study of how Amazon prices 500 products across 10 US zip codes")
    st.markdown(
        "Every hour from **May 10 to May 14, 2026**, Nimble's Web Search Agents captured a full "
        "snapshot of 500 Amazon products across 10 US zip codes — from New York to Valentine, Nebraska. "
        "That's **479,000+ data points** on prices, availability, reviews, and best-seller rankings."
    )
    st.divider()

    n_products = len(swings)
    n_zips = ph["zip_code"].nunique()
    n_runs = ph["run_number"].nunique()
    n_obs = len(ph)
    n_movers = int((swings["swing_abs"] > 0).sum())
    n_stable = n_products - n_movers
    biggest = swings.iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Products Tracked", f"{n_products:,}")
    c2.metric("Zip Codes", f"{n_zips}")
    c3.metric("Hourly Snapshots", f"{n_runs}")
    c4.metric("Total Observations", f"{n_obs:,}")

    st.markdown("")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Price Movers", f"{n_movers}", delta=f"{n_movers/n_products*100:.0f}% of catalog")
    c6.metric("Stable Products", f"{n_stable}", delta=f"{n_stable/n_products*100:.0f}% unchanged", delta_color="off")
    c7.metric("Biggest Swing", f"${biggest['swing_abs']:.2f}", delta=f"+{biggest['swing_pct']:.0f}%")
    c8.metric("Collection Window", "May 10–14", delta="96 hours, 2026")

    st.divider()
    st.markdown("#### Key Findings")
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown("**🔁 Algorithmic repricing**")
        st.markdown(r"The KN95 face mask crashed 67% — from \$24.98 to \$8.09 — six times in 96 hours. A textbook repricing bot pattern.")
        if st.button("View product →", key="kn95"):
            nav("product", "B09ND9NGTC", "swings")
    with k2:
        st.markdown("**🗺️ Pricing is overwhelmingly national**")
        st.markdown("483 of 497 products (97%) had identical prices across all 10 zip codes. The 14 exceptions were electronics and heavy goods.")
        if st.button("Explore zip comparison →", key="zip_cta"):
            nav("zip")
    with k3:
        st.markdown("**📊 67% of products never moved**")
        st.markdown("337 products held a perfectly stable price for the entire window. Movers are concentrated in electronics, consumables, and wellness.")
        if st.button("See price swings →", key="swings_cta"):
            nav("swings")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Price Distribution")
        st.caption("Mean price per product across all runs")
        fig = go.Figure(go.Histogram(x=swings["price_mean"], nbinsx=40,
                                     marker_color="#edc602", opacity=0.85))
        fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                          height=260, margin=dict(l=0,r=0,t=10,b=0),
                          xaxis=dict(title="Price ($)", gridcolor="#2a2a3e"),
                          yaxis=dict(title="# Products", gridcolor="#2a2a3e"),
                          font=dict(color="#e0e0e0"))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### Stable vs. Moving Products")
        st.caption("Whether price changed at all during the 96-hour window")
        fig2 = go.Figure(go.Pie(
            labels=["Stable (0% change)", "Price changed"],
            values=[n_stable, n_movers],
            marker_colors=["#4ab8e8", "#edc602"],
            hole=0.55, textinfo="label+percent", textfont_size=13,
        ))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#0e1117",
                           height=260, margin=dict(l=0,r=0,t=10,b=30),
                           showlegend=False, font=dict(color="#e0e0e0"))
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("#### Data Completeness")
        fill_data = {
            "Price": ph["web_price"].notna().mean(),
            "List Price": ph["list_price"].notna().mean(),
            "Availability": ph["availability"].notna().mean(),
            "Sub. & Save price": ph["subscription_price"].notna().mean(),
            "Product Title": (swings["product_title"] != "Unknown").mean(),
            "Brand": (swings["brand"] != "—").mean(),
            "BSR Category": (swings["category"] != "—").mean(),
        }
        fd = pd.DataFrame({"Field": list(fill_data.keys()), "v": [v*100 for v in fill_data.values()]}).sort_values("v")
        fig3 = go.Figure(go.Bar(
            x=fd["v"], y=fd["Field"], orientation="h",
            marker_color=["#7ec66a" if v >= 90 else "#edc602" if v >= 50 else "#e05c2a" for v in fd["v"]],
            text=[f"{v:.0f}%" for v in fd["v"]], textposition="outside",
        ))
        fig3.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                           height=260, margin=dict(l=0,r=60,t=10,b=0),
                           xaxis=dict(range=[0,115], showticklabels=False, gridcolor="#2a2a3e"),
                           yaxis=dict(title=""), font=dict(color="#e0e0e0"), showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("#### Category Breakdown")
        st.caption("Products with BSR category data")
        cat_counts = swings[swings["category"] != "—"]["category"].value_counts().head(10)
        fig4 = go.Figure(go.Bar(
            x=cat_counts.values, y=cat_counts.index, orientation="h",
            marker_color="#edc602", opacity=0.85,
        ))
        fig4.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                           height=260, margin=dict(l=0,r=0,t=10,b=0),
                           xaxis=dict(title="# Products", gridcolor="#2a2a3e"),
                           yaxis=dict(title="", autorange="reversed"),
                           font=dict(color="#e0e0e0", size=11))
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.markdown("#### Collection Timeline")
    st.caption("One snapshot per hour — 500 products × 10 zip codes each run")
    tl = ph.groupby(ph["timestamp"].dt.floor("h")).size().reset_index()
    tl.columns = ["hour", "obs"]
    fig5 = go.Figure(go.Bar(x=tl["hour"], y=tl["obs"], marker_color="#edc602", opacity=0.8))
    fig5.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                       height=160, margin=dict(l=0,r=0,t=10,b=0),
                       xaxis=dict(gridcolor="#2a2a3e"), yaxis=dict(title="Obs.", gridcolor="#2a2a3e"),
                       font=dict(color="#e0e0e0"))
    st.plotly_chart(fig5, use_container_width=True)

    st.divider()

    # ── Top 10 price swing chart ──────────────────────────────────────────────
    st.markdown("#### Top 10 Biggest Price Swings")
    st.caption("Dollar swing over the 96-hour window. Click a bar to see the full price timeline.")

    top10 = swings.sort_values("swing_abs", ascending=False).head(10).reset_index(drop=True)
    top10["short_name"] = top10["product_title"].str[:45]
    top10["label"] = top10.apply(
        lambda r: f"${r['price_min']:.2f} → ${r['price_max']:.2f}  (+{r['swing_pct']:.0f}%)", axis=1
    )

    fig_swings = go.Figure(go.Bar(
        x=top10["swing_abs"],
        y=top10["short_name"],
        orientation="h",
        marker=dict(
            color=top10["swing_pct"],
            colorscale=[[0, "#4ab8e8"], [0.4, "#edc602"], [1.0, "#e05c2a"]],
            showscale=True,
            colorbar=dict(title=dict(text="% swing", font=dict(color="#aaa")),
                         tickfont=dict(color="#aaa"), x=1.01),
        ),
        text=top10["label"],
        textposition="outside",
        textfont=dict(color="#aaa", size=11),
        customdata=top10["asin"],
        hovertemplate="<b>%{y}</b><br>Swing: $%{x:.2f}<extra></extra>",
    ))
    fig_swings.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=420, margin=dict(l=0, r=160, t=10, b=0),
        xaxis=dict(title="Price swing ($)", gridcolor="#2a2a3e"),
        yaxis=dict(title="", autorange="reversed", tickfont=dict(size=12)),
        font=dict(color="#e0e0e0"),
    )
    clicked = st.plotly_chart(fig_swings, use_container_width=True, on_select="rerun", key="top10_chart")
    if clicked and clicked.get("selection", {}).get("points"):
        pt = clicked["selection"]["points"][0]
        nav("product", top10.iloc[pt["point_index"]]["asin"], "overview")

    st.divider()

    # ── Zip gap chart ─────────────────────────────────────────────────────────
    st.markdown("#### Geographic Price Differences — All 12 Cases")
    st.caption("The only products in this dataset priced differently across zip codes.")

    zip_hl = (
        zip_gap[zip_gap["gap_abs"] > 0.01]
        .merge(meta[["asin", "product_title", "brand"]], on="asin")
        .sort_values("gap_abs", ascending=False)
        .reset_index(drop=True)
    )
    zip_hl["short_name"] = zip_hl["product_title"].str[:45]

    fig_zip = go.Figure()
    fig_zip.add_trace(go.Bar(
        name="Cheapest zip",
        x=zip_hl["short_name"],
        y=zip_hl["zip_min"],
        marker_color="#7ec66a",
        hovertemplate="<b>%{x}</b><br>Cheapest: $%{y:.2f}<extra></extra>",
    ))
    fig_zip.add_trace(go.Bar(
        name="Most expensive zip",
        x=zip_hl["short_name"],
        y=zip_hl["zip_max"],
        marker_color="#e05c2a",
        hovertemplate="<b>%{x}</b><br>Priciest: $%{y:.2f}<extra></extra>",
    ))
    fig_zip.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        barmode="group",
        height=360, margin=dict(l=0, r=0, t=10, b=120),
        xaxis=dict(title="", tickangle=-35, gridcolor="#2a2a3e", tickfont=dict(size=11)),
        yaxis=dict(title="Price ($)", gridcolor="#2a2a3e"),
        legend=dict(orientation="h", y=1.08),
        font=dict(color="#e0e0e0"),
    )
    zip_clicked = st.plotly_chart(fig_zip, use_container_width=True, on_select="rerun", key="zip_chart")
    if zip_clicked and zip_clicked.get("selection", {}).get("points"):
        pt = zip_clicked["selection"]["points"][0]
        nav("product", zip_hl.iloc[pt["point_index"]]["asin"], "overview")


# ════════════════════════════════════════════════════════════════════════════
# PRICE SWINGS
# ════════════════════════════════════════════════════════════════════════════
elif current_page == "swings":
    st.markdown("# Price Swings")
    st.markdown("All 500 products ranked by price movement across the 96-hour window. **Click any row** to see the full timeline.")

    # Top 30 movers — dumbbell chart (min → max price range)
    top30 = swings.sort_values("swing_abs", ascending=False).head(30).reset_index(drop=True)
    top30["short_name"] = top30["product_title"].str[:42]

    # Color each product by % swing
    def swing_color(pct):
        if pct < 20:   return "#4ab8e8"
        if pct < 60:   return "#edc602"
        return "#e05c2a"

    movers_fig = go.Figure()

    # Connecting lines (min to max)
    for _, row in top30.iterrows():
        movers_fig.add_trace(go.Scatter(
            x=[row["price_min"], row["price_max"]],
            y=[row["short_name"], row["short_name"]],
            mode="lines",
            line=dict(color=swing_color(row["swing_pct"]), width=3),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Min price dots
    movers_fig.add_trace(go.Scatter(
        x=top30["price_min"],
        y=top30["short_name"],
        mode="markers",
        name="Low price",
        marker=dict(color="#4ab8e8", size=10, symbol="circle"),
        customdata=top30[["asin", "swing_pct", "price_min", "price_max"]].values,
        hovertemplate="<b>%{y}</b><br>Low: $%{x:.2f}<br>Swing: +%{customdata[1]:.0f}%<extra></extra>",
    ))

    # Max price dots
    movers_fig.add_trace(go.Scatter(
        x=top30["price_max"],
        y=top30["short_name"],
        mode="markers",
        name="High price",
        marker=dict(color="#e05c2a", size=10, symbol="circle"),
        customdata=top30[["asin", "swing_pct", "price_min", "price_max"]].values,
        hovertemplate="<b>%{y}</b><br>High: $%{x:.2f}<br>Swing: +%{customdata[1]:.0f}%<extra></extra>",
    ))

    movers_fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=620, margin=dict(l=0, r=20, t=10, b=0),
        xaxis=dict(title="Price ($)", gridcolor="#2a2a3e"),
        yaxis=dict(title="", autorange="reversed", tickfont=dict(size=12)),
        legend=dict(orientation="h", y=1.04, x=0),
        font=dict(color="#e0e0e0"),
    )
    chart_click = st.plotly_chart(movers_fig, use_container_width=True, on_select="rerun", key="swings_chart")
    if chart_click and chart_click.get("selection", {}).get("points"):
        pt = chart_click["selection"]["points"][0]
        idx = pt.get("point_index")
        if idx is not None and idx < len(top30):
            nav("product", top30.iloc[idx]["asin"], "swings")

    st.divider()
    st.markdown("#### All products — click any row to explore")

    sort_map = {
        "Absolute change ($)": ("swing_abs", False),
        "% change": ("swing_pct", False),
        "Price — high to low": ("price_mean", False),
        "Price — low to high": ("price_mean", True),
    }
    sort_choice = st.radio("Sort by", list(sort_map.keys()), horizontal=True)
    sort_col, asc = sort_map[sort_choice]
    display = swings.sort_values(sort_col, ascending=asc).reset_index(drop=True)

    content = nft_header([
        ("Product", 4, "left"), ("Brand", 1.5, "left"), ("Category", 1.5, "left"),
        ("Min", 1, "right"), ("Max", 1, "right"), ("Swing $", 1, "right"), ("Swing %", 1, "right"),
    ])
    for _, row in display.iterrows():
        swing = row["swing_abs"]
        cls = "pos" if swing > 0 else "zero"
        content += nft_row(f"?asin={row['asin']}&from=swings", [
            (html.escape(str(row["product_title"])[:70]), 4, "pname", "left"),
            (html.escape(str(row["brand"])), 1.5, "brand", "left"),
            (html.escape(str(row["category"])), 1.5, "cat", "left"),
            (f"${row['price_min']:.2f}", 1, "", "right"),
            (f"${row['price_max']:.2f}", 1, "", "right"),
            (f"${swing:.2f}", 1, cls, "right"),
            (f"{row['swing_pct']:.1f}%", 1, cls, "right"),
        ])
    nft_render(content, height=640)


# ════════════════════════════════════════════════════════════════════════════
# ZIP COMPARISON
# ════════════════════════════════════════════════════════════════════════════
elif current_page == "zip":
    st.markdown("# Zip Code Comparison")
    st.markdown(
        "Does where you shop on Amazon affect what you pay? "
        "We checked the same 500 products across 10 US zip codes — from New York to rural Nebraska."
    )

    n_with_gap = int((zip_gap["gap_abs"] > 0.01).sum())
    n_zero = int((zip_gap["gap_abs"] == 0).sum())

    zc1, zc2, zc3 = st.columns(3)
    zc1.metric("Uniform national pricing", f"{n_zero} / {len(zip_gap)}", delta="97% of catalog", delta_color="off")
    zc2.metric("Products with a geographic gap", f"{n_with_gap}")
    zc3.metric("Largest gap found", f"${zip_gap['gap_abs'].max():.2f}")

    st.info("**Amazon prices are nearly uniform across the US.** 97% of products cost the same whether you shop from New York or Valentine, Nebraska. The 12 exceptions are electronics and heavy goods — likely logistics costs, not Amazon's own pricing engine.")
    st.divider()

    st.markdown("#### Products with geographic price differences")
    st.markdown("**Click a row** to see the full price timeline for that product.")

    with_gap = (
        zip_gap[zip_gap["gap_abs"] > 0.01]
        .merge(meta[["asin", "product_title", "brand"]], on="asin")
        .sort_values("gap_abs", ascending=False)
    )

    content = nft_header([
        ("Product", 4, "left"), ("Brand", 1.5, "left"),
        ("Cheapest", 1, "right"), ("Most Expensive", 1.5, "right"),
        ("Gap $", 1, "right"), ("Gap %", 1, "right"),
    ])
    for _, row in with_gap.iterrows():
        content += nft_row(f"?asin={row['asin']}&from=zip", [
            (html.escape(str(row["product_title"])[:70]), 4, "pname", "left"),
            (html.escape(str(row["brand"])), 1.5, "brand", "left"),
            (f"${row['zip_min']:.2f}", 1, "green", "right"),
            (f"${row['zip_max']:.2f}", 1.5, "red", "right"),
            (f"${row['gap_abs']:.2f}", 1, "pos", "right"),
            (f"{row['gap_pct']:.1f}%", 1, "pos", "right"),
        ])
    nft_render(content, height=400)

    st.divider()
    st.markdown("#### Look up any product")
    st.caption("Select a product to see its median price across all 10 zip codes.")

    all_zip = (
        zip_gap.merge(meta[["asin", "product_title", "brand"]], on="asin")
        .sort_values("gap_abs", ascending=False)
    )
    chosen_label = st.selectbox(
        "Product",
        all_zip["product_title"].str[:70].tolist(),
        label_visibility="collapsed",
    )
    chosen_asin = all_zip[all_zip["product_title"].str[:70] == chosen_label]["asin"].iloc[0]
    chosen_row = all_zip[all_zip["asin"] == chosen_asin].iloc[0]

    zm1, zm2, zm3 = st.columns(3)
    zm1.metric("Cheapest zip", f"${chosen_row['zip_min']:.2f}")
    zm2.metric("Most expensive zip", f"${chosen_row['zip_max']:.2f}")
    zm3.metric("Gap", f"${chosen_row['gap_abs']:.2f}", delta=f"{chosen_row['gap_pct']:.1f}%")

    asin_zips = zip_stats[zip_stats["asin"] == chosen_asin].sort_values("price_median").copy()
    bar_colors = [
        "#7ec66a" if i == 0 else ("#e05c2a" if i == len(asin_zips)-1 else "#4ab8e8")
        for i in range(len(asin_zips))
    ]
    bar_fig = go.Figure(go.Bar(
        x=asin_zips["zip_label"], y=asin_zips["price_median"],
        marker_color=bar_colors,
        text=asin_zips["price_median"].map("${:.2f}".format),
        textposition="outside",
    ))
    bar_fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=320, margin=dict(l=0,r=0,t=10,b=0),
        xaxis=dict(title="", gridcolor="#2a2a3e"),
        yaxis=dict(title="Median Price ($)", gridcolor="#2a2a3e",
                   range=[asin_zips["price_median"].min()*0.93,
                          asin_zips["price_median"].max()*1.12]),
        font=dict(color="#e0e0e0"), showlegend=False,
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    if st.button("View full price timeline →", type="primary"):
        nav("product", chosen_asin, "zip")


# ════════════════════════════════════════════════════════════════════════════
# SIGNALS & EVENTS
# ════════════════════════════════════════════════════════════════════════════
elif current_page == "signals":
    st.markdown("# Signals & Events")
    st.markdown(
        "Every non-price change detected across 500 products during the 96-hour window — "
        "title A/B tests, stock-outs, MSRP adjustments, and multi-signal cascades."
    )

    if len(sig_hist) == 0:
        st.warning("Signal data not yet generated. Run `python3 phase4_process.py` first.")
        st.stop()

    # ── Derived summaries ─────────────────────────────────────────────────────
    n_title_asins = title_chg["asin"].nunique() if len(title_chg) > 0 else 0
    n_oos_asins   = int((oos_sum["oos_rate"] > 0).sum()) if len(oos_sum) > 0 else 0
    msrp_chg = (
        sig_hist.dropna(subset=["list_price"])
        .groupby("asin").agg(lp_min=("list_price","min"), lp_max=("list_price","max"), lp_n=("list_price","nunique"))
        .reset_index()
    )
    msrp_chg["delta"] = msrp_chg["lp_max"] - msrp_chg["lp_min"]
    msrp_chg["pct"]   = (msrp_chg["delta"] / msrp_chg["lp_min"] * 100).round(1)
    msrp_chg = (
        msrp_chg[msrp_chg["delta"] > 0.50]
        .merge(meta[["asin","product_title","brand"]], on="asin")
        .sort_values("delta", ascending=False)
    )
    n_msrp        = len(msrp_chg)
    n_alert_events = len(sig_alerts)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Title A/B Tests", f"{n_title_asins}", delta="products testing titles live")
    s2.metric("Went Out of Stock", f"{n_oos_asins}", delta="products, any zip", delta_color="inverse")
    s3.metric("MSRP Changed", f"{n_msrp}", delta="list price adjustments")
    s4.metric("Multi-signal Events", f"{n_alert_events:,}", delta=f"{sig_alerts['asin'].nunique() if n_alert_events else 0} products")

    st.divider()

    # ── Availability heatmap ──────────────────────────────────────────────────
    st.markdown("#### Products That Went Out of Stock")
    st.caption("358 of 500 products had at least one zip go unavailable. Top 20 by OOS rate. Green = all zips available · Orange = some zips OOS · Red = fully OOS.")

    top_oos = oos_sum[oos_sum["oos_rate"] > 0].head(20).copy()
    heat_asins = top_oos["asin"].tolist()
    heat = (
        sig_hist[sig_hist["asin"].isin(heat_asins)]
        .merge(top_oos[["asin","oos_rate"]], on="asin", how="left")
        .copy()
    )
    heat["short_name"] = heat.apply(
        lambda r: (str(r["product_title"] or r["asin"])[:38]) + f" ({r['oos_rate']:.0f}% OOS)", axis=1
    )
    name_order = (
        heat.groupby(["asin","short_name"])["oos_rate"].first()
        .reset_index().sort_values("oos_rate", ascending=False)["short_name"].tolist()
    )
    heat_pivot = (
        heat.pivot_table(index="short_name", columns="run_number", values="n_available_zips", aggfunc="first")
        .fillna(10).reindex(name_order)
    )
    heatmap_fig = go.Figure(go.Heatmap(
        z=heat_pivot.values,
        x=list(heat_pivot.columns),
        y=list(heat_pivot.index),
        colorscale=[[0,"#e05c2a"],[0.05,"#e05c2a"],[0.4,"#edc602"],[1.0,"#7ec66a"]],
        zmin=0, zmax=10,
        hovertemplate="Run %{x}<br>%{y}<br>%{z}/10 zips available<extra></extra>",
        colorbar=dict(title=dict(text="Zips avail.", font=dict(color="#aaa")),
                     tickvals=[0,5,10], tickfont=dict(color="#aaa")),
    ))
    heatmap_fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=max(260, len(name_order) * 24 + 60),
        margin=dict(l=0, r=60, t=10, b=0),
        xaxis=dict(title="Run number", gridcolor="#2a2a3e", dtick=12),
        yaxis=dict(tickfont=dict(size=11)),
        font=dict(color="#e0e0e0"),
    )
    st.plotly_chart(heatmap_fig, use_container_width=True)

    oos_content = nft_header([
        ("Product", 4, "left"), ("Brand", 1.5, "left"),
        ("OOS Rate", 1, "right"), ("OOS / Total", 1.2, "right"), ("Last status", 1.2, "right"),
    ])
    for _, row in top_oos.iterrows():
        last_run = sig_hist[sig_hist["asin"] == row["asin"]].sort_values("run_number").iloc[-1]
        status = "OOS" if not last_run["is_available"] else "Available"
        sc = "red" if status == "OOS" else "green"
        oos_content += nft_row(f"?asin={row['asin']}&from=signals", [
            (html.escape(str(row["product_title"])[:70]), 4, "pname", "left"),
            (html.escape(str(row["brand"])), 1.5, "brand", "left"),
            (f"{row['oos_rate']:.1f}%", 1, "red" if row["oos_rate"] > 50 else "pos", "right"),
            (f"{int(row['oos_runs'])}/{int(row['total_runs'])}", 1.2, "cat", "right"),
            (status, 1.2, sc, "right"),
        ])
    nft_render(oos_content, height=380)

    st.divider()

    # ── Title A/B tests ───────────────────────────────────────────────────────
    st.markdown("#### Live Title A/B Testing")
    st.caption(
        "11 products served two different titles, alternating every few hours throughout the window. "
        "Every change is a keyword injection test — the BSR data shows which version ranks better."
    )

    if len(title_chg) > 0:
        for asin_tc, grp in title_chg.groupby("asin"):
            title_a = grp["old_title"].iloc[0]
            title_b = grp["new_title"].iloc[0]
            n_sw    = len(grp)
            prod_sig = sig_hist[sig_hist["asin"] == asin_tc].copy()
            prod_sig["t_clean"] = prod_sig["product_title"].astype(str).str.strip()
            bsr_a = prod_sig[prod_sig["t_clean"] == title_a.strip()]["bsr_rank"].median()
            bsr_b = prod_sig[prod_sig["t_clean"] == title_b.strip()]["bsr_rank"].median()
            brand_val = grp["brand"].iloc[0] if "brand" in grp.columns else "—"

            label = f"**{html.escape(str(title_a)[:70])}** — {n_sw} switches detected"
            with st.expander(label):
                ca, cb = st.columns(2)
                with ca:
                    st.markdown("**Version A**")
                    st.markdown(f"_{html.escape(str(title_a))}_")
                    if pd.notna(bsr_a):
                        st.metric("Median BSR", f"#{int(bsr_a):,}")
                with cb:
                    st.markdown("**Version B**")
                    st.markdown(f"_{html.escape(str(title_b))}_")
                    if pd.notna(bsr_b):
                        st.metric("Median BSR", f"#{int(bsr_b):,}")
                if pd.notna(bsr_a) and pd.notna(bsr_b) and bsr_a != bsr_b:
                    winner = "A" if bsr_a < bsr_b else "B"
                    delta  = abs(int(bsr_a) - int(bsr_b))
                    st.caption(f"Version {winner} ranks better by {delta:,} BSR positions")
                if st.button("View full timeline →", key=f"tc_{asin_tc}"):
                    nav("product", asin_tc, "signals")

    st.divider()

    # ── MSRP changes ─────────────────────────────────────────────────────────
    st.markdown("#### MSRP Changes")
    st.caption(f"{n_msrp} products had their Amazon list price adjusted — separate from and often larger than the web price movement.")

    msrp_content = nft_header([
        ("Product", 4, "left"), ("Brand", 1.5, "left"),
        ("From", 1, "right"), ("To", 1, "right"),
        ("Change", 1, "right"), ("Change %", 1, "right"), ("# Variants", 1, "right"),
    ])
    for _, row in msrp_chg.iterrows():
        cls = "red" if row["delta"] > 10 else "pos"
        msrp_content += nft_row(f"?asin={row['asin']}&from=signals", [
            (html.escape(str(row["product_title"])[:70]), 4, "pname", "left"),
            (html.escape(str(row["brand"])), 1.5, "brand", "left"),
            (f"&#36;{row['lp_min']:.2f}", 1, "", "right"),
            (f"&#36;{row['lp_max']:.2f}", 1, cls, "right"),
            (f"+&#36;{row['delta']:.2f}", 1, cls, "right"),
            (f"+{row['pct']:.1f}%", 1, cls, "right"),
            (str(int(row["lp_n"])), 1, "cat", "right"),
        ])
    nft_render(msrp_content, height=520)

    st.divider()

    # ── Multi-signal events ───────────────────────────────────────────────────
    st.markdown("#### Multi-Signal Events")
    st.caption("Run transitions where 2+ independent signals changed simultaneously. Higher signal count = more unusual event.")

    if len(sig_alerts) > 0:
        top_ev = sig_alerts.sort_values(["n_signals","asin","run_number"], ascending=[False,True,True]).head(60)
        ev_content = nft_header([
            ("Product", 3, "left"), ("Brand", 1.2, "left"),
            ("When", 1.2, "left"), ("Signals", 0.8, "right"), ("What changed", 4, "left"),
        ])
        for _, row in top_ev.iterrows():
            ts_str = pd.to_datetime(row["timestamp"]).strftime("%b %d %H:%M")
            # signals text was pre-encoded in phase4 — skip html.escape to avoid double-encoding
            signals_txt = str(row["signals"])[:90]
            ev_content += nft_row(f"?asin={row['asin']}&from=signals", [
                (html.escape(str(row.get("product_title",""))[:55]), 3, "pname", "left"),
                (html.escape(str(row.get("brand","—"))), 1.2, "brand", "left"),
                (ts_str, 1.2, "cat", "left"),
                (str(int(row["n_signals"])), 0.8, "pos" if int(row["n_signals"]) >= 3 else "", "right"),
                (signals_txt, 4, "cat", "left"),
            ])
        nft_render(ev_content, height=520)


# ════════════════════════════════════════════════════════════════════════════
# PRODUCT DETAIL
# ════════════════════════════════════════════════════════════════════════════
elif current_page == "product":
    asin = query_asin
    swing_row = swings[swings["asin"] == asin]
    meta_row = meta[meta["asin"] == asin]

    if swing_row.empty or meta_row.empty:
        st.error("Product not found.")
        st.stop()

    swing_row = swing_row.iloc[0]
    meta_row = meta_row.iloc[0]

    st.markdown(f"# {meta_row['product_title']}")

    brand = str(meta_row.get("brand") or swing_row.get("brand") or "—")
    cat = str(swing_row.get("category") or "—")
    st.markdown(f"**Brand:** {brand} &nbsp;&nbsp; **Category:** {cat}")

    rating = meta_row.get("average_of_reviews")
    n_rev = meta_row.get("number_of_reviews")
    bsr_name = meta_row.get("best_sellers_category_1_name")
    bsr_rank = meta_row.get("best_sellers_category_1_rank")
    if pd.notna(rating):
        stars = "★" * int(round(float(rating))) + "☆" * (5 - int(round(float(rating))))
        rev_str = f"— {int(n_rev):,} reviews" if pd.notna(n_rev) else ""
        st.markdown(f"**{float(rating):.1f}** {stars} {rev_str}")
    if pd.notna(bsr_name) and pd.notna(bsr_rank):
        st.markdown(f"**Best Seller Rank:** #{int(bsr_rank):,} in {bsr_name}")

    p1, p2, p3 = st.columns(3)
    p1.metric("Low", f"${swing_row['price_min']:.2f}")
    p2.metric("High", f"${swing_row['price_max']:.2f}")
    p3.metric("Swing", f"${swing_row['swing_abs']:.2f}", delta=f"+{swing_row['swing_pct']:.1f}%")

    if asin in STORY_CALLOUTS:
        st.info(STORY_CALLOUTS[asin])

    st.divider()

    st.markdown("#### Price over time")
    product_ph = ph[ph["asin"] == asin].sort_values("timestamp")
    line_fig = go.Figure()
    for i, (zip_code, grp) in enumerate(product_ph.groupby("zip_code")):
        run_med = grp.groupby("timestamp")["web_price"].median().reset_index()
        line_fig.add_trace(go.Scatter(
            x=run_med["timestamp"], y=run_med["web_price"],
            mode="lines+markers",
            name=ZIP_LABELS.get(zip_code, zip_code),
            line=dict(color=ZIP_COLORS[i % len(ZIP_COLORS)], width=2),
            marker=dict(size=4),
        ))
    line_fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=380, margin=dict(l=0,r=0,t=10,b=0),
        xaxis=dict(title="", gridcolor="#2a2a3e"),
        yaxis=dict(title="Price ($)", gridcolor="#2a2a3e"),
        legend=dict(orientation="h", y=-0.22),
        font=dict(color="#e0e0e0"),
    )
    st.plotly_chart(line_fig, use_container_width=True)

    st.markdown("#### Median price by zip code")
    asin_zips = zip_stats[zip_stats["asin"] == asin].sort_values("price_median").copy()
    bar_colors = [
        "#7ec66a" if i == 0 else ("#e05c2a" if i == len(asin_zips)-1 else "#4ab8e8")
        for i in range(len(asin_zips))
    ]
    bar_fig = go.Figure(go.Bar(
        x=asin_zips["zip_label"], y=asin_zips["price_median"],
        marker_color=bar_colors,
        text=asin_zips["price_median"].map("${:.2f}".format),
        textposition="outside",
    ))
    bar_fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=300, margin=dict(l=0,r=0,t=10,b=0),
        xaxis=dict(title="", gridcolor="#2a2a3e"),
        yaxis=dict(title="Median Price ($)", gridcolor="#2a2a3e",
                   range=[asin_zips["price_median"].min()*0.93,
                          asin_zips["price_median"].max()*1.12]),
        font=dict(color="#e0e0e0"), showlegend=False,
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    if len(sig_hist) > 0:
        prod_sig = sig_hist[sig_hist["asin"] == asin].sort_values("run_number")

        # ── BSR trend ─────────────────────────────────────────────────────────
        bsr_data = prod_sig.dropna(subset=["bsr_rank"])
        if len(bsr_data) > 1:
            st.divider()
            bsr_cat = bsr_data["bsr_name"].dropna().iloc[0] if bsr_data["bsr_name"].notna().any() else ""
            st.markdown("#### Best Seller Rank")
            if bsr_cat:
                st.caption(f"Category: {bsr_cat} — inverted axis: lower rank = better position")
            bsr_fig = go.Figure()
            bsr_fig.add_trace(go.Scatter(
                x=bsr_data["timestamp"], y=bsr_data["bsr_rank"],
                mode="lines+markers",
                line=dict(color="#edc602", width=2),
                marker=dict(size=4),
                hovertemplate="#%{y:,}<br>%{x|%b %d %H:%M}<extra></extra>",
            ))
            if len(title_chg) > 0:
                prod_tc = title_chg[title_chg["asin"] == asin]
                seen_ts = set()
                for _, tc_row in prod_tc.iterrows():
                    tc_ts_rows = sig_hist[
                        (sig_hist["asin"] == asin) & (sig_hist["run_number"] == tc_row["run_number"])
                    ]["timestamp"]
                    if len(tc_ts_rows) > 0:
                        ts_val = tc_ts_rows.iloc[0]
                        if ts_val not in seen_ts:
                            seen_ts.add(ts_val)
                            bsr_fig.add_vline(
                                x=ts_val, line=dict(color="#e05c2a", width=1, dash="dot"),
                                annotation_text="title", annotation_position="top",
                                annotation_font=dict(color="#e05c2a", size=9),
                            )
            bsr_fig.update_layout(
                template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                height=280, margin=dict(l=0, r=0, t=20, b=0),
                xaxis=dict(title="", gridcolor="#2a2a3e"),
                yaxis=dict(title="Rank (lower = better)", gridcolor="#2a2a3e", autorange="reversed"),
                font=dict(color="#e0e0e0"),
            )
            st.plotly_chart(bsr_fig, use_container_width=True)

        # ── Availability timeline ──────────────────────────────────────────────
        n_oos_runs = int((~prod_sig["is_available"]).sum())
        if n_oos_runs > 0:
            st.divider()
            oos_pct = int(n_oos_runs / len(prod_sig) * 100)
            st.markdown("#### Availability")
            st.caption(f"Out of stock in {oos_pct}% of runs ({n_oos_runs}/{len(prod_sig)}). Green = available · Red = fully OOS.")
            colors = ["#e05c2a" if not a else "#7ec66a" for a in prod_sig["is_available"]]
            avail_fig = go.Figure(go.Bar(
                x=prod_sig["timestamp"], y=[1] * len(prod_sig),
                marker_color=colors, bargap=0.05,
                hovertemplate="%{x|%b %d %H:%M}<br>%{customdata}<extra></extra>",
                customdata=["Available" if a else "Out of Stock" for a in prod_sig["is_available"]],
            ))
            avail_fig.update_layout(
                template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                height=72, margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[0, 1.2]),
            )
            st.plotly_chart(avail_fig, use_container_width=True)

        # ── MSRP history ───────────────────────────────────────────────────────
        msrp_ts = prod_sig.dropna(subset=["list_price"])
        if len(msrp_ts) > 1:
            lp_min = msrp_ts["list_price"].min()
            lp_max = msrp_ts["list_price"].max()
            if lp_max - lp_min > 0.50:
                st.divider()
                n_lp_vals = msrp_ts["list_price"].nunique()
                st.markdown("#### MSRP History")
                st.caption(f"List price changed across {n_lp_vals} distinct values over the study window")
                msrp_fig = go.Figure(go.Scatter(
                    x=msrp_ts["timestamp"], y=msrp_ts["list_price"],
                    mode="lines+markers",
                    line=dict(color="#c97de0", width=2, shape="hv"),
                    marker=dict(size=6, color="#c97de0"),
                    hovertemplate="&#36;%{y:.2f}<br>%{x|%b %d %H:%M}<extra></extra>",
                ))
                msrp_fig.update_layout(
                    template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    height=220, margin=dict(l=0, r=0, t=10, b=0),
                    xaxis=dict(title="", gridcolor="#2a2a3e"),
                    yaxis=dict(title="List Price", gridcolor="#2a2a3e",
                               range=[lp_min * 0.9, lp_max * 1.1]),
                    font=dict(color="#e0e0e0"),
                )
                st.plotly_chart(msrp_fig, use_container_width=True)
