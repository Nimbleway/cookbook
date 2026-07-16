"""The "DO something" layer: PDF memo generation and email delivery."""
import base64
import html
import os
import re
from datetime import date

from fpdf import FPDF

import config as C

VERDICT_COLORS = {
    "proceed": (46, 125, 50),
    "proceed_with_conditions": (237, 198, 2),
    "caution": (230, 126, 34),
    "do_not_proceed": (192, 57, 43),
}

_REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "•": "-", "…": "...",
    " ": " ",
}


def _clean(text):
    """fpdf core fonts are latin-1; normalize the usual unicode suspects."""
    if text is None:
        return ""
    text = str(text)
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


_WORD_FIXES = {"linkedin": "LinkedIn", "url": "URL", "arr": "ARR", "hq": "HQ",
               "sec": "SEC", "ceo": "CEO", "usd": "USD"}


def humanize_path(path):
    """'$.leadership[1].linkedin_url' -> 'Leadership 2 · LinkedIn URL'."""
    if not path or not str(path).startswith("$."):
        return str(path or "")
    parts = []
    for name, idx in re.findall(r"([a-zA-Z_]+)(?:\[(\d+)\])?", path[2:]):
        words = [_WORD_FIXES.get(w, w) for w in name.split("_")]
        label = " ".join(words)
        label = label[0].upper() + label[1:]
        parts.append(f"{label} {int(idx) + 1}" if idx else label)
    return " · ".join(parts)


def _first_sentence(text, limit=200):
    text = str(text or "").strip()
    if not text:
        return ""
    for end in (". ", "; "):
        pos = text.find(end)
        if 40 <= pos <= limit:
            return text[:pos + 1]
    return text[:limit].rsplit(" ", 1)[0] + ("..." if len(text) > limit else "")


def build_highlights(content):
    """Derive the at-a-glance rows from the memo's structured fields."""
    rows = []
    fin = content.get("financial_health") or {}
    money = " · ".join(_first_sentence(v, limit=110)
                       for v in (fin.get("revenue"), fin.get("last_round") or fin.get("funding_total")) if v)
    if money:
        rows.append(("Financials", money))
    if fin.get("growth"):
        rows.append(("Growth", _first_sentence(fin["growth"])))
    risks = [r for r in (content.get("risks") or []) if isinstance(r, dict)]
    if risks:
        top = sorted(risks, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("severity"), 1))[0]
        rows.append((f"Top risk ({top.get('severity', '')})", _first_sentence(top.get("risk"))))
    legal = (content.get("legal_regulatory") or {})
    if legal.get("summary") or legal.get("litigation"):
        rows.append(("Legal", _first_sentence(legal.get("summary") or legal.get("litigation"))))
    comp = content.get("competitive_position") or {}
    if comp.get("market_position") or comp.get("main_competitors"):
        detail = _first_sentence(comp.get("market_position")) or \
            "Competes with " + ", ".join(comp.get("main_competitors")[:4])
        rows.append(("Market", detail))
    lead = [p for p in (content.get("leadership") or []) if isinstance(p, dict)]
    if lead:
        flags = sum(1 for p in lead if p.get("flags"))
        detail = f"{lead[0].get('name')} ({lead[0].get('title')}) and {len(lead) - 1} other profiled executives"
        if flags:
            detail += f" - {flags} with flags noted"
        rows.append(("Leadership", detail))
    return rows[:6]


class MemoPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, "Diligence Desk - confidential", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 6, f"{self.page_no()}", align="C")

    def h2(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 20, 20)
        self.ln(3)
        self.cell(0, 8, _clean(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(237, 198, 2)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.l_margin + 40, self.get_y())
        self.ln(2)

    def body(self, text, size=10):
        self.set_font("Helvetica", "", size)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, _clean(text))
        self.ln(1)

    def kv(self, key, value):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(42, 5.5, _clean(key))
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, _clean(value if value not in (None, "") else "-"),
                        new_x="LMARGIN", new_y="NEXT")


def build_pdf(content, narrative, evidence_gaps, claims, company):
    """Render the memo PDF; returns the file path."""
    pdf = MemoPDF()
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()

    # Cover block
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, _clean(f"Diligence Memo: {content.get('company_name') or company}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _clean(f"Data as of {content.get('data_as_of_date') or date.today().isoformat()}"
                          f"  -  generated by Diligence Desk on Nimble Web Search Agents"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    assessment = content.get("overall_assessment") or {}
    verdict = assessment.get("verdict", "caution")
    r, g, b = VERDICT_COLORS.get(verdict, (100, 100, 100))
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(pdf.get_string_width(verdict.replace("_", " ").upper()) + 12, 9,
             _clean(verdict.replace("_", " ").upper()), fill=True, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    counts = {"high": 0, "medium": 0, "low": 0}
    for cl in claims:
        if cl.get("confidence") in counts:
            counts[cl["confidence"]] += 1
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, _clean(f"Evidence base: {len(claims)} cited claims - "
                          f"{counts['high']} high / {counts['medium']} medium / {counts['low']} low confidence"),
             new_x="LMARGIN", new_y="NEXT")

    highlights = build_highlights(content)
    if highlights:
        pdf.h2("At a glance")
        for title, detail in highlights:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(20, 20, 20)
            pdf.cell(0, 6, _clean(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(70, 70, 70)
            pdf.multi_cell(0, 4.8, _clean(detail), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

    pdf.h2("Executive summary")
    pdf.body(content.get("executive_summary"))

    pdf.h2("Assessment")
    pdf.body(assessment.get("rationale"))
    for cond in assessment.get("conditions") or []:
        pdf.body(f"Condition: {cond}")

    if narrative:
        pdf.h2("Analyst narrative")
        pdf.body(narrative)

    fin = content.get("financial_health") or {}
    pdf.h2("Financial health")
    for key in ("revenue", "growth", "funding_total", "last_round", "burn_or_profitability"):
        if key in fin:
            pdf.kv(key.replace("_", " ").title(), fin.get(key))
    if fin.get("summary"):
        pdf.body(fin["summary"])

    pdf.h2("Leadership")
    for person in content.get("leadership") or []:
        pdf.kv(person.get("name", "-"), f"{person.get('title', '')} - {person.get('background', '')}")
        if person.get("flags"):
            pdf.body(f"Flag: {person['flags']}", size=9)

    legal = content.get("legal_regulatory") or {}
    pdf.h2("Legal & regulatory")
    pdf.kv("Litigation", legal.get("litigation"))
    pdf.kv("Regulatory", legal.get("regulatory"))

    comp = content.get("competitive_position") or {}
    pdf.h2("Competitive position")
    pdf.kv("Competitors", ", ".join(comp.get("main_competitors") or []) or "-")
    pdf.kv("Differentiation", comp.get("differentiation"))
    pdf.kv("Position", comp.get("market_position"))

    pdf.h2("Risks")
    for risk in content.get("risks") or []:
        sev = risk.get("severity", "medium").upper() if isinstance(risk, dict) else "MEDIUM"
        text = risk.get("risk") if isinstance(risk, dict) else str(risk)
        pdf.kv(f"[{sev}]", text)
        if isinstance(risk, dict) and risk.get("evidence"):
            pdf.body(f"Evidence: {risk['evidence']}", size=9)

    if content.get("operational_risks"):
        pdf.h2("Operational risks")
        for item in content["operational_risks"]:
            pdf.body(f"- {item}")

    if content.get("opportunities"):
        pdf.h2("Opportunities")
        for item in content["opportunities"]:
            pdf.body(f"- {item}")

    rep = content.get("reputation") or {}
    if rep:
        pdf.h2("Reputation")
        pdf.kv("Press", rep.get("press_sentiment"))
        pdf.kv("Employees", rep.get("employee_sentiment"))

    if evidence_gaps:
        pdf.h2("Appendix A - Evidence gaps (Risk Officer)")
        pdf.body("Claims the verdict depends on that rest on weak evidence. "
                 "Verify these by hand before acting on the memo.", size=9)
        for gap in evidence_gaps:
            pdf.kv(humanize_path(gap.get("field", "-")),
                   f"{gap.get('issue', '')} -> {gap.get('recommendation', '')}")

    pdf.h2("Appendix B - Citations")
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4.5, _clean("Every memo field and the sources behind it, grouped by "
                                  "section. Confidence: how strongly the citations support the value."),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    last_section = None
    cited = [cl for cl in claims if cl.get("path")]
    for cl in sorted(cited, key=lambda c: humanize_path(c["path"]).partition(" · ")[0]):
        path = cl["path"]
        label = humanize_path(path)
        section, _, field = label.partition(" · ")
        if section != last_section:
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(20, 20, 20)
            pdf.ln(1.5)
            pdf.cell(0, 6, _clean(section), new_x="LMARGIN", new_y="NEXT")
            last_section = section
        urls = "  ".join((c.get("url") or "")[:85] for c in (cl.get("citations") or [])[:2])
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(0, 4.4, _clean(f"{field or section} [{cl.get('confidence')}]  {urls}"),
                       new_x="LMARGIN", new_y="NEXT")

    C.MEMO_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    path = C.MEMO_DIR / f"{slug}-{date.today().isoformat()}.pdf"
    pdf.output(str(path))
    return path


def email_body_html(content, company):
    assessment = content.get("overall_assessment") or {}
    verdict = html.escape((assessment.get("verdict") or "").replace("_", " ").upper())
    top_risks = "".join(
        f"<li><b>{html.escape((r.get('severity') or '').upper())}</b>"
        f" - {html.escape(str(r.get('risk') or ''))}</li>"
        for r in (content.get("risks") or [])[:3] if isinstance(r, dict))
    return (
        f"<h2>Diligence memo: {html.escape(str(content.get('company_name') or company))}</h2>"
        f"<p><b>Verdict: {verdict}</b></p>"
        f"<p>{html.escape(str(assessment.get('rationale', '')))}</p>"
        f"<p>Top risks:</p><ul>{top_risks}</ul>"
        f"<p>Full memo with the complete citation trail attached. "
        f"Generated by Diligence Desk on Nimble Web Search Agents.</p>"
    )


def send_email(pdf_path, recipients, content, company):
    """Send the memo via Resend. Without a key (or in replay mode), return a
    preview instead of sending — the demo-safe fallback."""
    body_html = email_body_html(content, company)
    subject = f"Diligence memo: {content.get('company_name') or company}"
    key = os.getenv("RESEND_API_KEY", "")
    if not key or not C.USE_LIVE:
        return {"sent": False, "subject": subject, "html": body_html,
                "reason": "replay mode" if key else "no RESEND_API_KEY - preview only"}

    import resend
    resend.api_key = key
    with open(pdf_path, "rb") as f:
        attachment_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "from": os.getenv("EMAIL_FROM", "diligence-desk@resend.dev"),
        "to": recipients,
        "subject": subject,
        "html": body_html,
        "attachments": [{
            "filename": os.path.basename(pdf_path),
            "content": attachment_b64,
        }],
    }
    sent = resend.Emails.send(payload)
    return {"sent": True, "subject": subject, "id": sent.get("id"), "to": recipients}
