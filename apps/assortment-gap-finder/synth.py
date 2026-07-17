"""The agentic synthesis loop: whitespace + review themes -> gap hypotheses ->
live-shelf verification -> Linear tickets.

Claude (via the OpenAI Agent SDK + LiteLLM) owns judgment: which cells matter, how to
phrase each gap, whether the verification verdict justifies a ticket. The tools do the
deterministic work.

Usage: python synth.py [--max-gaps 5]
"""
import hashlib
import json
import sys
from datetime import datetime, timezone

from agents import Agent, Runner, function_tool, set_tracing_disabled
set_tracing_disabled(True)  # no OpenAI key; tracing would warn every run
from agents.extensions.models.litellm_model import LitellmModel

import config as C
import delta
import gaps as gaps_mod
import linear_client
import wsa

MAX_GAPS = int(sys.argv[sys.argv.index("--max-gaps") + 1]) if "--max-gaps" in sys.argv else 5
filed = []


@function_tool
def get_whitespace_report() -> str:
    """The catalog whitespace grid (subcategory x price band: product counts, well-rated
    counts) plus the flagged candidate cells."""
    cols, rows = gaps_mod.whitespace_cells()
    lines = ["subcat | band | products | rated4.2+ | avg_rating"]
    lines += [f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}" for r in rows]
    lines.append("\nFlagged candidates: " + json.dumps(gaps_mod.candidate_cells()))
    return "\n".join(lines)


@function_tool
def get_review_themes() -> str:
    """Mined complaint/praise themes with verbatim customer quotes, by product."""
    _, rows = delta.query(f"""
        SELECT product_name, kind, theme, quote, quote_source_url
        FROM {C.DBX_SCHEMA}.review_themes WHERE found = true ORDER BY product_name""")
    return "\n".join(f"[{k}] {p}: {t} - \"{q}\" ({u})" for p, k, t, q, u in rows) or "(none mined)"


@function_tool
def verify_gap(gap_statement: str) -> str:
    """Verify a gap hypothesis against the retailer's LIVE shelf using the
    whitespace-verifier research agent (5-10 minutes). The statement must name a
    price band and a retailer site, e.g. 'no espresso machine under $150 with an
    integrated milk frother rated 4.2+ exists on target.com'."""
    agent_id = C.agent_id("whitespace_verifier")
    run = wsa.start_run(agent_id, f"Verify: {gap_statement}", effort="max")
    result, run_final = wsa.wait_for_result(agent_id, run["id"], timeout_seconds=1800)
    out = result["output"]["content"]
    out["_run_id"] = run["id"]
    out["_interaction_id"] = run_final.get("interaction_id")
    out["_citations"] = [c.get("citations", [{}])[0].get("url")
                         for c in (result["output"].get("trust") or {}).get("claims", [])[:6]]
    (C.RAW_DIR / f"verify_{run['id'][-8:]}.json").write_text(json.dumps(result, indent=1))
    return json.dumps(out)


@function_tool
def file_linear_ticket(gap_statement: str, verdict: str, evidence_summary: str,
                       demand_evidence: str, verification_json: str) -> str:
    """File a verified gap as a Linear ticket. verification_json is the exact string
    returned by verify_gap. Only call for verdicts 'confirmed' or 'partial'."""
    if str(verdict).lower() not in ("confirmed", "partial"):
        return f"refused: verdict '{verdict}' does not justify a ticket - only confirmed or partial gaps are filed"
    gap_id = hashlib.md5(gap_statement.encode()).hexdigest()[:12]
    _, existing = delta.query(
        f"SELECT linear_issue_id, linear_issue_url FROM {C.DBX_SCHEMA}.gaps "
        f"WHERE gap_id = ? AND linear_issue_id IS NOT NULL", [gap_id])
    if existing:
        return f"already filed as {existing[0][0]}: {existing[0][1]} (not filing a duplicate)"
    v = json.loads(verification_json)
    ident, url = linear_client.file_gap_ticket(
        gap_statement, verdict, evidence_summary, demand_evidence,
        v.get("closest_matches"), v.get("_citations"))
    delta.insert_rows("gaps", [{
        "gap_id": gap_id, "gap_statement": gap_statement, "price_band": "",
        "subcategory": "", "demand_evidence": demand_evidence, "verdict": verdict,
        "evidence_summary": evidence_summary,
        "closest_matches": json.dumps(v.get("closest_matches"))[:4000],
        "verify_run_id": v.get("_run_id"), "interaction_id": v.get("_interaction_id"),
        "linear_issue_id": ident, "linear_issue_url": url,
        "created_at": datetime.now(timezone.utc)}])
    filed.append(ident)
    return f"filed {ident}: {url}"


def taught_rules():
    try:
        _, rows = delta.query(f"SELECT rule FROM {C.DBX_SCHEMA}.merch_rules")
        return "\n".join(f"- {r[0]}" for r in rows)
    except Exception:
        return ""


INSTRUCTIONS = f"""You are a merchandising analyst finding real assortment gaps in the
{C.CATEGORY} category for a retail buyer.

Process, in order:
1. get_whitespace_report - see where the catalog is thin or badly rated.
2. get_review_themes - see what customers actually complain about (demand evidence).
3. Synthesize up to {MAX_GAPS} specific, checkable gap hypotheses. Each MUST name a price
   band, concrete product attributes, and a retailer site (rotate across amazon.com,
   walmart.com, target.com). Prefer gaps where whitespace math AND customer complaints
   point the same way - cite the quotes in your demand evidence.
4. verify_gap for each hypothesis, one at a time.
5. For every 'confirmed' or 'partial' verdict, file_linear_ticket with a demand_evidence
   paragraph quoting the customer complaints verbatim.
Refuted gaps: do not file; note what counterexample killed them.
Finish with a short summary listing verdicts and filed tickets.

Taught merchandising rules (always apply):
{taught_rules() or '- Always segment analysis by price band.'}"""


def main():
    import os
    model = LitellmModel(model="anthropic/claude-sonnet-5",
                         api_key=os.environ["ANTHROPIC_API_KEY"])
    agent = Agent(name="Gap Synthesizer", instructions=INSTRUCTIONS, model=model,
                  tools=[get_whitespace_report, get_review_themes, verify_gap,
                         file_linear_ticket])
    result = Runner.run_sync(agent, "Find and file the top assortment gaps.",
                             max_turns=30)
    print("\n=== agent summary ===\n", result.final_output)
    print("\nfiled tickets:", filed)


if __name__ == "__main__":
    main()
