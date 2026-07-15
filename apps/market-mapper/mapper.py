"""Market Mapper — core pipeline.

Discover companies matching an ICP with a Web Search Agents dataset_building
agent, enrich each with an enrichment agent, land everything in Supabase with
per-field trust. Live and sample-replay modes share every code path below the
fetch layer.
"""
import json
import os
import pathlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from supabase import create_client

load_dotenv()

USE_LIVE = os.getenv("USE_LIVE", "true").lower() == "true"

# Supabase is always required (persistence). NIMBLE_API_KEY only for live runs —
# sample replay must work without it. ANTHROPIC_API_KEY is checked in chat().
_required = ["SUPABASE_URL", "SUPABASE_KEY"] + (["NIMBLE_API_KEY"] if USE_LIVE else [])
_missing = [v for v in _required if not os.getenv(v)]
if _missing:
    raise SystemExit(f"Missing environment variables: {', '.join(_missing)} — copy .env.example to .env and fill it in.")

BASE = "https://sdk.nimbleway.com/v1"
HEADERS = {"Authorization": f"Bearer {os.getenv('NIMBLE_API_KEY', '')}", "Content-Type": "application/json"}
ENRICH_CAP = int(os.getenv("ENRICH_CAP", "10"))
SAMPLE_DIR = pathlib.Path(__file__).parent / "data" / "sample_run"
_agents_file = pathlib.Path(__file__).parent / "agents.json"


class _Agents:
    """Lazy agents.json loader with a clear error before setup has run."""

    def __getitem__(self, key):
        if not _agents_file.exists():
            raise SystemExit("agents.json not found — run `python3 setup_agents.py` first to create your agents.")
        return json.loads(_agents_file.read_text())[key]


AGENTS = _Agents()

POLL_SECONDS = 20
CHAT_MODEL = "claude-sonnet-4-6"

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ---------------------------------------------------------------- Web Search Agents client

def _create_run(agent_id, input_text, previous_interaction_id=None):
    body = {"input": input_text}
    if previous_interaction_id:
        body["previous_interaction_id"] = previous_interaction_id
    r = requests.post(f"{BASE}/task-agents/{agent_id}/runs", headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_run(agent_id, run_id):
    r = requests.get(f"{BASE}/task-agents/{agent_id}/runs/{run_id}", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _get_result(agent_id, run_id):
    r = requests.get(f"{BASE}/task-agents/{agent_id}/runs/{run_id}/result", headers=HEADERS, timeout=60)
    if r.status_code == 408:  # still active
        return None
    r.raise_for_status()
    return r.json()


def run_and_wait(agent_id, input_text, previous_interaction_id=None, on_status=None, timeout_s=1800):
    """Create a run, poll to a terminal state, return (run, result_or_None)."""
    run = _create_run(agent_id, input_text, previous_interaction_id)
    t0 = time.time()
    while run.get("is_active", False) or run["status"] in ("queued", "running"):
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"run {run['id']} still active after {timeout_s}s")
        if on_status:
            on_status(run["status"], int(time.time() - t0))
        time.sleep(POLL_SECONDS)
        run = _get_run(agent_id, run["id"])
    result = _get_result(agent_id, run["id"]) if run["status"] == "completed" else None
    return run, result


# ---------------------------------------------------------------- fetch layer (live | replay)

def _discovery_result(icp, exclude_domains, on_status):
    if not USE_LIVE:
        payload = json.loads((SAMPLE_DIR / "discovery_result.json").read_text())
        return payload["run"], payload["result"]
    text = icp
    if exclude_domains:
        text += "\n\nExclusion list — never return companies with these domains: " + ", ".join(exclude_domains)
    return run_and_wait(AGENTS["mapper"], text, on_status=on_status)


def _enrichment_result(company_name, domain, on_status=None):
    if not USE_LIVE:
        path = SAMPLE_DIR / "enrichment" / f"{domain}.json"
        if not path.exists():
            return None, None
        payload = json.loads(path.read_text())
        return payload["run"], payload["result"]
    prompt = (f"Enrich lead: {company_name} ({domain}) — company details, funding stage and investors, "
              f"headcount, key decision-makers with titles and LinkedIn URLs, tech stack, buying signals")
    return run_and_wait(AGENTS["enricher"], prompt, on_status=on_status)


# ---------------------------------------------------------------- parsing

_BAND = re.compile(r"(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)")


def band_upper(employee_count):
    """Deterministic parse of an employee band's upper bound; None if unparseable."""
    if not employee_count:
        return None
    m = _BAND.search(str(employee_count))
    if m:
        return int(m.group(2).replace(",", ""))
    digits = re.sub(r"[^\d]", "", str(employee_count))
    return int(digits) if digits else None


def _normalize_rows(result):
    rows = result["output"]["content"]
    seen, out = set(), []
    for r in rows:
        domain = (r.get("domain") or "").lower().strip().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        out.append({**r, "domain": domain})
    return out


_CONF_RANK = {"high": 0, "pre_existing": 1, "medium": 2, "low": 3}


def _field_claims(result):
    """Aggregate claims per top-level field. Array fields carry one claim per element,
    so a field's grade is its WORST element claim, with a count breakdown."""
    fields = {}
    for cl in result["output"]["trust"].get("claims", []):
        path = (cl.get("path") or "").replace("$.", "").strip("$[]'`\"")
        if not path:
            continue
        field = path.split("[")[0].split(".")[0]
        f = fields.setdefault(field, {"confidence": "high", "n_claims": 0, "by_level": {}, "citations": []})
        f["n_claims"] += 1
        conf = cl.get("confidence", "high")
        f["by_level"][conf] = f["by_level"].get(conf, 0) + 1
        if _CONF_RANK.get(conf, 0) > _CONF_RANK.get(f["confidence"], 0):
            f["confidence"] = conf
        for ci in cl.get("citations", [])[:2]:
            if ci.get("url") and ci["url"] not in f["citations"]:
                f["citations"].append(ci["url"])
        f["citations"] = f["citations"][:3]
    return fields


# ---------------------------------------------------------------- pipeline

def map_market(icp, exclude_domains=None, max_employees=None, on_status=None):
    """Run discovery, land companies in Supabase. Returns the mm_runs row id."""
    exclude_domains = [d.lower().strip() for d in (exclude_domains or [])]
    run_row = sb.table("mm_runs").insert({
        "icp_prompt": icp, "exclude_domains": exclude_domains, "agent_id": AGENTS["mapper"],
    }).execute().data[0]

    run, result = _discovery_result(icp, exclude_domains, on_status)
    if result is None or run["status"] != "completed":
        sb.table("mm_runs").update({"status": run.get("status", "failed"),
                                    "raw_result": run}).eq("id", run_row["id"]).execute()
        return run_row["id"]

    rows = _normalize_rows(result)
    rows = [r for r in rows if r["domain"] not in exclude_domains]
    for r in rows:
        upper = band_upper(r.get("employee_count"))
        r["size_flag"] = "out_of_band" if (max_employees and upper and upper > max_employees) else None

    if rows:
        sb.table("mm_companies").upsert([{
            "run_id": run_row["id"],
            "company_name": r.get("company_name"), "domain": r["domain"],
            "website": r.get("website"), "linkedin_url": r.get("linkedin_url"),
            "industry": r.get("industry"), "employee_count": r.get("employee_count"),
            "headquarters": r.get("headquarters"), "recent_funding": r.get("recent_funding"),
            "icp_fit_reason": r.get("icp_fit_reason"), "source_url": r.get("source_url"),
            "size_flag": r.get("size_flag"),
        } for r in rows], on_conflict="run_id,domain").execute()

    sb.table("mm_runs").update({
        "status": "completed", "run_id": run["id"], "interaction_id": run.get("interaction_id"),
        "discovered_count": len(rows), "completed_at": run.get("completed_at"),
        "raw_result": result,  # raw saved before any transform is used downstream
    }).eq("id", run_row["id"]).execute()
    return run_row["id"]


def expand_map(run_uuid, count=10, on_status=None):
    """Multi-turn: re-run the mapper with previous_interaction_id to extend the same map."""
    prev = sb.table("mm_runs").select("*").eq("id", run_uuid).single().execute().data
    if not prev.get("interaction_id"):
        raise ValueError("previous run has no interaction_id (sample mode or failed run)")
    known = [c["domain"] for c in
             sb.table("mm_companies").select("domain").eq("run_id", run_uuid).execute().data]
    text = (f"Find {count} more companies matching the same ICP that you have not already returned. "
            f"Never repeat these domains: {', '.join(known)}")
    run, result = run_and_wait(AGENTS["mapper"], text,
                               previous_interaction_id=prev["interaction_id"], on_status=on_status)
    if result is None or run["status"] != "completed":
        return 0
    rows = [r for r in _normalize_rows(result) if r["domain"] not in set(known)]
    if rows:
        sb.table("mm_companies").upsert([{
            "run_id": run_uuid, "company_name": r.get("company_name"), "domain": r["domain"],
            "website": r.get("website"), "linkedin_url": r.get("linkedin_url"),
            "industry": r.get("industry"), "employee_count": r.get("employee_count"),
            "headquarters": r.get("headquarters"), "recent_funding": r.get("recent_funding"),
            "icp_fit_reason": r.get("icp_fit_reason"), "source_url": r.get("source_url"),
        } for r in rows], on_conflict="run_id,domain").execute()
        sb.table("mm_runs").update({"interaction_id": run.get("interaction_id")}).eq("id", run_uuid).execute()
    return len(rows)


def enrich_pending(run_uuid, cap=None, workers=5, on_event=None):
    """Fan out enrichment runs over pending companies. Resume-safe: skips non-pending rows."""
    cap = cap or ENRICH_CAP
    pending = (sb.table("mm_companies").select("id, company_name, domain")
               .eq("run_id", run_uuid).eq("enrich_status", "pending")
               .order("id").limit(cap).execute().data)

    def fetch(c):
        return c, *_enrichment_result(c["company_name"], c["domain"])

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, c): c for c in pending}
        for f in as_completed(futures):
            c = futures[f]
            try:
                _, run, result = f.result()
            except Exception as e:  # network/API failure is a data state, not a crash
                print(f"enrichment failed for {c['domain']}: {e}", flush=True)
                sb.table("mm_companies").update({"enrich_status": "failed",
                                                 "raw_enrichment": {"error": str(e)}}
                                                ).eq("id", c["id"]).execute()
                if on_event:
                    on_event(c["domain"], "failed")
                continue
            if result is None or (run and run.get("status") != "completed"):
                sb.table("mm_companies").update({"enrich_status": "failed", "raw_enrichment": run}
                                                ).eq("id", c["id"]).execute()
                if on_event:
                    on_event(c["domain"], "failed")
                continue
            content = result["output"]["content"]
            trust = result["output"]["trust"]
            sb.table("mm_companies").update({
                "funding_stage": content.get("funding_stage"), "total_funding": content.get("total_funding"),
                "headcount_estimate": content.get("headcount_estimate"),
                "key_investors": content.get("key_investors"), "tech_stack": content.get("tech_stack"),
                "key_contacts": content.get("key_contacts"), "buying_signals": content.get("buying_signals"),
                "summary": content.get("summary"),
                "enrichment_confidence": trust.get("confidence"),
                "claims": _field_claims(result), "raw_enrichment": result,
                "enrich_status": "enriched", "enriched_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", c["id"]).execute()
            done += 1
            if on_event:
                on_event(c["domain"], "enriched")
    return done, len(pending)


# ---------------------------------------------------------------- queries + chat

def get_run(run_uuid):
    return sb.table("mm_runs").select("*").eq("id", run_uuid).single().execute().data


def get_companies(run_uuid):
    return (sb.table("mm_companies").select("*").eq("run_id", run_uuid)
            .order("id").execute().data)


def list_runs(limit=20):
    return (sb.table("mm_runs").select("id, created_at, icp_prompt, status, discovered_count")
            .order("created_at", desc=True).limit(limit).execute().data)


_chat_chain = None


def chat(question, companies):
    """Answer a question over the mapped dataset. LangChain prompt | Claude."""
    global _chat_chain
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY missing — chat needs it; add it to .env.")
    if _chat_chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are Market Mapper's analyst. Answer questions about the company dataset below. "
             "Be concrete and cite company names; when a claim comes from a specific source_url, mention it. "
             "If the data doesn't contain the answer, say so.\n\nDATASET:\n{dataset}"),
            ("human", "{question}"),
        ])
        _chat_chain = prompt | ChatAnthropic(model=CHAT_MODEL, max_tokens=1024)
    slim = [{k: v for k, v in c.items() if k not in ("raw_enrichment", "claims")} for c in companies]
    return _chat_chain.invoke({"dataset": json.dumps(slim, default=str), "question": question}).content


# ---------------------------------------------------------------- headless CLI

def run_cli(icp, exclude=None, enrich=True):
    """Full collection without the UI: map, then enrich. Returns the run uuid."""
    print(f"mapping: {icp}", flush=True)
    run_uuid = map_market(icp, exclude_domains=exclude or [],
                          on_status=lambda s, t: print(f"  discovery {s} {t}s", flush=True))
    companies = get_companies(run_uuid)
    print(f"discovered {len(companies)} companies", flush=True)
    if enrich and companies:
        done, attempted = enrich_pending(run_uuid,
                                         on_event=lambda d, s: print(f"  {d}: {s}", flush=True))
        print(f"enriched {done}/{attempted}", flush=True)
    print(f"run: {run_uuid} — query mm_companies in Supabase or load it in the app", flush=True)
    return run_uuid


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Map a market from the command line (no UI).")
    ap.add_argument("icp", help="ICP description, quoted")
    ap.add_argument("--exclude", help="path to a file with one domain per line to exclude")
    ap.add_argument("--no-enrich", action="store_true", help="discovery only")
    args = ap.parse_args()
    excl = []
    if args.exclude:
        excl = [ln.strip() for ln in open(args.exclude) if ln.strip()]
    run_cli(args.icp, exclude=excl, enrich=not args.no_enrich)
