"""CrewAI review layer: the WSA does the research; the crew turns the structured
result + trust claims into the consulting deliverable.

Sequential crew — QA Analyst (goals checklist) → Risk Officer (evidence gaps)
→ Editor (memo narrative). Replay mode serves data/sample_run/crew_output.json.
"""
import json

import config as C

GOALS_CHECKLIST = "\n".join(f"- {g}" for g in C.GOALS)


def _claims_digest(claims, max_claims=120):
    """Compact claims view for prompt context: path, confidence, first source."""
    rows = []
    for cl in claims[:max_claims]:
        cite = (cl.get("citations") or [{}])[0]
        rows.append({
            "path": cl.get("path"),
            "confidence": cl.get("confidence"),
            "source": cite.get("url"),
            "n_citations": len(cl.get("citations") or []),
        })
    return rows


def run_crew(content, claims):
    """Returns {"qa_check": str, "evidence_gaps": list, "narrative": str}."""
    if not C.USE_LIVE:
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", str(content.get("company_name") or "").lower()).strip("-")
        keyed = C.SAMPLE_DIR / f"crew_output_{slug}.json"
        if slug and keyed.exists():
            return json.loads(keyed.read_text())
        return json.loads((C.SAMPLE_DIR / "crew_output.json").read_text())

    from crewai import Agent, Crew, Task, LLM

    llm = LLM(model=C.CREW_MODEL)
    memo_json = json.dumps(content, indent=1)
    claims_json = json.dumps(_claims_digest(claims), indent=1)

    qa = Agent(
        role="Diligence QA Analyst",
        goal="Verify a diligence memo meets every acceptance criterion before it reaches a client",
        backstory="You run the quality gate at a strategy consultancy; nothing "
                  "leaves the building without passing your checklist.",
        llm=llm, verbose=False,
    )
    risk = Agent(
        role="Risk Officer",
        goal="Find where the memo's load-bearing claims rest on weak evidence",
        backstory="A former auditor: you care about which citations would survive "
                  "a hostile review, not how the memo reads.",
        llm=llm, verbose=False,
    )
    editor = Agent(
        role="Memo Editor",
        goal="Write the executive narrative a consulting partner reads first",
        backstory="You write memos for partners with ninety seconds: verdict-first, "
                  "plain, concrete, zero hedging or filler.",
        llm=llm, verbose=False,
    )

    t_qa = Task(
        description=(
            "Check this diligence memo against the acceptance criteria.\n\n"
            f"CRITERIA:\n{GOALS_CHECKLIST}\n\nMEMO JSON:\n{memo_json}\n\n"
            "For each criterion answer PASS or FAIL with one short reason."
        ),
        expected_output="One line per criterion: PASS/FAIL - reason.",
        agent=qa,
    )
    t_risk = Task(
        description=(
            "Every field of the memo carries trust claims (path, confidence, source "
            "count). Identify the load-bearing claims — those the verdict rationale, "
            "top risks, or financial figures depend on — that rest on low confidence "
            "or a single source.\n\n"
            f"MEMO JSON:\n{memo_json}\n\nTRUST CLAIMS:\n{claims_json}\n\n"
            "Return STRICT JSON only: an array of objects with keys "
            '"field" (the claim path), "issue" (why it is weak), '
            '"recommendation" (how a human should verify it). Maximum 8 items, '
            "most material first. No prose outside the JSON."
        ),
        expected_output='A JSON array of {"field", "issue", "recommendation"} objects.',
        agent=risk,
    )
    t_edit = Task(
        description=(
            "Write the executive narrative for this diligence memo: 3-5 paragraphs, "
            "verdict first, then the findings that drive it, then material risks with "
            "their evidence strength (use the QA and risk notes from the previous "
            "steps), then what the deal team should do next. Plain text, no headers, "
            "no bullet points, no invented facts — only what the memo JSON supports.\n\n"
            f"MEMO JSON:\n{memo_json}"
        ),
        expected_output="3-5 paragraphs of plain prose.",
        agent=editor, context=[t_qa, t_risk],
    )

    crew = Crew(agents=[qa, risk, editor], tasks=[t_qa, t_risk, t_edit], verbose=False)
    result = crew.kickoff()

    raw_risk = t_risk.output.raw.strip()
    if raw_risk.startswith("```"):
        raw_risk = raw_risk.strip("`").lstrip("json").strip()
    try:
        gaps = json.loads(raw_risk)
    except json.JSONDecodeError:
        gaps = [{"field": "(unparsed)", "issue": raw_risk[:500], "recommendation": ""}]

    return {
        "qa_check": t_qa.output.raw,
        "evidence_gaps": gaps,
        "narrative": result.raw,
    }
