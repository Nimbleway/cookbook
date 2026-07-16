"""Supabase data layer. Raw results are saved verbatim before any transform."""
import os

from supabase import create_client

import config as C  # noqa: F401  (loads .env)

_client = None


def client():
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


def create_memo(company, input_prompt):
    row = client().table("dd_memos").insert(
        {"company": company, "input_prompt": input_prompt, "status": "running"}
    ).execute().data[0]
    return row["id"]


def fail_memo(memo_id, message):
    client().table("dd_memos").update(
        {"status": "failed", "memo_narrative": message}).eq("id", memo_id).execute()


def save_memo_result(memo_id, raw_result, run):
    """Verbatim raw first, then derived columns and per-claim rows."""
    content = raw_result["output"]["content"]
    client().table("dd_memos").update({
        "raw_result": raw_result,
        "run_id": run["id"],
        "interaction_id": run.get("interaction_id"),
        "status": "completed",
        "verdict": (content.get("overall_assessment") or {}).get("verdict"),
        "data_as_of_date": content.get("data_as_of_date"),
    }).eq("id", memo_id).execute()

    claims = (raw_result["output"].get("trust") or {}).get("claims") or []
    if claims:
        client().table("dd_claims").insert([{
            "memo_id": memo_id,
            "path": cl.get("path"),
            "confidence": cl.get("confidence"),
            "reasoning": cl.get("reasoning"),
            "citations": cl.get("citations"),
        } for cl in claims]).execute()


def save_crew_output(memo_id, narrative, evidence_gaps):
    client().table("dd_memos").update({
        "memo_narrative": narrative, "evidence_gaps": evidence_gaps,
    }).eq("id", memo_id).execute()


def save_actions(memo_id, pdf_path=None, emailed_to=None):
    patch = {}
    if pdf_path:
        patch["pdf_path"] = str(pdf_path)
    if emailed_to:
        patch["emailed_to"] = emailed_to
    if patch:
        client().table("dd_memos").update(patch).eq("id", memo_id).execute()


def save_followup(memo_id, question, raw_result, run):
    content = raw_result["output"]["content"]
    answer = content.get("answer") if isinstance(content, dict) else str(content)
    key_points = content.get("key_points") if isinstance(content, dict) else None
    client().table("dd_followups").insert({
        "memo_id": memo_id,
        "question": question,
        "answer": answer,
        "key_points": key_points,
        "interaction_id": run.get("interaction_id"),
        "raw_result": raw_result,
    }).execute()
    return answer, key_points


def save_agent_update(instruction, before, after):
    client().table("dd_agent_updates").insert({
        "instruction": instruction,
        "expertise_before": before,
        "expertise_after": after,
    }).execute()


def list_memos():
    return client().table("dd_memos").select(
        "id, company, status, verdict, data_as_of_date, pdf_path, emailed_to, created_at"
    ).order("created_at", desc=True).execute().data


def get_memo(memo_id):
    return client().table("dd_memos").select("*").eq("id", memo_id).single().execute().data


def get_claims(memo_id):
    return client().table("dd_claims").select("*").eq("memo_id", memo_id).execute().data


def get_followups(memo_id):
    return client().table("dd_followups").select("*").eq(
        "memo_id", memo_id).order("created_at").execute().data


def list_agent_updates():
    return client().table("dd_agent_updates").select("*").order(
        "created_at", desc=True).execute().data
