"""Earnings Guidance vs Actuals — Streamlit UI over the Snowflake ledger."""
import os

import pandas as pd
import streamlit as st

import ask as ask_mod
import config as C
import slack_post
from setup_snowflake import connect

st.set_page_config(page_title="Earnings Guidance vs Actuals", page_icon="📊", layout="wide")
DB = os.environ.get("SNOWFLAKE_DATABASE", "EARNINGS_DESK")
VERDICT_ICON = {"beat": "🟢 beat", "miss": "🔴 miss", "inline": "🟡 inline", "not_guided": "⚪ n/a"}


@st.cache_resource
def conn():
    return connect()


def live_cursor():
    try:
        cur = conn().cursor()
        cur.execute("SELECT 1")
        return cur
    except Exception:
        conn.clear()
        return conn().cursor()


@st.cache_data(ttl=300)
def q(sql, params=None):
    try:
        cur = conn().cursor()
        cur.execute(sql, params or ())
    except Exception:
        conn.clear()  # session token expired (~4h) or connection dropped - rebuild once
        cur = conn().cursor()
        cur.execute(sql, params or ())
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def page_scorecard():
    st.title("📊 Earnings Guidance vs Actuals")
    st.caption("What management promised vs what landed — every number cited. "
               "Built on Nimble Web Search Agents; the ledger grows with every run.")
    df = q(f"""SELECT ticker, fiscal_quarter, report_date, metric_verdict
               FROM {DB}.LEDGER.V_HEADLINE_DEDUP""")
    if df.empty:
        st.info("Ledger is empty — run backfill.py then ingest.py.")
        return
    # rank quarters per ticker (1 = most recent) so all tickers share columns
    df = df.sort_values("REPORT_DATE", ascending=False)
    df["QRANK"] = df.groupby("TICKER").cumcount() + 1
    df = df[df["QRANK"] <= 8]
    grid = df.pivot_table(index="TICKER", columns="QRANK",
                          values="METRIC_VERDICT", aggfunc="first")
    grid.columns = ["latest" if c == 1 else f"-{c - 1}" for c in grid.columns]
    st.markdown("#### Revenue verdict grid (most recent quarters)")
    st.dataframe(grid.style.map(lambda v: {
        "beat": "background-color:#1b5e20;color:white",
        "miss": "background-color:#b71c1c;color:white",
        "inline": "background-color:#f9a825;color:black"}.get(v, "")), use_container_width=True)

    counts = df.groupby(["TICKER", "METRIC_VERDICT"]).size().unstack(fill_value=0)
    for v in ("beat", "miss", "inline"):
        if v not in counts:
            counts[v] = 0
    counts["record"] = counts.apply(lambda r: f"{r['beat']}W-{r['miss']}L", axis=1)
    st.markdown("#### Track records")
    st.dataframe(counts[["beat", "miss", "inline", "record"]].sort_values("beat", ascending=False),
                 use_container_width=True)


def page_company():
    tickers = q(f"SELECT DISTINCT ticker FROM {DB}.LEDGER.GUIDANCE_LEDGER ORDER BY 1")["TICKER"].tolist()
    if not tickers:
        st.info("Ledger is empty.")
        return
    ticker = st.selectbox("Company", tickers)
    st.title(f"{ticker} — guidance vs delivery")
    df = q(f"""SELECT fiscal_quarter, report_date, metric_raw, guided_range_raw, guided_value_raw,
               actual_value_raw, metric_verdict, quarter_verdict, notes,
               guidance_source_url, actual_source_url
               FROM {DB}.LEDGER.GUIDANCE_LEDGER WHERE ticker = %s
               ORDER BY report_date DESC, metric_raw""", (ticker,))
    headline = q(f"""SELECT fiscal_quarter, metric_verdict, basis
                     FROM {DB}.LEDGER.V_HEADLINE_DEDUP WHERE ticker = %s""", (ticker,))
    hmap = {r["FISCAL_QUARTER"]: (r["METRIC_VERDICT"], r["BASIS"]) for _, r in headline.iterrows()}
    na_share = (headline["METRIC_VERDICT"] == "not_guided").mean() if not headline.empty else 0
    if na_share >= 0.5:
        st.info(f"{ticker} issues little or no formal numeric guidance — verdicts appear only "
                "where management gave a measurable outlook. The quarter notes below record what "
                "management *did* say; grading qualitative commentary would be fabrication.")
    for fq in df["FISCAL_QUARTER"].unique():
        sub = df[df["FISCAL_QUARTER"] == fq]
        head = sub.iloc[0]
        h_verdict, h_basis = hmap.get(fq, (head["QUARTER_VERDICT"], None))
        icon = VERDICT_ICON.get(h_verdict, "⚪")
        title = f"{icon}  {fq} — reported {head['REPORT_DATE']}"
        if h_basis:
            title += f"  ·  {h_basis}"
        with st.expander(title, expanded=False):
            for _, r in sub.iterrows():
                guided = r["GUIDED_RANGE_RAW"] or r["GUIDED_VALUE_RAW"]
                if guided:
                    if r["METRIC_VERDICT"] == "not_guided" and r["ACTUAL_VALUE_RAW"]:
                        verdict_txt = "⚪ not comparable — directional/qualitative outlook"
                    elif r["METRIC_VERDICT"] == "not_guided":
                        verdict_txt = "⚪ actual not located"
                    else:
                        verdict_txt = VERDICT_ICON.get(r["METRIC_VERDICT"], r["METRIC_VERDICT"])
                    st.markdown(f"**{r['METRIC_RAW']}**: guided {guided} → actual "
                                f"{r['ACTUAL_VALUE_RAW'] or '—'}  ({verdict_txt})")
                else:
                    st.markdown(f"**{r['METRIC_RAW']}**: reported {r['ACTUAL_VALUE_RAW'] or '—'} "
                                f"*(not guided)*")
                links = []
                if r["GUIDANCE_SOURCE_URL"]:
                    links.append(f"[guidance source]({r['GUIDANCE_SOURCE_URL']})")
                if r["ACTUAL_SOURCE_URL"]:
                    links.append(f"[actual source]({r['ACTUAL_SOURCE_URL']})")
                if links:
                    st.caption(" · ".join(links))
            if head["NOTES"]:
                st.caption(f"Notes: {head['NOTES']}")

    st.markdown("---")
    claims = q(f"""SELECT confidence, COUNT(*) AS n FROM {DB}.LEDGER.CLAIMS
                   WHERE ticker = %s GROUP BY 1""", (ticker,))
    if not claims.empty:
        st.caption("Evidence: " + " · ".join(
            f"{int(r['N'])} {r['CONFIDENCE']}-confidence claims" for _, r in claims.iterrows()))
    if st.button(f"📣 Post {ticker} scorecard to Slack"):
        webhook = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook:
            st.error("SLACK_WEBHOOK_URL is not set; configure .env to enable Slack posting.")
        else:
            cur = live_cursor()
            rows = slack_post.scorecard(cur, DB, ticker)
            slack_post.post(ticker, rows, webhook)
            st.success("Posted.")


def page_ask():
    st.title("💬 Ask the Desk")
    st.caption("Aggregation questions are answered from the ledger (Claude writes the SQL). "
               "Questions needing new research go back to the live agent — expect 5–10 minutes.")
    tickers = q(f"SELECT DISTINCT ticker FROM {DB}.LEDGER.GUIDANCE_LEDGER ORDER BY 1")["TICKER"].tolist()
    question = st.text_input("Question",
                             placeholder="Who missed revenue guidance most often? / Why did IBM's guidance change?")
    lane_choice = st.radio("Lane", ["auto", "ledger (SQL)", "live agent"], horizontal=True)
    ticker = st.selectbox("Ticker (for live lane)", tickers) if tickers else None
    if st.button("Ask", type="primary") and question:
        lane = {"auto": ask_mod.route(question),
                "ledger (SQL)": "ledger", "live agent": "live"}[lane_choice]
        if lane == "ledger":
            try:
                with st.spinner("Claude is writing SQL and querying the ledger (~30s)…"):
                    sql, cols, rows, answer = ask_mod.ask_ledger(question, live_cursor(), DB)
                if answer:
                    st.markdown(f"**{answer}**")
                st.code(sql, language="sql")
                if rows:
                    st.dataframe(pd.DataFrame(rows, columns=cols), use_container_width=True)
                else:
                    st.info("Query ran but returned no rows — try rephrasing.")
            except Exception as e:
                st.error(f"Ledger lane failed ({e}) — try the live agent lane.")
        else:
            inter = q(f"""SELECT interaction_id FROM {DB}.LEDGER.RUNS WHERE ticker = %s
                          ORDER BY ingested_at DESC LIMIT 1""", (ticker,))
            iid = inter["INTERACTION_ID"].iloc[0] if not inter.empty else None
            with st.status(f"Live research on {ticker}…", expanded=True) as status:
                out = ask_mod.ask_live(question, ticker, iid)
                status.update(label="Done", state="complete")
            content = out["content"]
            st.markdown(content if isinstance(content, str) else st.json(content) or "")
            st.caption(f"confidence: {out['confidence']} · {out['claims']} claims")


PAGES = {"Scorecard": page_scorecard, "Company drill-down": page_company, "Ask the Desk": page_ask}
with st.sidebar:
    st.markdown("## Earnings Desk")
    st.caption("Nimble Web Search Agents")
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    if st.button("🔄 Refresh data"):
        q.clear()
        st.rerun()
    st.caption(f"Mode: {'LIVE' if C.USE_LIVE else 'REPLAY'}")
PAGES[page]()
