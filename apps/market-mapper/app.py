"""Market Mapper — Streamlit UI."""
import os

import pandas as pd
import streamlit as st

import mapper

st.set_page_config(page_title="Market Mapper", page_icon="🗺️", layout="wide")

CONF_BADGE = {"high": "🟢 high", "medium": "🟡 medium", "low": "🔴 low", "pre_existing": "⚪ pre-existing"}

st.title("🗺️ Market Mapper")
st.caption("Map the universe of companies fitting your ICP — every field cited, powered by Nimble Web Search Agents.")
if not mapper.USE_LIVE:
    st.warning("Replaying sample data (USE_LIVE=false) — no live API calls are being made.", icon="🎬")

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Map a market")
    icp = st.text_area("Describe your ICP", height=120, placeholder=(
        "AI-powered vertical SaaS companies in healthcare, 11-200 employees, "
        "US or Israel, Series A or later"))
    exclude_file = st.file_uploader("Exclusion list (optional)", type=["csv", "txt"],
                                    help="One domain per line — companies already in your CRM.")
    max_employees = st.number_input("Max employees (post-hoc check)", min_value=0, value=0,
                                    help="0 = off. Rows above the bound are flagged, not dropped.")
    start = st.button("Map the market", type="primary", use_container_width=True, disabled=not icp)

    st.divider()
    runs = mapper.list_runs()
    options = {f"{r['created_at'][:16]} · {r['icp_prompt'][:48]}": r["id"] for r in runs}
    picked = st.selectbox("Or load a previous map", ["—"] + list(options))

# ------------------------------------------------------------------ actions
if start:
    exclude = []
    if exclude_file:
        exclude = [ln.strip() for ln in exclude_file.read().decode().splitlines() if ln.strip()]
    with st.status("Mapping the market — the agent is searching…", expanded=True) as box:
        def on_status(status, elapsed):
            box.update(label=f"Discovery run: {status} · {elapsed}s")
        run_id = mapper.map_market(icp, exclude, max_employees or None, on_status=on_status)
        st.session_state["run_id"] = run_id
        box.update(label="Discovery complete", state="complete")

if picked != "—":
    st.session_state["run_id"] = options[picked]

run_id = st.session_state.get("run_id")
if not run_id:
    st.info("Describe an ICP and click **Map the market**, or load a previous map.")
    st.stop()

run = mapper.get_run(run_id)
companies = mapper.get_companies(run_id)

if run["status"] == "running":
    st.info("This map is still being discovered — the agent is researching (runs take several minutes). "
            "Companies appear here the moment discovery completes.", icon="⏳")
    if st.button("Refresh"):
        st.rerun()
    if not companies:
        st.stop()

# ------------------------------------------------------------------ stats row
enriched = [c for c in companies if c["enrich_status"] == "enriched"]
high_conf = [c for c in enriched if c.get("enrichment_confidence") == "high"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Companies mapped", len(companies))
c2.metric("Enriched", len(enriched))
c3.metric("High confidence", len(high_conf))
c4.metric("Flagged (size)", sum(1 for c in companies if c.get("size_flag")))

# ------------------------------------------------------------------ controls
b1, b2, _ = st.columns([1, 1, 2])
if b1.button(f"Enrich next {mapper.ENRICH_CAP}", use_container_width=True,
             disabled=all(c["enrich_status"] != "pending" for c in companies)):
    prog = st.progress(0.0, "Enriching…")
    state = {"done": 0}
    def on_event(domain, status):
        state["done"] += 1
        prog.progress(min(state["done"] / mapper.ENRICH_CAP, 1.0), f"{domain}: {status}")
    mapper.enrich_pending(run_id, on_event=on_event)
    st.rerun()

if b2.button("Expand the map (+10)", use_container_width=True,
             disabled=not run.get("interaction_id"),
             help="Re-runs the mapper with previous_interaction_id — same ICP context, new companies."):
    with st.status("Expanding the map…") as box:
        added = mapper.expand_map(run_id, on_status=lambda s, t: box.update(label=f"{s} · {t}s"))
        box.update(label=f"Added {added} companies", state="complete")
    st.rerun()

# ------------------------------------------------------------------ table + detail
tab_map, tab_chat = st.tabs(["Map", "Chat"])

with tab_map:
    only_high = st.toggle("High-confidence only")
    view = [c for c in companies if not only_high or c.get("enrichment_confidence") == "high"]
    df = pd.DataFrame([{
        "Company": c["company_name"], "Domain": c["domain"], "HQ": c.get("headquarters"),
        "Size": (c.get("employee_count") or "") + (" ⚠️" if c.get("size_flag") else ""),
        "Funding": c.get("funding_stage") or c.get("recent_funding"),
        "Fit reason": c.get("icp_fit_reason"),
        "Trust": CONF_BADGE.get(c.get("enrichment_confidence"), "· pending"),
    } for c in view])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", pd.DataFrame(view).to_csv(index=False), "market_map.csv")

    names = [c["company_name"] for c in view if c["enrich_status"] == "enriched"]
    if names:
        sel = st.selectbox("Company detail", names)
        c = next(x for x in view if x["company_name"] == sel)
        left, right = st.columns(2)
        with left:
            st.subheader(c["company_name"])
            st.write(c.get("summary") or "")
            st.write(f"**Funding:** {c.get('funding_stage')} · {c.get('total_funding')}")
            st.write(f"**Headcount:** {c.get('headcount_estimate')}")
            st.write("**Tech stack:**", ", ".join(c.get("tech_stack") or []))
            st.write("**Buying signals:**")
            for s in c.get("buying_signals") or []:
                st.write(f"- {s}")
        with right:
            st.subheader("Contacts")
            for k in c.get("key_contacts") or []:
                st.write(f"- **{k.get('name')}** — {k.get('title')}"
                         + (f" · [LinkedIn]({k['linkedin_url']})" if k.get("linkedin_url") else ""))
            st.subheader("Per-field trust")
            for field, f in (c.get("claims") or {}).items():
                badge = CONF_BADGE.get(f.get("confidence"), f.get("confidence"))
                levels = f.get("by_level") or {}
                breakdown = (f" ({levels.get('medium', 0) + levels.get('low', 0)} of {f['n_claims']} claims below high)"
                             if f.get("n_claims", 0) > 1 and len(levels) > 1 else "")
                st.write(f"- `{field}` — {badge}{breakdown}")
                for url in (f.get("citations") or [])[:2]:
                    st.caption(f"    ↳ {url}")

with tab_chat:
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.info("Chat is disabled — add ANTHROPIC_API_KEY to .env to enable it.")
    else:
        if "chat_log" not in st.session_state:
            st.session_state.chat_log = []
        for role, msg in st.session_state.chat_log:
            st.chat_message(role).write(msg)
        if q := st.chat_input("Ask about this market — e.g. 'who raised most recently?'"):
            st.chat_message("user").write(q)
            answer = mapper.chat(q, companies)
            st.chat_message("assistant").write(answer)
            st.session_state.chat_log += [("user", q), ("assistant", answer)]
