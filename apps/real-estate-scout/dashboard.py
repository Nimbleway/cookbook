import streamlit as st
import pandas as pd
import json
import re
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Real Estate Investment Scout",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #2d3347; }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px 8px 0 0;
        padding: 8px 24px;
        font-weight: 600;
        font-size: 14px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #edc602 !important;
        color: #0e1117 !important;
    }

    /* City cards */
    .city-card {
        background: linear-gradient(135deg, #1a1f2e, #252a3d);
        border: 1px solid #2d3347;
        border-left: 4px solid #edc602;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .rank-badge {
        background-color: #edc602;
        color: #0e1117;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 13px;
        margin-right: 8px;
    }
    .nimble-yellow { color: #edc602; }
    hr { border-color: #2d3347; }
</style>
""", unsafe_allow_html=True)


# --- City coordinates (for national map) ---
CITY_COORDS = {
    ("San Francisco", "CA"): (37.7749, -122.4194),
    ("Chicago", "IL"): (41.8781, -87.6298),
    ("Oakland", "CA"): (37.8044, -122.2712),
    ("Flagstaff", "AZ"): (35.1983, -111.6513),
    ("Rochester", "NY"): (43.1566, -77.6088),
    ("Columbus", "OH"): (39.9612, -82.9988),
    ("Kansas City", "MO"): (39.0997, -94.5786),
    ("Philadelphia", "PA"): (39.9526, -75.1652),
    ("Virginia Beach", "VA"): (36.8529, -75.9780),
    ("Tacoma", "WA"): (47.2529, -122.4443),
    ("Anchorage", "AK"): (61.2181, -149.9003),
    ("Reno", "NV"): (39.5296, -119.8138),
    ("Buffalo", "NY"): (42.8864, -78.8784),
    ("Louisville", "KY"): (38.2527, -85.7585),
    ("Worcester", "MA"): (42.2626, -71.8023),
    ("Stamford", "CT"): (41.0534, -73.5387),
    ("St Louis", "MO"): (38.6270, -90.1994),
    ("Charlotte", "NC"): (35.2271, -80.8431),
    ("Richmond", "VA"): (37.5407, -77.4360),
    ("Boise", "ID"): (43.6150, -116.2023),
    ("Albuquerque", "NM"): (35.0844, -106.6504),
    ("Phoenix", "AZ"): (33.4484, -112.0740),
    ("New York", "NY"): (40.7128, -74.0060),
    ("Providence", "RI"): (41.8240, -71.4128),
    ("Indianapolis", "IN"): (39.7684, -86.1581),
    ("Madison", "WI"): (43.0731, -89.4012),
    ("Minneapolis", "MN"): (44.9778, -93.2650),
    ("Omaha", "NE"): (41.2565, -95.9345),
    ("Houston", "TX"): (29.7604, -95.3698),
    ("Dallas", "TX"): (32.7767, -96.7970),
    ("Portland", "OR"): (45.5051, -122.6750),
    ("Little Rock", "AR"): (34.7465, -92.2896),
    ("San Jose", "CA"): (37.3382, -121.8863),
    ("Los Angeles", "CA"): (34.0522, -118.2437),
    ("Baltimore", "MD"): (39.2904, -76.6122),
    ("Birmingham", "AL"): (33.5186, -86.8104),
    ("Knoxville", "TN"): (35.9606, -83.9207),
    ("Cincinnati", "OH"): (39.1031, -84.5120),
    ("El Paso", "TX"): (31.7619, -106.4850),
    ("Denver", "CO"): (39.7392, -104.9903),
    ("Salt Lake City", "UT"): (40.7608, -111.8910),
    ("Boston", "MA"): (42.3601, -71.0589),
    ("Sioux Falls", "SD"): (43.5446, -96.7311),
    ("Fort Worth", "TX"): (32.7555, -97.3308),
    ("Nashville", "TN"): (36.1627, -86.7816),
    ("Oklahoma City", "OK"): (35.4676, -97.5164),
    ("Milwaukee", "WI"): (43.0389, -87.9065),
    ("Tulsa", "OK"): (36.1540, -95.9928),
    ("Seattle", "WA"): (47.6062, -122.3321),
    ("Sacramento", "CA"): (38.5816, -121.4944),
    ("Jacksonville", "FL"): (30.3322, -81.6557),
    ("Des Moines", "IA"): (41.5868, -93.6250),
    ("Eugene", "OR"): (44.0521, -123.0868),
    ("San Diego", "CA"): (32.7157, -117.1611),
    ("Portland", "ME"): (43.6591, -70.2568),
    ("Raleigh", "NC"): (35.7796, -78.6382),
    ("Fresno", "CA"): (36.7378, -119.7871),
    ("Fort Collins", "CO"): (40.5853, -105.0844),
    ("Atlanta", "GA"): (33.7490, -84.3880),
    ("San Antonio", "TX"): (29.4241, -98.4936),
    ("Detroit", "MI"): (42.3314, -83.0458),
    ("Fort Lauderdale", "FL"): (26.1224, -80.1373),
    ("Colorado Springs", "CO"): (38.8339, -104.8214),
    ("Riverside", "CA"): (33.9806, -117.3755),
    ("Scottsdale", "AZ"): (33.4942, -111.9261),
    ("Mesa", "AZ"): (33.4152, -111.8315),
    ("Gilbert", "AZ"): (33.3528, -111.7890),
    ("Las Vegas", "NV"): (36.1699, -115.1398),
    ("Charleston", "SC"): (32.7765, -79.9311),
    ("Chattanooga", "TN"): (35.0456, -85.3097),
    ("Memphis", "TN"): (35.1495, -90.0490),
    ("Austin", "TX"): (30.2672, -97.7431),
    ("Salem", "OR"): (44.9429, -123.0351),
    ("Chandler", "AZ"): (33.3062, -111.8413),
    ("Henderson", "NV"): (36.0395, -114.9817),
    ("Pittsburgh", "PA"): (40.4406, -79.9959),
    ("Plano", "TX"): (33.0198, -96.6989),
    ("Tucson", "AZ"): (32.2226, -110.9747),
    ("Savannah", "GA"): (32.0835, -81.0998),
    ("Baton Rouge", "LA"): (30.4515, -91.1871),
    ("Frisco", "TX"): (33.1507, -96.8236),
    ("Palm Springs", "CA"): (33.8303, -116.5453),
    ("Manhattan", "NY"): (40.7831, -73.9712),
    ("Tampa", "FL"): (27.9506, -82.4572),
    ("Orlando", "FL"): (28.5383, -81.3792),
    ("Cape Coral", "FL"): (26.5629, -81.9495),
    ("Washington DC", "DC"): (38.9072, -77.0369),
    ("New Orleans", "LA"): (29.9511, -90.0715),
    ("Irvine", "CA"): (33.6846, -117.8265),
    ("Sarasota", "FL"): (27.3364, -82.5307),
    ("Bend", "OR"): (44.0582, -121.3153),
    ("Honolulu", "HI"): (21.3069, -157.8583),
    ("Santa Fe", "NM"): (35.6870, -105.9378),
    ("Myrtle Beach", "SC"): (33.6891, -78.8867),
    ("Fort Myers", "FL"): (26.6406, -81.8723),
    ("Boca Raton", "FL"): (26.3683, -80.1289),
    ("West Palm Beach", "FL"): (26.7153, -80.0534),
    ("Naples", "FL"): (26.1420, -81.7948),
    ("Boulder", "CO"): (40.0150, -105.2705),
    ("Miami", "FL"): (25.7617, -80.1918),
}

# Market slug → (city, state) for Zillow filename parsing
SLUG_TO_MARKET = {
    "kansas_city": ("Kansas City", "MO"),
    "san_francisco": ("San Francisco", "CA"),
    "virginia_beach": ("Virginia Beach", "VA"),
    "albuquerque": ("Albuquerque", "NM"),
    "columbus": ("Columbus", "OH"),
    "philadelphia": ("Philadelphia", "PA"),
    "chicago": ("Chicago", "IL"),
    "tacoma": ("Tacoma", "WA"),
    "dallas": ("Dallas", "TX"),
    "reno": ("Reno", "NV"),
}

CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"


# --- Data loading ---

@st.cache_data
def load_data():
    top10 = json.loads(Path("data/top10_cities.json").read_text())
    all_cities = json.loads(Path("data/all_cities_scored.json").read_text())
    reports_raw = json.loads(Path("data/perplexity_reports.json").read_text())

    df_all = pd.DataFrame(all_cities)
    df_all["lat"] = df_all.apply(
        lambda r: CITY_COORDS.get((r["city"], r["state"]), (None, None))[0], axis=1
    )
    df_all["lon"] = df_all.apply(
        lambda r: CITY_COORDS.get((r["city"], r["state"]), (None, None))[1], axis=1
    )
    df_all["homes_sold"] = pd.to_numeric(df_all["homes_sold"], errors="coerce").fillna(50)
    df_all["is_top10"] = df_all.apply(
        lambda r: any(t["city"] == r["city"] and t["state"] == r["state"] for t in top10), axis=1
    )

    reports_dict = {(r["city"], r["state"]): r["report"] for r in reports_raw}

    # Load Zillow listings — sorted slugs longest-first for correct prefix matching
    slugs_sorted = sorted(SLUG_TO_MARKET.keys(), key=len, reverse=True)
    listings = []
    for f in sorted(Path("data/raw/zillow").glob("*.json")):
        raw = json.loads(f.read_text())
        items = raw.get("data", {}).get("parsing", [])
        if not items:
            continue
        stem = f.stem
        market_city, market_state = None, None
        for slug in slugs_sorted:
            if stem.startswith(slug):
                market_city, market_state = SLUG_TO_MARKET[slug]
                break
        for item in items:
            item["market_city"] = market_city
            item["market_state"] = market_state
            listings.append(item)

    df_listings = pd.DataFrame(listings)
    df_listings["latitude"] = pd.to_numeric(df_listings["latitude"], errors="coerce")
    df_listings["longitude"] = pd.to_numeric(df_listings["longitude"], errors="coerce")
    df_listings["price"] = pd.to_numeric(df_listings["price"], errors="coerce")
    df_listings["bedrooms"] = pd.to_numeric(df_listings["bedrooms"], errors="coerce")
    df_listings["bathrooms"] = pd.to_numeric(df_listings["bathrooms"], errors="coerce")
    df_listings["living_area_in_sqft"] = pd.to_numeric(df_listings["living_area_in_sqft"], errors="coerce")
    df_listings["days_on_zillow"] = pd.to_numeric(df_listings["days_on_zillow"], errors="coerce")
    df_listings["first_image"] = df_listings["images"].apply(
        lambda imgs: imgs[0] if isinstance(imgs, list) and imgs else None
    )

    return top10, df_all, reports_dict, df_listings


top10, df_all, reports_dict, df_listings = load_data()
top10_df = pd.DataFrame(top10)


# --- Helpers ---

def fmt_price(p):
    if p is None or pd.isna(p):
        return "N/A"
    if p >= 1_000_000:
        return f"${p/1_000_000:.1f}M"
    return f"${p/1_000:.0f}K"


def price_color(price):
    if pd.isna(price):
        return [128, 128, 128, 150]
    elif price < 300_000:
        return [0, 200, 100, 210]
    elif price < 700_000:
        return [237, 198, 2, 210]
    elif price < 1_500_000:
        return [255, 100, 40, 210]
    else:
        return [180, 80, 255, 210]


def format_report(text):
    # Period or colon immediately followed by a capital letter (no space)
    text = re.sub(r'\.([A-Z])', r'.\n\n\1', text)
    text = re.sub(r':([A-Z])', r':\n\n\1', text)
    # Lowercase letter immediately followed by a capital — concatenated section headers
    # e.g. "topicAppreciation", "demandDemand", "risksInventory"
    text = re.sub(r'([a-z])([A-Z])', r'\1\n\n\2', text)
    # Collapse any triple+ newlines to double
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_series(s, invert=False):
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series([0.5] * len(s), index=s.index)
    normed = (s - lo) / (hi - lo)
    return 1 - normed if invert else normed


# ============================================================
# Header
# ============================================================

st.markdown("""
<div style="padding: 24px 0 8px 0;">
  <span style="font-size: 32px; font-weight: 800; color: #f0f0f0;">
    Real Estate Investment Scout
  </span>
  <span style="font-size: 14px; color: #888; margin-left: 16px;">
    100 US markets · 10 top picks · 1,199 active listings
  </span>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️  National Market Scan",
    "🏆  Top 10 Investment Markets",
    "🔍  Listings Explorer",
    "🏙️  City Deep Dive",
])


# ============================================================
# TAB 1 — National Market Scan
# ============================================================

with tab1:
    st.markdown("### 100 US Housing Markets — Investment Score")
    st.caption(
        "Each bubble is one metro. **Size** = number of homes sold (liquidity proxy). "
        "**Color** = composite investment score built from YoY appreciation, sale-to-list ratio, "
        "days on market, transaction volume, and affordability. Gold rings mark the top-10 picks."
    )

    df_map = df_all[df_all["lat"].notna() & df_all["lon"].notna()].copy()

    fig_geo = px.scatter_geo(
        df_map,
        lat="lat",
        lon="lon",
        size="homes_sold",
        color="score",
        color_continuous_scale=[
            [0.0, "#1a3a6b"],
            [0.4, "#2d6ea8"],
            [0.65, "#edc602"],
            [1.0, "#ff4500"],
        ],
        hover_name="city",
        hover_data={
            "state": True,
            "score": ":.3f",
            "median_price": ":,.0f",
            "yoy_change": ":.1f",
            "days_on_market": True,
            "lat": False,
            "lon": False,
        },
        scope="usa",
        projection="albers usa",
        size_max=40,
    )
    fig_geo.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        geo=dict(
            bgcolor="#0e1117",
            lakecolor="#1a2540",
            landcolor="#1c2235",
            subunitcolor="#2d3347",
            showlakes=True,
            showland=True,
        ),
        coloraxis_colorbar=dict(
            title=dict(text="Score", font=dict(color="#aaa")),
            tickfont=dict(color="#aaa"),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
    )
    # Highlight top-10 with gold border
    top10_map = df_map[df_map["is_top10"]]
    fig_geo.add_trace(go.Scattergeo(
        lat=top10_map["lat"],
        lon=top10_map["lon"],
        mode="markers+text",
        marker=dict(size=14, color="rgba(0,0,0,0)", line=dict(color="#edc602", width=2)),
        text=top10_map["city"],
        textposition="top center",
        textfont=dict(color="#edc602", size=10),
        hoverinfo="skip",
        showlegend=False,
    ))
    st.plotly_chart(fig_geo, use_container_width=True)

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("#### Market Rankings")
        st.caption("Scored on 5 weighted factors: YoY appreciation (30%), sale-to-list ratio (25%), days on market (20%), transaction volume (15%), affordability (10%). Click a column header to sort.")
        display_df = df_all[["rank", "city", "state", "score", "median_price",
                              "yoy_change", "days_on_market", "sale_to_list", "homes_sold"]].copy()
        display_df["median_price"] = display_df["median_price"].apply(fmt_price)
        display_df["score"] = display_df["score"].round(3)
        display_df["yoy_change"] = display_df["yoy_change"].apply(
            lambda v: f"+{v:.1f}%" if pd.notna(v) and v > 0 else (f"{v:.1f}%" if pd.notna(v) else "N/A")
        )
        display_df["sale_to_list"] = display_df["sale_to_list"].apply(
            lambda v: f"{v:.1f}%" if pd.notna(v) else "N/A"
        )
        display_df.columns = ["#", "City", "State", "Score", "Med. Price",
                               "YoY", "DOM", "STL", "Vol."]
        st.dataframe(display_df, use_container_width=True, height=420, hide_index=True)

    with col_b:
        st.markdown("#### Price vs. Appreciation")
        st.caption("The sweet spot: markets in the upper-left — strong appreciation without a high entry price. Top-10 markets are labeled. Hover any dot for full details.")
        scatter_df = df_all[df_all["median_price"].notna() & df_all["yoy_change"].notna()].copy()
        fig_scatter = px.scatter(
            scatter_df,
            x="median_price",
            y="yoy_change",
            color="score",
            color_continuous_scale=[[0, "#2d6ea8"], [0.5, "#edc602"], [1, "#ff4500"]],
            hover_name="city",
            hover_data={"state": True, "score": ":.3f", "median_price": False, "yoy_change": False},
            labels={"median_price": "Median Price ($)", "yoy_change": "YoY Appreciation (%)"},
            size_max=10,
        )
        # Label top-10
        for _, row in top10_df.iterrows():
            match = df_all[(df_all["city"] == row["city"]) & (df_all["state"] == row["state"])]
            if not match.empty and pd.notna(match.iloc[0]["median_price"]):
                m = match.iloc[0]
                fig_scatter.add_annotation(
                    x=m["median_price"], y=m["yoy_change"],
                    text=m["city"].split()[0], showarrow=False,
                    font=dict(color="#edc602", size=9), yshift=10,
                )
        fig_scatter.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#151b2d",
            font=dict(color="#aaa"),
            xaxis=dict(gridcolor="#2d3347", color="#aaa"),
            yaxis=dict(gridcolor="#2d3347", color="#aaa"),
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=10, b=0),
            height=420,
        )
        st.plotly_chart(fig_scatter, use_container_width=True)


# ============================================================
# TAB 2 — Top 10 Investment Markets
# ============================================================

with tab2:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### Investment Radar")
        st.caption(
            "Each axis is normalized 0–1 across the top 10. Larger filled area = stronger overall profile. "
            "**Speed** is days-on-market inverted (faster = better). **Affordability** is price inverted (cheaper = better). "
            "Use the multiselect to isolate specific cities."
        )

        radar_cities = st.multiselect(
            "Compare cities:",
            options=[f"{r['city']}, {r['state']}" for r in top10],
            default=[f"{r['city']}, {r['state']}" for r in top10[:5]],
            key="radar_select",
        )

        dims = {
            "YoY Apprec.": ("yoy_change", False),
            "Sale-to-List": ("sale_to_list", False),
            "Speed (DOM)": ("days_on_market", True),
            "Volume": ("homes_sold", False),
            "Affordability": ("median_price", True),
        }
        labels = list(dims.keys())

        normed = {}
        for label, (col, inv) in dims.items():
            s = pd.to_numeric(top10_df[col], errors="coerce")
            normed[label] = normalize_series(s, invert=inv).values

        colors = ["#edc602", "#4fc3f7", "#81c784", "#ff8a65", "#ce93d8",
                  "#80deea", "#a5d6a7", "#ef9a9a", "#fff59d", "#b39ddb"]

        fig_radar = go.Figure()
        for i, row in enumerate(top10):
            key = f"{row['city']}, {row['state']}"
            if key not in radar_cities:
                continue
            vals = [normed[lbl][i] for lbl in labels]
            vals_closed = vals + [vals[0]]
            labels_closed = labels + [labels[0]]
            hex_c = colors[i % len(colors)].lstrip("#")
            r_c, g_c, b_c = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            fig_radar.add_trace(go.Scatterpolar(
                r=vals_closed,
                theta=labels_closed,
                fill="toself",
                name=row["city"],
                line=dict(color=colors[i % len(colors)], width=2),
                fillcolor=f"rgba({r_c},{g_c},{b_c},0.15)",
                opacity=0.85,
            ))

        fig_radar.update_layout(
            polar=dict(
                bgcolor="#151b2d",
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#2d3347", color="#555", showticklabels=False),
                angularaxis=dict(gridcolor="#2d3347", color="#aaa"),
            ),
            paper_bgcolor="#0e1117",
            legend=dict(font=dict(color="#aaa"), bgcolor="#0e1117"),
            margin=dict(l=40, r=40, t=20, b=20),
            height=420,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.markdown("#### Metric Comparison")
        st.caption("Raw values for each metric across all 10 markets. Switch the dropdown to see how rankings shift depending on what you optimize for — price, velocity, or appreciation.")
        metric_options = {
            "Median Price": "median_price",
            "YoY Appreciation (%)": "yoy_change",
            "Days on Market": "days_on_market",
            "Sale-to-List (%)": "sale_to_list",
            "Homes Sold": "homes_sold",
        }
        sel_metric = st.selectbox("Sort by:", list(metric_options.keys()), key="bar_metric")
        bar_col = metric_options[sel_metric]
        bar_df = top10_df[["city", bar_col]].dropna().sort_values(bar_col, ascending=True)
        fig_bar = px.bar(
            bar_df, x=bar_col, y="city", orientation="h",
            color=bar_col,
            color_continuous_scale=[[0, "#2d6ea8"], [0.5, "#edc602"], [1, "#ff4500"]],
            labels={bar_col: sel_metric, "city": ""},
        )
        fig_bar.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#151b2d",
            font=dict(color="#aaa"),
            xaxis=dict(gridcolor="#2d3347", color="#aaa"),
            yaxis=dict(gridcolor="#2d3347", color="#aaa"),
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=0, b=0),
            height=320,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.markdown("### City Analysis")
        st.caption("Claude's investment thesis and key risk for each market, derived from Redfin market data. Expand any card for the full analysis.")
        for row in top10:
            price_str = fmt_price(row.get("median_price"))
            yoy = row.get("yoy_change")
            yoy_str = f"+{yoy:.1f}%" if yoy and yoy > 0 else (f"{yoy:.1f}%" if yoy else "N/A")
            dom = row.get("days_on_market", "N/A")
            stl = row.get("sale_to_list")
            stl_str = f"{stl:.1f}%" if stl else "N/A"

            st.markdown(f"""
            <div class="city-card">
              <div style="display:flex; align-items:center; margin-bottom:10px;">
                <span class="rank-badge">#{row['rank']}</span>
                <span style="font-size:18px; font-weight:700; color:#f0f0f0;">{row['city']}, {row['state']}</span>
              </div>
              <div style="display:flex; gap:24px; margin-bottom:12px; flex-wrap:wrap;">
                <div><div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Price</div>
                     <div style="color:#edc602;font-size:16px;font-weight:700;">{price_str}</div></div>
                <div><div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;">YoY</div>
                     <div style="color:#4fc3f7;font-size:16px;font-weight:700;">{yoy_str}</div></div>
                <div><div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;">DOM</div>
                     <div style="color:#f0f0f0;font-size:16px;font-weight:700;">{dom}d</div></div>
                <div><div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;">STL</div>
                     <div style="color:#81c784;font-size:16px;font-weight:700;">{stl_str}</div></div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"Analysis — {row['city']}"):
                st.markdown(f"**Investment Thesis**\n\n{row['thesis']}")
                st.markdown(f"**Key Risk**\n\n{row['risk']}")


# ============================================================
# TAB 3 — Listings Explorer
# ============================================================

with tab3:
    st.markdown("### Active Listings — Top 10 Markets")
    st.caption("1,199 active Zillow listings collected across 30 zip codes (3 per market). Filter by market, price, bedrooms, and home type. Click any dot on the map for address and details.")

    # Filters
    f1, f2, f3, f4 = st.columns([2, 2, 1, 2])
    with f1:
        cities_available = sorted(df_listings["market_city"].dropna().unique())
        sel_cities = st.multiselect("Markets:", cities_available, default=cities_available, key="filter_cities")
    with f2:
        price_max = int(df_listings["price"].quantile(0.97))
        price_range = st.slider("Price range:", 0, price_max, (0, price_max), step=10_000,
                                format="$%d", key="filter_price")
    with f3:
        min_beds = st.selectbox("Min beds:", [0, 1, 2, 3, 4], index=0, key="filter_beds")
    with f4:
        home_types = sorted(df_listings["home_type"].dropna().unique())
        sel_types = st.multiselect("Home type:", home_types, default=home_types, key="filter_types")

    mask = (
        df_listings["market_city"].isin(sel_cities) &
        df_listings["price"].between(price_range[0], price_range[1]) &
        (df_listings["bedrooms"] >= min_beds) &
        df_listings["home_type"].isin(sel_types)
    )
    df_filtered = df_listings[mask].dropna(subset=["latitude", "longitude"]).copy()

    st.caption(f"{len(df_filtered):,} listings match · {len(df_listings):,} total")

    # Price color column
    df_filtered["color"] = df_filtered["price"].apply(price_color)

    # pydeck map
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtered[["latitude", "longitude", "price", "color",
                           "bedrooms", "home_type", "full_address"]].copy(),
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=400,
        radius_min_pixels=4,
        radius_max_pixels=16,
        pickable=True,
        auto_highlight=True,
    )
    view = pdk.ViewState(
        latitude=df_filtered["latitude"].mean() if len(df_filtered) else 39.5,
        longitude=df_filtered["longitude"].mean() if len(df_filtered) else -98.35,
        zoom=5,
        pitch=0,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style=CARTO_DARK,
        tooltip={
            "html": "<b>{full_address}</b><br/>💰 ${price}<br/>🛏 {bedrooms} bed · {home_type}",
            "style": {"backgroundColor": "#1a1f2e", "color": "#edc602", "fontSize": "13px"},
        },
    )
    st.pydeck_chart(deck, use_container_width=True, height=440)

    # Legend
    st.markdown("""
    <div style="display:flex;gap:20px;padding:8px 0;font-size:12px;color:#aaa;">
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#00c864;margin-right:4px;"></span>&lt;$300K</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#edc602;margin-right:4px;"></span>$300K–$700K</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ff6428;margin-right:4px;"></span>$700K–$1.5M</span>
      <span><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#b450ff;margin-right:4px;"></span>&gt;$1.5M</span>
    </div>
    """, unsafe_allow_html=True)

    # Stats by city
    st.markdown("#### Stats by Market")
    st.caption("Aggregated from filtered listings. Median price reflects active asking prices, not closed sales.")
    stats_df = (
        df_filtered.groupby("market_city")
        .agg(
            listings=("price", "count"),
            median_price=("price", "median"),
            avg_beds=("bedrooms", "mean"),
            avg_sqft=("living_area_in_sqft", "mean"),
            avg_dom=("days_on_zillow", "mean"),
        )
        .reset_index()
        .sort_values("listings", ascending=False)
    )
    stats_df["median_price"] = stats_df["median_price"].apply(fmt_price)
    stats_df["avg_beds"] = stats_df["avg_beds"].round(1)
    stats_df["avg_sqft"] = stats_df["avg_sqft"].round(0).apply(
        lambda v: f"{int(v):,}" if pd.notna(v) else "N/A"
    )
    stats_df["avg_dom"] = stats_df["avg_dom"].round(1)
    stats_df.columns = ["Market", "Listings", "Median Price", "Avg Beds", "Avg Sqft", "Avg DOM"]
    st.dataframe(stats_df, use_container_width=True, hide_index=True)

    # Photo gallery — first 24 with images
    st.markdown("#### Listings Gallery")
    st.caption("24 lowest-priced listings with photos from the current filter. Prices shown are active asking prices from Zillow.")
    gallery_df = (
        df_filtered[df_filtered["first_image"].notna()]
        .sort_values("price")
        .head(24)
    )
    if gallery_df.empty:
        st.info("No listings with photos match the current filters.")
    else:
        rows = [gallery_df.iloc[i:i+4] for i in range(0, min(len(gallery_df), 24), 4)]
        for row_items in rows:
            cols = st.columns(4)
            for col, (_, listing) in zip(cols, row_items.iterrows()):
                with col:
                    st.image(listing["first_image"], use_container_width=True)
                    beds = int(listing["bedrooms"]) if pd.notna(listing["bedrooms"]) else "?"
                    baths = int(listing["bathrooms"]) if pd.notna(listing["bathrooms"]) else "?"
                    st.markdown(
                        f"**{fmt_price(listing['price'])}**  \n"
                        f"{beds}bd · {baths}ba · {listing['home_type'].replace('_', ' ').title()}  \n"
                        f"<span style='color:#888;font-size:11px;'>{listing['market_city']}</span>",
                        unsafe_allow_html=True,
                    )


# ============================================================
# TAB 4 — City Deep Dive
# ============================================================

with tab4:
    city_options = [f"{r['city']}, {r['state']}" for r in top10]
    selected = st.selectbox("Select a market:", city_options, key="deepdive_city")
    sel_city, sel_state = selected.split(", ", 1)

    # Find top10 entry
    t10_row = next(r for r in top10 if r["city"] == sel_city and r["state"] == sel_state)
    city_listings = df_listings[
        (df_listings["market_city"] == sel_city) & df_listings["latitude"].notna()
    ].copy()

    # 5 metric cards
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Median Price", fmt_price(t10_row.get("median_price")))
    with m2:
        yoy = t10_row.get("yoy_change")
        st.metric("YoY Appreciation", f"{yoy:+.1f}%" if yoy else "N/A")
    with m3:
        st.metric("Days on Market", f"{t10_row.get('days_on_market', 'N/A')}d")
    with m4:
        stl = t10_row.get("sale_to_list")
        st.metric("Sale-to-List", f"{stl:.1f}%" if stl else "N/A")
    with m5:
        st.metric("Homes Sold", f"{int(t10_row['homes_sold']):,}" if t10_row.get("homes_sold") else "N/A")

    st.divider()

    # Claude analysis — full width
    st.markdown("#### Claude Investment Analysis")
    st.markdown(
        f"<div style='background:#1a1f2e;border-radius:10px;padding:20px;border-left:4px solid #edc602;'>"
        f"<div style='color:#aaa;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;'>"
        f"Rank #{t10_row['rank']} · Investment Thesis</div>"
        f"<div style='color:#e8e8e8;line-height:1.7;'>{t10_row['thesis']}</div>"
        f"<div style='color:#888;font-size:12px;margin-top:16px;padding-top:12px;border-top:1px solid #2d3347;'>"
        f"⚠️ Key Risk: {t10_row['risk']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Perplexity report — full width with read more
    st.markdown("#### Perplexity Market Report")
    report = reports_dict.get((sel_city, sel_state), "Report not available.")
    paragraphs = format_report(report).split("\n\n")
    preview = "\n\n".join(paragraphs[:4])
    remainder = "\n\n".join(paragraphs[4:])
    with st.container(border=True):
        st.markdown(preview)
        if remainder:
            with st.expander("Read more"):
                st.markdown(remainder)

    st.divider()

    # pydeck city map
    map_col, chart_col = st.columns([3, 2], gap="large")

    with map_col:
        st.markdown(f"#### Active Listings Map — {sel_city}")
        st.caption("Dots colored by price tier: green < $300K · yellow $300K–$700K · red $700K–$1.5M · purple > $1.5M. Hover for address and details.")
        if city_listings.empty:
            st.info("No listings data for this market.")
        else:
            city_listings["color"] = city_listings["price"].apply(price_color)
            city_lat = CITY_COORDS.get((sel_city, sel_state), (None, None))[0] or city_listings["latitude"].mean()
            city_lon = CITY_COORDS.get((sel_city, sel_state), (None, None))[1] or city_listings["longitude"].mean()

            city_layer = pdk.Layer(
                "ScatterplotLayer",
                data=city_listings[["latitude", "longitude", "price", "color",
                                    "bedrooms", "home_type", "full_address"]].copy(),
                get_position=["longitude", "latitude"],
                get_color="color",
                get_radius=80,
                pickable=True,
                auto_highlight=True,
            )
            city_view = pdk.ViewState(latitude=city_lat, longitude=city_lon, zoom=11, pitch=30)
            city_deck = pdk.Deck(
                layers=[city_layer],
                initial_view_state=city_view,
                map_style=CARTO_DARK,
                tooltip={
                    "html": "<b>{full_address}</b><br/>💰 ${price}<br/>🛏 {bedrooms} bed · {home_type}",
                    "style": {"backgroundColor": "#1a1f2e", "color": "#edc602", "fontSize": "13px"},
                },
            )
            st.pydeck_chart(city_deck, use_container_width=True, height=380)

    with chart_col:
        st.markdown("#### Price Distribution")
        st.caption("Active listing prices (top 5% outliers excluded for readability).")
        price_data = city_listings["price"].dropna()
        if not price_data.empty:
            fig_hist = px.histogram(
                city_listings[city_listings["price"] < city_listings["price"].quantile(0.95)],
                x="price",
                nbins=30,
                color_discrete_sequence=["#edc602"],
                labels={"price": "Price ($)", "count": "Listings"},
            )
            fig_hist.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#151b2d",
                font=dict(color="#aaa"),
                xaxis=dict(gridcolor="#2d3347", color="#aaa"),
                yaxis=dict(gridcolor="#2d3347", color="#aaa"),
                bargap=0.1,
                margin=dict(l=0, r=0, t=0, b=0),
                height=170,
                showlegend=False,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("#### Listings by Home Type")
        st.caption("Breakdown of available inventory by property type in this market.")
        type_counts = city_listings["home_type"].value_counts().reset_index()
        type_counts.columns = ["type", "count"]
        type_counts["type"] = type_counts["type"].str.replace("_", " ").str.title()
        fig_types = px.bar(
            type_counts, x="count", y="type", orientation="h",
            color="count",
            color_continuous_scale=[[0, "#2d6ea8"], [1, "#edc602"]],
            labels={"count": "Listings", "type": ""},
        )
        fig_types.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#151b2d",
            font=dict(color="#aaa"),
            xaxis=dict(gridcolor="#2d3347", color="#aaa"),
            yaxis=dict(gridcolor="#2d3347", color="#aaa"),
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=0, b=0),
            height=180,
        )
        st.plotly_chart(fig_types, use_container_width=True)

    # Photo gallery — 12 listings with images
    st.markdown(f"#### Active Listings — {sel_city}")
    st.caption("12 lowest-priced active listings with photos. Click through to Zillow for full details.")
    gallery_city = (
        city_listings[city_listings["first_image"].notna()]
        .sort_values("price")
        .head(12)
    )
    if gallery_city.empty:
        st.info("No listing photos available for this market.")
    else:
        rows = [gallery_city.iloc[i:i+4] for i in range(0, min(len(gallery_city), 12), 4)]
        for row_items in rows:
            cols = st.columns(4)
            for col, (_, listing) in zip(cols, row_items.iterrows()):
                with col:
                    st.image(listing["first_image"], use_container_width=True)
                    beds = int(listing["bedrooms"]) if pd.notna(listing["bedrooms"]) else "?"
                    baths = int(listing["bathrooms"]) if pd.notna(listing["bathrooms"]) else "?"
                    sqft = f"{int(listing['living_area_in_sqft']):,} sqft" if pd.notna(listing.get("living_area_in_sqft")) else ""
                    st.markdown(
                        f"**{fmt_price(listing['price'])}**  \n"
                        f"{beds}bd · {baths}ba  \n"
                        f"<span style='color:#888;font-size:11px;'>{sqft}</span>",
                        unsafe_allow_html=True,
                    )
