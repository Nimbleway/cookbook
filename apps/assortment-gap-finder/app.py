"""Assortment Gap Finder — Streamlit UI over the Delta catalog."""
import json
import os

import pandas as pd
import requests
import streamlit as st

import config as C
import delta
import gaps as gaps_mod

st.set_page_config(page_title="Assortment Gap Finder", page_icon="🧭", layout="wide")


@st.cache_data(ttl=300)
def q(sql, params=None):
    cols, rows = delta.query(sql, params)
    # Databricks returns lowercase column names; normalize like Snowflake for consistency
    return pd.DataFrame(rows, columns=[c.upper() for c in cols])


def page_catalog():
    st.title("🧭 Assortment Gap Finder")
    st.caption(f"The digital shelf for {C.CATEGORY}: full catalog, whitespace math, "
               "verified gaps. Built on Nimble Web Search Agents.")
    stats = q(f"""SELECT COUNT(*) AS skus, COUNT(DISTINCT brand) AS brands,
                  ROUND(AVG(rating),2) AS avg_rating
                  FROM {C.DBX_SCHEMA}.catalog""")
    if stats.empty or not stats.iloc[0]["SKUS"]:
        st.info("Catalog is empty — run discover.py first.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("SKUs", int(stats.iloc[0]["SKUS"]))
    c2.metric("Brands", int(stats.iloc[0]["BRANDS"]))
    c3.metric("Avg rating", stats.iloc[0]["AVG_RATING"])

    st.markdown("#### Whitespace grid (products / rated 4.2+)")
    grid = q(f"""SELECT {gaps_mod.normalize_subcat_sql()} AS subcat, {gaps_mod.BAND_SQL} AS band,
                 COUNT(*) AS n, SUM(CASE WHEN rating >= 4.2 THEN 1 ELSE 0 END) AS wr
                 FROM {C.DBX_SCHEMA}.catalog WHERE price_usd IS NOT NULL GROUP BY 1, 2""")
    if not grid.empty:
        pivot = grid.assign(CELL=grid["N"].astype(str) + " / " + grid["WR"].astype(str)) \
                    .pivot_table(index="SUBCAT", columns="BAND", values="CELL", aggfunc="first")
        band_order = [b for _, _, b in C.PRICE_BANDS if b in pivot.columns]
        st.dataframe(pivot[band_order], use_container_width=True)

    st.markdown("#### Catalog")
    df = q(f"""SELECT product_name, brand, subcategory, price_raw AS price, rating_raw AS rating,
               review_count_raw AS reviews, product_url
               FROM {C.DBX_SCHEMA}.catalog ORDER BY review_count DESC NULLS LAST""")
    st.dataframe(df, use_container_width=True, height=420,
                 column_config={"PRODUCT_URL": st.column_config.LinkColumn()})


def page_gaps():
    st.title("🎯 Gap board")
    df = q(f"""SELECT gap_statement, verdict, demand_evidence, evidence_summary,
               closest_matches, linear_issue_id, linear_issue_url, created_at
               FROM {C.DBX_SCHEMA}.gaps ORDER BY created_at DESC""")
    if df.empty:
        st.info("No gaps yet — run synth.py after discovery + mining.")
        return
    icon = {"confirmed": "🟢", "partial": "🟡", "refuted": "🔴"}
    for _, r in df.iterrows():
        with st.expander(f"{icon.get(r['VERDICT'], '⚪')} {r['GAP_STATEMENT']}", expanded=False):
            if r["LINEAR_ISSUE_URL"]:
                st.markdown(f"**Ticket:** [{r['LINEAR_ISSUE_ID']}]({r['LINEAR_ISSUE_URL']})")
            st.markdown(f"**Customer demand:** {r['DEMAND_EVIDENCE']}")
            st.markdown(f"**Live-shelf verification:** {r['EVIDENCE_SUMMARY']}")
            try:
                for m in json.loads(r["CLOSEST_MATCHES"] or "[]")[:5]:
                    st.caption(f"closest: {m.get('product_name')} — {m.get('price_usd')} — "
                               f"{m.get('why_close_but_not_matching') or ''} {m.get('product_url')}")
            except (json.JSONDecodeError, TypeError):
                pass


def page_evidence():
    st.title("🗣 Customer evidence")
    st.caption("Why these products: the whitespace math flagged thin or badly-rated cells in the "
               "catalog. These are the MOST-REVIEWED products in and around those cells — their "
               "reviews are the customer-demand evidence behind each gap hypothesis. Every quote "
               "is verbatim from a real review; the synthesis agent only proposed gaps where "
               "these complaints and the catalog math pointed the same way.")
    df = q(f"""SELECT t.product_name, t.kind, t.theme, t.quote, t.quote_source_url,
               {gaps_mod.normalize_subcat_sql().replace('subcategory', 'c.subcategory').replace('chunk_id', 'c.chunk_id')} AS subcat,
               CASE WHEN c.price_usd < 50 THEN '<$50' WHEN c.price_usd < 150 THEN '$50-150'
                    WHEN c.price_usd < 400 THEN '$150-400' ELSE '$400+' END AS band
               FROM {C.DBX_SCHEMA}.review_themes t
               LEFT JOIN {C.DBX_SCHEMA}.catalog c ON c.sku_key = t.sku_key
               WHERE t.found = true ORDER BY subcat, t.product_name, t.kind""")
    if df.empty:
        st.info("No mined themes yet — run mine.py.")
        return
    cand = {c["subcat"]: c for c in gaps_mod.candidate_cells()}
    for subcat in df["SUBCAT"].dropna().unique():
        block = df[df["SUBCAT"] == subcat]
        c = cand.get(subcat)
        header = f"#### {subcat}"
        if c:
            header += f" — flagged cell: {c['band']} ({c['kind']}: {c['detail']})"
        st.markdown(header)
        for name in block["PRODUCT_NAME"].unique():
            sub = block[block["PRODUCT_NAME"] == name]
            band = sub["BAND"].iloc[0]
            with st.expander(f"{name}  ·  {band or ''}"):
                for _, r in sub.iterrows():
                    badge = "🔴" if r["KIND"] == "complaint" else "🟢"
                    st.markdown(f"{badge} **{r['THEME']}** — \"{r['QUOTE']}\"")
                    if r["QUOTE_SOURCE_URL"]:
                        st.caption(r["QUOTE_SOURCE_URL"])


def page_teach():
    st.title("🎓 Teach the analyst")
    st.caption("Merchandising rules PATCH the whitespace-verifier agent permanently and "
               "steer the synthesis loop — the self-learning layer, audited below.")
    rule = st.text_area("New merchandising rule",
                        placeholder="Treat sub-$100 espresso as a distinct segment; never propose gaps without a rating threshold.")
    if st.button("Teach", type="primary") and rule:
        import logging
        try:
            agent_id = C.agent_id("whitespace_verifier")
            H = {"Authorization": f"Bearer {C.NIMBLE_API_KEY}"}
            resp = requests.get(f"{C.BASE_URL}/task-agents/{agent_id}", headers=H, timeout=60)
            resp.raise_for_status()
            updated = resp.json()["domain_expertise"].rstrip() + f"\n- {rule.strip()}"
            r = requests.patch(f"{C.BASE_URL}/task-agents/{agent_id}",
                               headers={**H, "Content-Type": "application/json-patch+json"},
                               data=json.dumps([{"op": "replace", "path": "/domain_expertise",
                                                 "value": updated}]), timeout=60)
            r.raise_for_status()
            from datetime import datetime, timezone
            delta.insert_rows("merch_rules", [{"rule": rule.strip(),
                                               "taught_at": datetime.now(timezone.utc)}])
            st.success("The analyst learned it — the rule is now part of the verifier agent.")
        except Exception as e:
            logging.exception("teach failed")
            st.error(f"Teaching failed ({type(e).__name__}) - the agent was not updated; see app logs.")
    rules = q(f"SELECT rule, taught_at FROM {C.DBX_SCHEMA}.merch_rules ORDER BY taught_at DESC")
    if not rules.empty:
        st.markdown("#### What the analyst has learned")
        for _, r in rules.iterrows():
            st.markdown(f"- **{r['RULE']}**")
            st.caption(str(r["TAUGHT_AT"]))


def page_ops():
    st.title("⚙️ Runs")
    df = q(f"""SELECT chunk_id, run_id, status, item_count, wall_clock_s, completed_at
               FROM {C.DBX_SCHEMA}.discovery_runs ORDER BY completed_at DESC""")
    st.dataframe(df, use_container_width=True)


PAGES = {"Catalog & whitespace": page_catalog, "Gap board": page_gaps,
         "Customer evidence": page_evidence, "Teach the analyst": page_teach, "Runs": page_ops}
with st.sidebar:
    st.markdown("## Assortment Gap Finder")
    st.caption("Nimble Web Search Agents")
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    if st.button("🔄 Refresh data"):
        q.clear()
        st.rerun()
    st.caption(f"Mode: {'LIVE' if C.USE_LIVE else 'REPLAY'}")
PAGES[page]()
