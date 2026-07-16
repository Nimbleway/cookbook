"""Diligence Desk — Streamlit UI.

Run: streamlit run app.py
"""
import json
import time

import streamlit as st

import actions
import config as C
import crew
import db
import wsa

st.set_page_config(page_title="Diligence Desk", page_icon="🗂️", layout="wide")

VERDICT_BADGE = {
    "proceed": "🟢 PROCEED",
    "proceed_with_conditions": "🟡 PROCEED WITH CONDITIONS",
    "caution": "🟠 CAUTION",
    "do_not_proceed": "🔴 DO NOT PROCEED",
}
CONF_ICON = {"high": "🟢", "medium": "🟡", "low": "🔴", "pre_existing": "⚪"}
CONF_RANK = {"low": 0, "medium": 1, "high": 2, "pre_existing": 1}

SECTION_LABELS = {
    "executive_summary": "Executive summary", "overall_assessment": "Assessment",
    "financial_health": "Financial health", "leadership": "Leadership",
    "legal_regulatory": "Legal & regulatory", "competitive_position": "Competitive position",
    "operational_risks": "Operational risks", "reputation": "Reputation",
    "risks": "Risks", "opportunities": "Opportunities",
}


def section_of(path):
    if not path or not path.startswith("$."):
        return None
    return path[2:].split(".")[0].split("[")[0]


def section_confidence(claims):
    """Worst-claim-per-section aggregation with counts."""
    sections = {}
    for cl in claims:
        sec = section_of(cl.get("path"))
        if not sec:
            continue
        entry = sections.setdefault(sec, {"worst": "high", "counts": {"high": 0, "medium": 0, "low": 0}})
        conf = cl.get("confidence", "medium")
        if conf in entry["counts"]:
            entry["counts"][conf] += 1
        if CONF_RANK.get(conf, 1) < CONF_RANK.get(entry["worst"], 2):
            entry["worst"] = conf
    return sections


def progress_banner(container, label):
    start = time.time()

    def on_tick(elapsed, status):
        mins, secs = divmod(int(time.time() - start), 60)
        container.info(
            f"⏳ **{label}** — status: `{status}` — {mins}m {secs:02d}s elapsed. "
            "Max-effort research runs take 10–20 minutes; the agent is reading "
            "filings, registries, and press right now."
        )
    return on_tick


def render_memo(memo):
    raw = memo["raw_result"]
    content = raw["output"]["content"]
    claims = db.get_claims(memo["id"])
    trust = raw["output"].get("trust") or {}
    sections = section_confidence(claims)

    left, right = st.columns([3, 1])
    assessment = content.get("overall_assessment") or {}
    with left:
        st.subheader(content.get("company_name") or memo["company"])
        st.markdown(f"### {VERDICT_BADGE.get(assessment.get('verdict'), '⚪ N/A')}")
    with right:
        counts = {"high": 0, "medium": 0, "low": 0}
        for cl in claims:
            if cl.get("confidence") in counts:
                counts[cl["confidence"]] += 1
        st.metric("Cited claims", len(claims))
        st.caption(f"🟢 {counts['high']} high · 🟡 {counts['medium']} medium · 🔴 {counts['low']} low")
        st.caption(f"Overall run confidence: {CONF_ICON.get(trust.get('confidence'), '⚪')} "
                   f"{trust.get('confidence', 'n/a')}")
        st.caption(f"Data as of {content.get('data_as_of_date', 'n/a')}")

    highlights = actions.build_highlights(content)
    if highlights:
        st.markdown("#### At a glance")
        cols = st.columns(2)
        for i, (title, detail) in enumerate(highlights):
            with cols[i % 2]:
                st.markdown(f"**{title}**  \n{detail}")

    st.markdown("---")
    st.markdown("#### Assessment")
    st.markdown(assessment.get("rationale", ""))
    for cond in assessment.get("conditions") or []:
        st.markdown(f"- ⚠️ {cond}")

    st.markdown("#### Executive summary")
    st.markdown(content.get("executive_summary", ""))

    if memo.get("memo_narrative"):
        with st.expander("Analyst narrative (Crew editor)", expanded=False):
            st.markdown(memo["memo_narrative"])

    body_sections = [
        ("financial_health", "Financial health"), ("leadership", "Leadership"),
        ("legal_regulatory", "Legal & regulatory"), ("competitive_position", "Competitive position"),
        ("risks", "Risks"), ("operational_risks", "Operational risks"),
        ("opportunities", "Opportunities"), ("reputation", "Reputation"),
    ]
    for key, label in body_sections:
        value = content.get(key)
        if not value:
            continue
        sec = sections.get(key)
        badge = ""
        if sec:
            badge = (f" {CONF_ICON[sec['worst']]} `{sec['worst']}` "
                     f"({sec['counts']['high']}h/{sec['counts']['medium']}m/{sec['counts']['low']}l)")
        with st.expander(f"{label}{badge}", expanded=key == "risks"):
            if key == "risks":
                for r in value:
                    if isinstance(r, dict):
                        sev = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(r.get("severity"), "⚪")
                        st.markdown(f"{sev} **{r.get('risk')}**")
                        if r.get("evidence"):
                            st.caption(r["evidence"])
                    else:
                        st.markdown(f"- {r}")
            elif key == "leadership":
                for p in value:
                    link = f" · [LinkedIn]({p['linkedin_url']})" if p.get("linkedin_url") else ""
                    st.markdown(f"**{p.get('name')}** — {p.get('title')}{link}")
                    st.caption(p.get("background", ""))
                    if p.get("flags"):
                        st.warning(p["flags"])
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v:
                        st.markdown(f"**{k.replace('_', ' ').title()}**: {v}")
            elif isinstance(value, list):
                for item in value:
                    st.markdown(f"- {item}")
            else:
                st.markdown(str(value))

    gaps = memo.get("evidence_gaps")
    if gaps:
        st.markdown("#### 🔍 Evidence gaps (Risk Officer)")
        st.caption("Load-bearing claims that rest on weak evidence — verify by hand before acting.")
        for gap in gaps:
            st.markdown(f"- `{gap.get('field')}` — {gap.get('issue')} "
                        f"*→ {gap.get('recommendation')}*")

    with st.expander(f"🧾 Trust panel — every claim and its citations ({len(claims)})"):
        for cl in claims:
            if not cl.get("path"):
                continue
            st.markdown(f"{CONF_ICON.get(cl.get('confidence'), '⚪')} `{cl['path']}`")
            for cit in (cl.get("citations") or [])[:3]:
                excerpt = (cit.get("excerpts") or [""])[0][:180]
                st.caption(f"[{cit.get('title') or cit.get('url')}]({cit.get('url')}) — {excerpt}")

    # ---- Actions ----
    st.markdown("---")
    st.markdown("#### Act on this memo")
    col_pdf, col_mail = st.columns(2)
    with col_pdf:
        if st.button("📄 Generate PDF memo", key=f"pdf_{memo['id']}"):
            path = actions.build_pdf(content, memo.get("memo_narrative"),
                                     gaps or [], claims, memo["company"])
            db.save_actions(memo["id"], pdf_path=path)
            st.session_state[f"pdf_path_{memo['id']}"] = str(path)
        pdf_path = st.session_state.get(f"pdf_path_{memo['id']}") or memo.get("pdf_path")
        if pdf_path:
            try:
                with open(pdf_path, "rb") as fh:
                    st.download_button("⬇️ Download memo PDF", fh.read(),
                                       file_name=pdf_path.split("/")[-1],
                                       mime="application/pdf", key=f"dl_{memo['id']}")
            except FileNotFoundError:
                st.caption("PDF file missing — regenerate.")
    with col_mail:
        recipients = st.text_input("Email the memo to (comma-separated)",
                                   key=f"to_{memo['id']}",
                                   placeholder="partner@firm.com, deal-team@firm.com")
        if st.button("✉️ Send memo", key=f"send_{memo['id']}") and recipients:
            pdf_path = st.session_state.get(f"pdf_path_{memo['id']}") or memo.get("pdf_path")
            if not pdf_path:
                pdf_path = str(actions.build_pdf(content, memo.get("memo_narrative"),
                                                 gaps or [], claims, memo["company"]))
                db.save_actions(memo["id"], pdf_path=pdf_path)
            to = [t.strip() for t in recipients.split(",") if t.strip()]
            outcome = actions.send_email(pdf_path, to, content, memo["company"])
            if outcome["sent"]:
                db.save_actions(memo["id"], emailed_to=to)
                st.success(f"Sent to {', '.join(to)} (Resend id {outcome.get('id')})")
            else:
                st.info(f"Email preview ({outcome['reason']}):")
                st.code(outcome["html"], language="html")

    # ---- Follow-up Q&A ----
    st.markdown("---")
    st.markdown("#### Ask the analyst anything")
    st.caption("Follow-ups go back to the live agent with the memo's research context — "
               "this is new research, not chat over stored data. Expect 5–10 minutes.")
    for fu in db.get_followups(memo["id"]):
        st.markdown(f"**Q: {fu['question']}**")
        st.markdown(fu.get("answer") or "")
        for kp in fu.get("key_points") or []:
            st.markdown(f"- {kp}")
    question = st.text_input("Follow-up question", key=f"q_{memo['id']}",
                             placeholder="How exposed are they to the pending copyright rulings?")
    if st.button("Ask", key=f"ask_{memo['id']}") and question:
        banner = st.empty()
        n_existing = len(db.get_followups(memo["id"]))
        try:
            raw_fu, run_fu = wsa.run_followup(
                question, memo.get("interaction_id"), followup_index=n_existing,
                on_tick=progress_banner(banner, "Researching your question"))
            banner.empty()
            db.save_followup(memo["id"], question, raw_fu, run_fu)
            st.rerun()
        except wsa.RunFailed as exc:
            banner.error(f"Follow-up failed: {exc}")


def page_new_memo():
    st.title("🗂️ Diligence Desk")
    st.caption("Audit-grade diligence memos on Nimble Web Search Agents — "
               "every claim cited, every verdict evidenced."
               + ("" if C.USE_LIVE else "  ·  🎬 REPLAY MODE — cached data"))
    prompt = st.text_area(
        "Who are we diligencing?",
        placeholder='e.g. "Due diligence on Perplexity AI (perplexity.ai) for a strategic investment"',
        height=80)
    company = st.text_input("Company label (for files and history)",
                            placeholder="Perplexity AI")
    auto_email = st.text_input(
        "✉️ Email the finished memo to (optional, comma-separated)",
        placeholder="you@firm.com — PDF is generated and sent the moment the memo is ready")
    if st.button("Run diligence", type="primary") and prompt and company:
        memo_id = db.create_memo(company, prompt)
        banner = st.empty()
        try:
            raw, run = wsa.run_memo(prompt, cache_key=company, on_tick=progress_banner(
                banner, f"Researching {company}"))
        except wsa.RunFailed as exc:
            banner.error(f"Run failed: {exc}. You can retry — this memo is logged as failed.")
            db.fail_memo(memo_id, str(exc))
            return
        db.save_memo_result(memo_id, raw, run)
        banner.info("🧠 Research done — Crew review in progress (QA → Risk Officer → Editor)…")
        content = raw["output"]["content"]
        claims = (raw["output"].get("trust") or {}).get("claims") or []
        crew_out = crew.run_crew(content, claims)
        db.save_crew_output(memo_id, crew_out["narrative"], crew_out["evidence_gaps"])

        recipients = [t.strip() for t in (auto_email or "").split(",") if t.strip()]
        if recipients:
            banner.info("📄 Generating the PDF memo and sending it…")
            pdf_path = actions.build_pdf(content, crew_out["narrative"],
                                         crew_out["evidence_gaps"], claims, company)
            db.save_actions(memo_id, pdf_path=str(pdf_path))
            outcome = actions.send_email(str(pdf_path), recipients, content, company)
            if outcome["sent"]:
                db.save_actions(memo_id, emailed_to=recipients)
                st.toast(f"Memo emailed to {', '.join(recipients)}")
            else:
                st.toast(f"Email not sent ({outcome['reason']}) — PDF saved locally")
        banner.success("Memo ready.")
        st.session_state["view_memo"] = memo_id
        st.rerun()


def page_memos():
    st.title("📁 Memos")
    memos = db.list_memos()
    if not memos:
        st.info("No memos yet — run your first diligence from the New memo page.")
        return
    options = {f"#{m['id']} · {m['company']} · {m['status']}"
               f" · {(m.get('verdict') or '').replace('_', ' ')}": m["id"] for m in memos}
    default_id = st.session_state.get("view_memo")
    keys = list(options)
    index = next((i for i, k in enumerate(keys) if options[k] == default_id), 0)
    choice = st.selectbox("Memo", keys, index=index)
    memo = db.get_memo(options[choice])
    if memo["status"] != "completed":
        st.warning(f"Status: {memo['status']}")
        if memo.get("memo_narrative"):
            st.caption(memo["memo_narrative"])
        return
    render_memo(memo)


def page_teach():
    st.title("🎓 Teach the analyst")
    st.caption("Standing instructions PATCH the agent's expertise permanently — "
               "every future memo honors them. This is the self-learning loop, audited.")
    instruction = st.text_area(
        "New standing instruction",
        placeholder="Always check EU regulatory exposure for companies with European operations.")
    if st.button("Teach", type="primary") and instruction:
        before, after = wsa.teach(instruction)
        db.save_agent_update(instruction, before, after)
        st.success("The analyst learned it — the instruction is now part of the agent.")
    updates = db.list_agent_updates()
    if updates:
        st.markdown("#### What the analyst has learned")
        for up in updates:
            st.markdown(f"- **{up['instruction']}**")
            st.caption(up["created_at"])
        with st.expander("Current standing-instructions section (after last update)"):
            after = updates[0]["expertise_after"]
            section = after.split(C.STANDING_INSTRUCTIONS_HEADER)[-1]
            st.code(C.STANDING_INSTRUCTIONS_HEADER + section, language="markdown")


PAGES = {"New memo": page_new_memo, "Memos": page_memos, "Teach the analyst": page_teach}

with st.sidebar:
    st.markdown("## Diligence Desk")
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    st.caption(f"Mode: {'🌐 LIVE' if C.USE_LIVE else '🎬 REPLAY (cached)'}")
    if C.AGENT_FILE.exists():
        st.caption(f"Agent: `{json.loads(C.AGENT_FILE.read_text())['agent_id'][:16]}…`")

PAGES[page]()
