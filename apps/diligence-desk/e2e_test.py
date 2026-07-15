"""End-to-end test + sample-dataset capture for Diligence Desk.

Prereq: supabase/schema.sql applied. Run: .venv/bin/python e2e_test.py

Live phase (USE_LIVE=true): full memo on the demo target through the real code
paths (db -> wsa -> crew -> actions), one follow-up, one teach cycle. Every raw
response is saved verbatim to data/sample_run/. Replay phase then re-runs the
same paths with the captured data to verify cached demo mode.
"""
import json
import sys
import time

import config as C

DEMO_PROMPT = ("Due diligence on Perplexity AI (perplexity.ai) for a strategic "
               "investment - financial health, leadership, legal exposure, "
               "competitive position, and key risks")
DEMO_COMPANY = "Perplexity AI"
FOLLOWUP_Q = ("How exposed is Perplexity to the pending copyright lawsuits, and "
              "what would an adverse ruling mean for its business model?")
TEACH_INSTRUCTION = ("Always assess exposure to pending AI copyright litigation "
                     "and name the specific cases and plaintiffs.")


def tick(elapsed, status):
    print(f"  {elapsed}s {status}", flush=True)


def live_phase():
    import actions, crew, db, wsa
    assert C.USE_LIVE, "set USE_LIVE=true for the live phase"
    C.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    print("1/6 memo run (max effort, expect 10-20 min)")
    memo_id = db.create_memo(DEMO_COMPANY, DEMO_PROMPT)
    raw, run = wsa.run_memo(DEMO_PROMPT, on_tick=tick)
    (C.SAMPLE_DIR / "memo_result.json").write_text(json.dumps(raw, indent=2))
    (C.SAMPLE_DIR / "memo_run.json").write_text(json.dumps(run, indent=2))
    db.save_memo_result(memo_id, raw, run)
    content = raw["output"]["content"]
    claims = (raw["output"].get("trust") or {}).get("claims") or []
    verdict = (content.get("overall_assessment") or {}).get("verdict")
    print(f"  verdict={verdict}, claims={len(claims)}")
    assert verdict, "no verdict in output"
    assert len(claims) >= 20, "suspiciously few trust claims"

    # source-enforcement check on the production agent (design finding)
    hosts = {("" if not s.get("url") else s["url"].split("/")[2].replace("www.", ""))
             for s in (raw["output"]["trust"].get("sources") or [])}
    print(f"  trust.sources hosts: {sorted(hosts)}")

    print("2/6 crew review")
    crew_out = crew.run_crew(content, claims)
    (C.SAMPLE_DIR / "crew_output.json").write_text(json.dumps(crew_out, indent=2))
    db.save_crew_output(memo_id, crew_out["narrative"], crew_out["evidence_gaps"])
    print(f"  gaps={len(crew_out['evidence_gaps'])}, narrative={len(crew_out['narrative'])} chars")

    print("3/6 pdf")
    pdf_path = actions.build_pdf(content, crew_out["narrative"],
                                 crew_out["evidence_gaps"], claims, DEMO_COMPANY)
    db.save_actions(memo_id, pdf_path=str(pdf_path))
    print(f"  {pdf_path}")

    print("4/6 email (fallback expected without RESEND_API_KEY)")
    outcome = actions.send_email(str(pdf_path), ["deal-team@example.com"], content, DEMO_COMPANY)
    print(f"  sent={outcome['sent']} ({outcome.get('reason', outcome.get('id'))})")

    print("5/6 follow-up (high effort)")
    raw_fu, run_fu = wsa.run_followup(FOLLOWUP_Q, run.get("interaction_id"),
                                      followup_index=0, on_tick=tick)
    (C.SAMPLE_DIR / "followup_0_result.json").write_text(json.dumps(raw_fu, indent=2))
    (C.SAMPLE_DIR / "followup_0_run.json").write_text(json.dumps(run_fu, indent=2))
    answer, _ = db.save_followup(memo_id, FOLLOWUP_Q, raw_fu, run_fu)
    print(f"  answer: {answer[:150]}...")

    print("6/6 teach cycle")
    import wsa as _w
    before, after = _w.teach(TEACH_INSTRUCTION)
    (C.SAMPLE_DIR / "teach_before_after.json").write_text(
        json.dumps({"before": before, "after": after}, indent=2))
    db.save_agent_update(TEACH_INSTRUCTION, before, after)
    assert TEACH_INSTRUCTION[:30] in after and TEACH_INSTRUCTION[:30] not in before
    print("  standing instruction landed in domain_expertise")
    print(f"LIVE PHASE PASS - memo #{memo_id}")


def replay_phase():
    """Re-import modules with USE_LIVE=false and drive the same code paths."""
    import importlib
    C.USE_LIVE = False
    import wsa, crew
    importlib.reload(wsa)
    importlib.reload(crew)
    wsa.C.USE_LIVE = False
    crew.C.USE_LIVE = False

    raw, run = wsa.run_memo(DEMO_PROMPT)
    content = raw["output"]["content"]
    claims = (raw["output"].get("trust") or {}).get("claims") or []
    assert (content.get("overall_assessment") or {}).get("verdict")
    out = crew.run_crew(content, claims)
    assert out["narrative"]
    raw_fu, _ = wsa.run_followup(FOLLOWUP_Q, "ignored", followup_index=0)
    assert raw_fu["output"]["content"]
    before, after = wsa.teach(TEACH_INSTRUCTION)
    assert before != after
    import actions
    pdf = actions.build_pdf(content, out["narrative"], out["evidence_gaps"],
                            claims, DEMO_COMPANY + " (replay)")
    print(f"REPLAY PHASE PASS - {pdf}")


if __name__ == "__main__":
    t0 = time.time()
    if "--replay-only" not in sys.argv:
        live_phase()
    replay_phase()
    print(f"E2E DONE in {int(time.time() - t0)}s")
