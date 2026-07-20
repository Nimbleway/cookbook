"""MAP Compliance Monitor — Streamlit dashboard (Nimble-themed).

Reads the built JSON summaries (data/*.json). Leads with the discovery-fan-out
aggregate, then a severity-coded overview, the repeat-offender leaderboard, and a
per-violation evidence drill-down. Run: streamlit run app.py

Design (per dataviz method):
  - Dark surface + Nimble yellow (#edc602) as the brand/magnitude accent.
  - Magnitude bars use a single hue (category identity is carried by the axis).
  - Severity uses the reserved, validated STATUS palette, always with a label:
      Mild <10%  (amber #fab219) · Moderate 10-25% (orange #ec835a) · Severe >=25% (red #d03b3b)
"""
import json

import altair as alt
import pandas as pd
import streamlit as st

import config as C

# --- Nimble palette ---
YELLOW = "#edc602"
SURFACE = "#0e1117"
CARD = "#1a1d24"
BORDER = "#2b2f38"
INK = "#f5f5f2"
MUTED = "#9aa0aa"
SEV = {"Mild": "#fab219", "Moderate": "#ec835a", "Severe": "#d03b3b"}   # reserved status palette
SEV_EMOJI = {"Mild": "🟡", "Moderate": "🟠", "Severe": "🔴"}
SEV_ORDER = ["Severe", "Moderate", "Mild"]

st.set_page_config(page_title="MAP Compliance Monitor", page_icon="🛡️", layout="wide")

st.markdown(f"""
<style>
  .stApp {{ background:{SURFACE}; }}
  .block-container {{ padding-top:2.2rem; max-width:1300px; }}
  h1,h2,h3 {{ color:{INK}; letter-spacing:-0.01em; }}
  /* KPI cards */
  div[data-testid="stMetric"] {{
    background:{CARD}; border:1px solid {BORDER}; border-radius:14px;
    padding:16px 18px; box-shadow:0 1px 0 rgba(0,0,0,.3);
  }}
  div[data-testid="stMetric"] label p {{ color:{MUTED}; font-weight:600; font-size:.8rem;
    text-transform:uppercase; letter-spacing:.04em; }}
  div[data-testid="stMetricValue"] {{ color:{INK}; font-weight:700; }}
  div[data-testid="stMetric"]:first-child div[data-testid="stMetricValue"] {{ color:{YELLOW}; }}
  /* accent rule under the title */
  .accent {{ height:3px; width:64px; background:{YELLOW}; border-radius:3px; margin:.2rem 0 1.1rem; }}
  .sev-chip {{ display:inline-block; padding:2px 10px; border-radius:999px; font-weight:700;
    font-size:.75rem; color:#0e1117; }}
  a {{ color:{YELLOW} !important; }}
</style>
""", unsafe_allow_html=True)


def load(name):
    p = C.DATA / name
    return json.loads(p.read_text()) if p.exists() else None


def severity(gap_pct: float) -> str:
    if gap_pct >= 25:
        return "Severe"
    if gap_pct >= 10:
        return "Moderate"
    return "Mild"


summary = load("summary.json")
violations = load("violations.json") or []
rollup = load("seller_rollup.json") or []

st.title("🛡️ MAP Compliance Monitor")
st.markdown('<div class="accent"></div>', unsafe_allow_html=True)
st.caption("Open-web seller discovery + below-MAP violation detection · powered by Nimble Web Search Agents")

if not summary:
    st.warning("No data yet. Run `python discover.py` then `python compute_violations.py`.")
    st.stop()

vdf = pd.DataFrame(violations)
if not vdf.empty:
    vdf["severity"] = vdf["gap_pct"].apply(severity)

# --- Aggregate KPIs (the discovery fan-out headline) ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Listings scanned", f"{summary['total_offers']:,}")
c2.metric("Unique sellers", f"{summary['unique_sellers']:,}")
c3.metric("Violations", f"{summary['total_violations']:,}")
c4.metric("Sellers in violation", f"{summary['sellers_in_violation']:,}")
top = summary.get("top_offender")
c5.metric("Top offender", top.get("seller_domain") if top else "—",
          f"{top['distinct_skus_violated']} SKUs" if top else None)

st.write("")

# --- Row: severity mix + violations by seller type ---
left, right = st.columns([1, 1.3])

with left:
    st.subheader("Violation severity")
    if not vdf.empty:
        sev = (vdf.groupby("severity").size().reindex(SEV_ORDER).fillna(0)
               .astype(int).reset_index(name="count"))
        chart = alt.Chart(sev).mark_bar(cornerRadiusEnd=4, size=34).encode(
            x=alt.X("count:Q", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("severity:N", sort=SEV_ORDER, title=None),
            color=alt.Color("severity:N", scale=alt.Scale(domain=list(SEV), range=list(SEV.values())),
                            legend=None),
            tooltip=["severity", "count"],
        ).properties(height=150)
        st.altair_chart(chart, use_container_width=True)
        cols = st.columns(3)
        for i, tier in enumerate(["Mild", "Moderate", "Severe"]):
            n = int((vdf["severity"] == tier).sum())
            band = {"Mild": "<10%", "Moderate": "10–25%", "Severe": "≥25%"}[tier]
            cols[i].markdown(
                f'<span class="sev-chip" style="background:{SEV[tier]}">{SEV_EMOJI[tier]} {tier}</span>'
                f'<div style="color:{MUTED};font-size:.75rem;margin-top:4px">{band} below MAP</div>'
                f'<div style="color:{INK};font-size:1.4rem;font-weight:700">{n}</div>',
                unsafe_allow_html=True)

with right:
    st.subheader("Violations by seller type")
    if not vdf.empty:
        bytype = vdf.groupby("seller_type").size().reset_index(name="count").sort_values("count")
        chart = alt.Chart(bytype).mark_bar(cornerRadiusEnd=4, color=YELLOW).encode(
            x=alt.X("count:Q", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("seller_type:N", sort="-x", title=None),
            tooltip=["seller_type", "count"],
        ).properties(height=210)
        st.altair_chart(chart, use_container_width=True)

st.divider()

# --- Repeat-offender leaderboard (scale-native payoff) ---
st.subheader("Top 10 repeat offenders")
st.caption("Sellers ranked by how many of your SKUs they undercut — the enforcement priority list. "
           "Gap columns are colored by severity.")
if rollup:
    rdf = pd.DataFrame(rollup).head(10).copy()
    rdf.insert(0, "rank", range(1, len(rdf) + 1))
    rdf["type_label"] = rdf["seller_type"].fillna("unknown").str.replace("_", " ").str.title()
    tbl = rdf[["rank", "seller_domain", "type_label", "distinct_skus_violated",
               "violation_count", "avg_gap_pct", "max_gap_pct"]].copy()
    tbl.columns = ["#", "Seller (domain)", "Type", "SKUs undercut", "Listings", "Avg gap %", "Max gap %"]

    def color_gap(val):
        return f"color:{SEV[severity(val)]};font-weight:700"
    styler = (tbl.style
              .map(color_gap, subset=["Avg gap %", "Max gap %"])
              .format({"Avg gap %": "{:.1f}%", "Max gap %": "{:.1f}%"}))
    st.dataframe(
        styler, use_container_width=True, hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "SKUs undercut": st.column_config.NumberColumn(help="Distinct SKUs this seller lists below MAP"),
            "Listings": st.column_config.NumberColumn(help="Total below-MAP listings from this seller"),
        })
    st.caption("Identity = seller domain. Marketplace domains (walmart.com, ebay.com) aggregate their "
               "third-party sellers — the unit you'd file one Brand Registry takedown against.")
else:
    st.info("No violations found.")

st.divider()

# --- Violations table with severity coding + evidence drill-down ---
st.subheader("Violations")
if not vdf.empty:
    brands = ["All"] + sorted(vdf["brand"].dropna().unique().tolist())
    tiers = ["All"] + SEV_ORDER
    f1, f2, _ = st.columns([1, 1, 2])
    brand = f1.selectbox("Brand", brands)
    tier = f2.selectbox("Severity", tiers)
    view = vdf.copy()
    if brand != "All":
        view = view[view["brand"] == brand]
    if tier != "All":
        view = view[view["severity"] == tier]
    view = view.sort_values("gap_pct", ascending=False)

    show = view[["severity", "sku_id", "product_name", "size", "seller_name", "seller_domain",
                 "seller_type", "advertised_price_num", "map_price", "gap_pct", "price_confidence",
                 "listing_url"]].copy()
    show["severity"] = show["severity"].map(lambda t: f"{SEV_EMOJI[t]} {t}")
    show.columns = ["Severity", "SKU", "Product", "Size", "Seller", "Domain", "Type",
                    "Advertised", "MAP", "Gap %", "Confidence", "Listing"]

    def color_gap(val):
        t = severity(val)
        return f"color:{SEV[t]};font-weight:700"
    styler = show.style.map(color_gap, subset=["Gap %"]) \
        .format({"Advertised": "${:.2f}", "MAP": "${:.2f}", "Gap %": "{:.1f}%"})
    st.dataframe(styler, use_container_width=True, hide_index=True,
                 column_config={"Listing": st.column_config.LinkColumn("Listing", display_text="open")})

    st.markdown("#### Evidence drill-down")
    # Cascading select: pick a source (seller) first, then a violation from that seller.
    src_counts = view["seller_domain"].value_counts()
    sources = sorted(src_counts.index, key=lambda d: (-src_counts[d], d))
    s1, s2 = st.columns(2)
    source = s1.selectbox("1 · Source (seller domain)", sources,
                          format_func=lambda d: f"{d} ({src_counts[d]} violation{'s' if src_counts[d] > 1 else ''})")
    src_view = view[view["seller_domain"] == source]
    vidx = s2.selectbox("2 · Violation at this source", src_view.index,
                        format_func=lambda i: f"{src_view.loc[i,'sku_id']} · {src_view.loc[i,'product_name'][:38]} · "
                                              f"${src_view.loc[i,'advertised_price_num']:.2f} (−{src_view.loc[i,'gap_pct']:.0f}%)")
    v = view.loc[vidx]
    tier = v["severity"]

    # 1) Header — product + severity chip
    st.markdown(
        f"<div style='font-size:1.15rem;font-weight:700;color:{INK};margin-bottom:2px'>{v['product_name']}"
        f"<span style='color:{MUTED};font-weight:500'> · {v['size']}</span></div>"
        f"<span class='sev-chip' style='background:{SEV[tier]}'>{SEV_EMOJI[tier]} {tier} · "
        f"{v['gap_pct']:.0f}% below MAP</span>", unsafe_allow_html=True)
    st.write("")

    # 2) Price comparison — three metrics
    p1, p2, p3 = st.columns(3)
    p1.metric("Advertised price", f"${v['advertised_price_num']:.2f}")
    p2.metric("Minimum Advertised Price", f"${v['map_price']:.2f}")
    p3.metric("Gap below MAP", f"${v['gap_abs']:.2f}", f"-{v['gap_pct']:.0f}%", delta_color="inverse")

    # 3) Structured seller + evidence blocks
    def kv(label, val):
        return (f"<div style='margin-bottom:8px'><span style='color:{MUTED};font-size:.75rem;"
                f"text-transform:uppercase;letter-spacing:.04em'>{label}</span><br>"
                f"<span style='color:{INK}'>{val}</span></div>")

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Seller**")
        conf = (v.get("price_confidence") or "n/a").title()
        st.markdown(
            kv("Seller", v.get("seller_name") or v["seller_domain"])
            + kv("Domain", v["seller_domain"])
            + kv("Type", (v.get("seller_type") or "unknown").replace("_", " ").title())
            + kv("SKU", f"{v['sku_id']} — {v['brand']}")
            + kv("Observed", v.get("observed_at") or "n/a")
            + kv("Price-claim confidence", conf), unsafe_allow_html=True)
    with d2:
        st.markdown("**Cited evidence**")
        st.info(v.get("evidence_excerpt") or "(price observed on listing page)")
        src = v.get("evidence_url") or v.get("listing_url")
        st.markdown(
            kv("Source", f"<a href='{src}' target='_blank'>{src}</a>" if src else "n/a")
            + kv("Listing", f"<a href='{v['listing_url']}' target='_blank'>open listing ↗</a>"),
            unsafe_allow_html=True)
else:
    st.info("No violations found across the scanned catalog.")
