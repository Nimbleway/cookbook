import json
from typing import Optional
import pandas as pd
import streamlit as st

from agent import get_search_agent, parse_leads, score_leads, chat_with_leads, get_full_records

st.set_page_config(page_title="Lead Generation Agent", page_icon="🎯", layout="wide")

st.title("🎯 Lead Generation Agent")
st.caption("Powered by Nimble + LangChain")

# ── Session state ──────────────────────────────────────────────────────────────

for key, default in [
    ("leads", []),
    ("leads_by_title", {}),
    ("scores", {}),          # {title: {score, reason}}
    ("all_results", []),
    ("extraction_status", {}),
    ("selected_bizzes", []),
    ("last_query", ""),
    ("chat_history", []),    # [{role, content}]
    ("search_agent", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.search_agent is None:
    st.session_state.search_agent = get_search_agent()


# ── Card helpers ───────────────────────────────────────────────────────────────

def labeled(label: str, value: str):
    st.markdown(
        f"<div style='margin-bottom:10px'>"
        f"<div style='font-size:0.68em;text-transform:uppercase;letter-spacing:0.08em;"
        f"color:#888;margin-bottom:2px'>{label}</div>"
        f"<div style='font-size:0.9em'>{value}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def chips(items: list):
    if not items:
        return
    labels = []
    for item in items:
        if isinstance(item, dict):
            if item.get("is_available"):
                labels.append(item.get("display_name", ""))
        else:
            labels.append(str(item))
    labels = [l for l in labels if l]
    if not labels:
        return
    html = "".join(
        f"<span style='display:inline-block;background:#1e293b;border:1px solid #334155;"
        f"border-radius:12px;padding:2px 10px;font-size:0.72em;margin:2px 2px 2px 0;"
        f"color:#94a3b8'>{label}</span>"
        for label in labels
    )
    st.markdown(html, unsafe_allow_html=True)


def score_color(score: int) -> str:
    if score >= 8:
        return "#22c55e"
    if score >= 5:
        return "#edc602"
    return "#ef4444"


# ── Card rendering ─────────────────────────────────────────────────────────────

def render_single_card(
    biz: dict,
    status: str,
    lead_data: Optional[dict] = None,
    score_data: Optional[dict] = None,
):
    status_cfg = {
        "pending": ("⏳", "Pending",   "#2a2a1a"),
        "done":    ("✅", "Extracted", "#0f2318"),
        "failed":  ("❌", "Failed",    "#2a0f0f"),
    }
    icon, label, badge_bg = status_cfg.get(status, ("⏳", "Pending", "#2a2a1a"))
    score = score_data.get("score") if score_data else None

    with st.container(border=True):
        # Header
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"### {biz.get('title', '')}")
            st.caption(f"📍 {biz.get('address', '')}")
        with right:
            if score is not None:
                color = score_color(score)
                st.markdown(
                    f"<div style='background:{color};color:#000;border-radius:50%;"
                    f"width:42px;height:42px;display:flex;align-items:center;"
                    f"justify-content:center;font-weight:bold;font-size:1.1em;"
                    f"margin-left:auto'>{score}</div>",
                    unsafe_allow_html=True,
                )
            else:
                rating = biz.get("rating", "")
                reviews = biz.get("number_of_reviews", "")
                if rating:
                    st.markdown(f"⭐ **{rating}**")
                if reviews:
                    st.caption(f"{reviews} reviews")
            st.markdown(
                f"<div style='background:{badge_bg};border-radius:6px;padding:2px 8px;"
                f"font-size:0.75em;margin-top:4px;display:inline-block'>{icon} {label}</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # Key fields
        c1, c2, c3 = st.columns(3)
        with c1:
            labeled("📞 Phone", biz.get("phone_number") or "—")
        with c2:
            cats = biz.get("business_category", [])
            labeled("🏷️ Category", ", ".join(cats[:2]) if cats else "—")
        with c3:
            bstatus = biz.get("business_status", "").replace("_", " ").title()
            labeled("🟢 Business Status", bstatus or "—")

        if status == "done":
            with st.expander("View details"):
                lead = lead_data or {}

                # Score reason
                if score_data:
                    reason = score_data.get("reason", "")
                    color = score_color(score_data.get("score", 5))
                    st.markdown(
                        f"<div style='background:{color}22;border-left:3px solid {color};"
                        f"padding:8px 12px;border-radius:4px;margin-bottom:12px'>"
                        f"🎯 <strong>Score {score_data.get('score')}/10</strong> — {reason}</div>",
                        unsafe_allow_html=True,
                    )

                # Contact
                st.markdown("**Contact**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    labeled("📧 Email", lead.get("email") or "Not found")
                with c2:
                    labeled("📞 Phone", biz.get("phone_number") or "—")
                with c3:
                    website = biz.get("website_url", "")
                    if website:
                        domain = website.split("//")[-1].rstrip("/")
                        labeled("🌐 Website", f'<a href="{website}" target="_blank">{domain}</a>')
                    else:
                        labeled("🌐 Website", "—")

                # About
                desc = lead.get("description", "")
                if desc:
                    st.divider()
                    st.markdown("**About**")
                    st.write(desc)

                # Location
                st.divider()
                st.markdown("**Location**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    labeled("🏙️ City", biz.get("city") or "—")
                with c2:
                    labeled("📮 Zip", biz.get("zip_code") or "—")
                with c3:
                    price = biz.get("price_level", "")
                    labeled("💰 Price Level", price or "—")

                # Lead attributes
                attr_sections = [
                    ("✨ Highlights",     biz.get("highlights", [])),
                    ("🌿 Atmosphere",     biz.get("atmosphere", [])),
                    ("☕ Offerings",      biz.get("offerings", [])),
                    ("🍳 Dining Options", biz.get("dining_options", [])),
                    ("♿ Accessibility",  biz.get("accessibility", [])),
                    ("🛎️ Amenities",     biz.get("amenities", [])),
                    ("💳 Payments",      biz.get("payments", [])),
                    ("🔥 Popular For",   biz.get("popular_for", [])),
                    ("📋 Services",      biz.get("services", [])),
                    ("👥 Crowd",         biz.get("crowd", [])),
                    ("🗓️ Planning",      biz.get("planning", [])),
                ]
                visible = [(t, items) for t, items in attr_sections if items]
                if visible:
                    st.divider()
                    st.markdown("**Lead Attributes**")
                    for t, items in visible:
                        st.caption(t)
                        chips(items)

                place_url = biz.get("place_url", "")
                if place_url:
                    st.divider()
                    st.markdown(f"[Open in Google Maps ↗]({place_url})")


def render_cards_grid(placeholder, selected_bizzes, extraction_status, leads_by_title, scores):
    if not selected_bizzes:
        return
    # Sort by score descending when scores are available
    def sort_key(b):
        s = scores.get(b.get("title", {}), {})
        return -(s.get("score", 0) if s else 0)

    ordered = sorted(selected_bizzes, key=sort_key) if scores else selected_bizzes

    with placeholder.container():
        st.subheader(f"Businesses — {len(selected_bizzes)} extracted")
        for i in range(0, len(ordered), 2):
            row = ordered[i : i + 2]
            cols = st.columns(2)
            for j, biz in enumerate(row):
                title = biz.get("title", "")
                url = biz.get("website_url", "")
                with cols[j]:
                    render_single_card(
                        biz,
                        extraction_status.get((title, url), "pending"),
                        leads_by_title.get(title),
                        scores.get(title),
                    )


# ── Streaming ──────────────────────────────────────────────────────────────────

def stream_agent(agent, prompt: str, status_line, cards_placeholder) -> list:
    leads = []
    selected_bizzes = []
    extraction_status = {}   # (title, url) → "pending"/"done"/"failed"
    leads_by_title = {}
    tool_id_to_title = {}    # tc_id → [(title, url), ...]
    seen_keys = set()        # (title, url) pairs already added as cards
    bizz_by_url = {}
    for r in st.session_state.all_results:
        url = r.get("website_url")
        if url:
            bizz_by_url.setdefault(url, []).append(r)

    for chunk in agent.stream(
        {"messages": [("user", prompt)]},
        config={"recursion_limit": 100},
        stream_mode="updates",
    ):
        if "agent" in chunk:
            msg = chunk["agent"]["messages"][0]
            tool_calls = getattr(msg, "tool_calls", []) or []

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", "")

                if name == "search_google_maps":
                    status_line.info(f"🔍 Searching Google Maps for **{args.get('query', '')}**...")

                elif name == "nimble_extract":
                    url = args.get("url", "")
                    bizzes = bizz_by_url.get(url) or [{
                        "title": url.split("//")[-1].split("/")[0],
                        "address": "", "rating": "", "phone_number": "",
                        "business_category": [], "website_url": url,
                    }]
                    tc_pairs = []
                    for biz in bizzes:
                        title = biz["title"]
                        key = (title, url)
                        tc_pairs.append(key)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            selected_bizzes.append(biz)
                            extraction_status[key] = "pending"
                    tool_id_to_title[tc_id] = tc_pairs

            if any(tc.get("name") == "nimble_extract" for tc in tool_calls):
                render_cards_grid(cards_placeholder, selected_bizzes, extraction_status, leads_by_title, {})

            content = getattr(msg, "content", "")
            if content and not tool_calls:
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                    )
                leads = parse_leads(content)
                leads_by_title = {l["title"]: l for l in leads}
                render_cards_grid(cards_placeholder, selected_bizzes, extraction_status, leads_by_title, {})

        elif "tools" in chunk:
            for msg in chunk["tools"]["messages"]:
                tool_name = getattr(msg, "name", "")
                tc_id = getattr(msg, "tool_call_id", "")

                if tool_name == "search_google_maps":
                    try:
                        raw = json.loads(msg.content)
                        with_sites = sum(1 for r in raw if r.get("website_url"))
                        status_line.info(f"✅ Found {len(raw)} businesses — {with_sites} have websites")
                        # Build all_results from full raw records (all fields, incl. place_information)
                        full = get_full_records()
                        store = full if full else raw
                        st.session_state.all_results = []
                        bizz_by_url = {}
                        for r in store:
                            place_info = r.get("place_information") or {}
                            entry = dict(r)
                            if not entry.get("website_url"):
                                entry["website_url"] = place_info.get("website_url")
                            st.session_state.all_results.append(entry)
                            u = entry.get("website_url")
                            if u:
                                bizz_by_url.setdefault(u, []).append(entry)
                    except Exception:
                        pass

                elif tool_name == "nimble_extract":
                    pairs = tool_id_to_title.get(tc_id, [])
                    updated = [k for k in pairs if k in extraction_status]
                    for key in updated:
                        extraction_status[key] = "done"
                    if updated:
                        render_cards_grid(cards_placeholder, selected_bizzes, extraction_status, leads_by_title, {})
                        done = sum(1 for v in extraction_status.values() if v == "done")
                        total = len(extraction_status)
                        status_line.info(f"✅ Extracted {done}/{total}: **{updated[0][0]}**")

    # Store selected_bizzes in session state so scoring can re-render correctly
    st.session_state.selected_bizzes = selected_bizzes
    st.session_state.extraction_status = extraction_status
    return leads


# ── Page layout ────────────────────────────────────────────────────────────────

query = st.text_input("Search query", value="independent coffee shops in Nashville, TN")
find_btn = st.button("🔍 Find Leads", type="primary")

# Status line — single updating line, above cards
status_line = st.empty()

# Cards grid placeholder
cards_placeholder = st.empty()

# Restore cards from previous run
if st.session_state.selected_bizzes:
    render_cards_grid(
        cards_placeholder,
        st.session_state.selected_bizzes,
        st.session_state.extraction_status,
        st.session_state.leads_by_title,
        st.session_state.scores,
    )

# ── Find Leads ─────────────────────────────────────────────────────────────────

if find_btn and query:
    st.session_state.leads = []
    st.session_state.leads_by_title = {}
    st.session_state.scores = {}
    st.session_state.all_results = []
    st.session_state.extraction_status = {}
    st.session_state.selected_bizzes = []
    st.session_state.chat_history = []
    st.session_state.last_query = query
    cards_placeholder.empty()

    leads = stream_agent(
        st.session_state.search_agent,
        f"Find leads for: {query}",
        status_line,
        cards_placeholder,
    )
    st.session_state.leads = leads
    st.session_state.leads_by_title = {l["title"]: l for l in leads}

    # ── Auto-scoring ──────────────────────────────────────────────────────────
    if leads:
        status_line.info(f"🎯 Scoring {len(leads)} leads...")
        scored = score_leads(leads)
        scores = {s["title"]: s for s in scored if "title" in s}
        st.session_state.scores = scores
        render_cards_grid(
            cards_placeholder,
            st.session_state.selected_bizzes,
            st.session_state.extraction_status,
            st.session_state.leads_by_title,
            scores,
        )
        top = max(scored, key=lambda s: s.get("score", 0), default={})
        status_line.success(
            f"✅ Done — {len(leads)} leads enriched & scored. "
            f"Top pick: **{top.get('title', '')}** ({top.get('score', '')}/10)"
        )

# ── Chat ───────────────────────────────────────────────────────────────────────

if st.session_state.leads:
    st.divider()
    st.subheader("💬 Chat with your leads")
    st.caption("Ask anything about the leads — scores, attributes, comparisons, recommendations.")

    # Render chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_input := st.chat_input("e.g. Which leads have outdoor seating? Who scored highest?"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        all_by_title = {r.get("title"): r for r in st.session_state.all_results}
        leads_context = json.dumps(
            [
                {
                    **all_by_title.get(lead["title"], {}),
                    **lead,
                    "score": st.session_state.scores.get(lead["title"], {}).get("score"),
                    "score_reason": st.session_state.scores.get(lead["title"], {}).get("reason"),
                }
                for lead in st.session_state.leads
            ],
            indent=2,
        )
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = chat_with_leads(user_input, leads_context, st.session_state.chat_history[:-1])
            st.write(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})

# ── Results table ──────────────────────────────────────────────────────────────

if st.session_state.leads:
    st.divider()
    st.subheader(f"📋 {len(st.session_state.leads)} Leads")

    rows = []
    for lead in st.session_state.leads:
        score_info = st.session_state.scores.get(lead["title"], {})
        rows.append({**lead, "score": score_info.get("score"), "score_reason": score_info.get("reason")})

    df = pd.DataFrame(rows)
    col_order = ["title", "score", "address", "phone_number", "rating", "email", "opening_hours", "website_url", "description", "score_reason"]
    df = df[[c for c in col_order if c in df.columns]]
    if "score" in df.columns:
        df = df.sort_values("score", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️ Download CSV",
        csv,
        file_name=f"leads_{st.session_state.last_query.replace(' ', '_')[:40]}.csv",
        mime="text/csv",
    )
