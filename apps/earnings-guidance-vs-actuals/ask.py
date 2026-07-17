"""Ask the Desk: two lanes.

Lane 1 (ledger): natural language -> SQL over the Snowflake ledger via Claude
(aggregation/trend questions the accumulated dataset already answers).
Lane 2 (live): new research -> a fresh agent run with previous_interaction_id
so the agent keeps the ticker's research context.
"""
import os
import re

import anthropic

import config as C
import wsa

MODEL = "claude-sonnet-5"

SCHEMA_CARD = """Snowflake tables (database {db}, schema LEDGER):
GUIDANCE_LEDGER(ticker, fiscal_quarter, report_date, metric, guided_value_raw, guided_range_raw,
                guided_low, guided_mid, guided_high, actual_value_raw, actual_value_num,
                metric_verdict beat|miss|inline|not_guided, quarter_verdict, notes,
                guidance_source_url, actual_source_url, run_id)
CLAIMS(claim_id, run_id, ticker, json_path, confidence high|medium|low|pre_existing,
       reasoning, citation_url, citation_title, excerpt)
RUNS(run_id, interaction_id, ticker, quarter_window, overall_confidence, wall_clock_s)"""


def route(question):
    """ledger for aggregation over stored data; live for anything needing new research."""
    q = question.lower()
    live_markers = ("why", "what happened", "explain", "context", "call", "said",
                    "management", "outlook", "expect", "will ", "next quarter")
    return "live" if any(m in q for m in live_markers) else "ledger"


def ask_ledger(question, cur, db):
    """NL -> SQL over the ledger. LlamaIndex engine first; direct Claude as fallback."""
    try:
        return _ask_ledger_llamaindex(question, db)
    except Exception:
        return _ask_ledger_direct(question, cur, db)


def _sqlalchemy_engine(db):
    from pathlib import Path

    from cryptography.hazmat.primitives import serialization
    from snowflake.sqlalchemy import URL
    from sqlalchemy import create_engine
    key_path = Path(__file__).parent / os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    pkb = key.private_bytes(encoding=serialization.Encoding.DER,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption())
    return create_engine(URL(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        database=db, schema="LEDGER",
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"), role=os.environ.get("SNOWFLAKE_ROLE"),
    ), connect_args={"private_key": pkb})


TABLE_INFO = {
    "guidance_ledger": (
        "One row per (ticker, fiscal_quarter, metric). Guidance vs actuals.\n"
        "- metric_verdict is PRECOMPUTED: beat|miss|inline|not_guided - use it for who-beat/missed questions.\n"
        "- Numeric analysis (margins, deltas): use guided_low/guided_mid/guided_high and actual_value_num.\n"
        "  These are NULL when guidance was text-only ('mid single digit growth') - ALWAYS filter\n"
        "  'guided_mid IS NOT NULL AND actual_value_num IS NOT NULL' before arithmetic, and never\n"
        "  ORDER BY an expression that can be NULL without filtering the NULLs out first.\n"
        "- Beat margin pct = (actual_value_num - guided_high) / guided_high * 100 (use guided_high, not mid).\n"
        "- For revenue questions filter metric = 'revenue'. Units are absolute dollars (e.g. 4.67e10).\n"
        "- Round percentages to 1 decimal and alias columns with readable names.\n"
        "- Metrics whose metric_raw mentions 'growth' or 'qualitative' carry PERCENT-scale guided\n"
        "  values - never mix them with dollar-scale actual_value_num in one calculation; add a\n"
        "  sanity filter like actual_value_num / NULLIF(guided_high,0) BETWEEN 0.5 AND 2."),
    "v_headline_dedup": (
        "One HEADLINE row per (ticker, quarter): the quarter's overall verdict in metric_verdict\n"
        "and how it was derived in basis. Prefer this table for per-quarter or track-record questions."),
    "claims": "Field-level citations: json_path, confidence (high|medium|low), citation_url, excerpt.",
    "runs": "One row per agent run: ticker, quarter_window, wall_clock_s, overall_confidence.",
}


def _ask_ledger_llamaindex(question, db):
    from llama_index.core import SQLDatabase, Settings
    from llama_index.core.query_engine import NLSQLTableQueryEngine
    from llama_index.llms.anthropic import Anthropic as LlamaAnthropic

    Settings.llm = LlamaAnthropic(model=MODEL, max_tokens=1000)
    Settings.embed_model = None
    tables = list(TABLE_INFO)
    sa_engine = _sqlalchemy_engine(db)
    sql_db = SQLDatabase(sa_engine, include_tables=tables,
                         custom_table_info=TABLE_INFO, view_support=True)
    # sql_only: generate WITHOUT executing, so nothing runs before validation
    engine = NLSQLTableQueryEngine(sql_database=sql_db, tables=tables, sql_only=True)
    resp = engine.query(question)
    sql = ((resp.metadata or {}).get("sql_query") or str(resp)).strip().rstrip(";")
    if not re.match(r"^\s*(select|with)\b", sql, re.I) or ";" in sql:
        raise ValueError(f"refusing non-SELECT SQL: {sql[:80]}")
    from sqlalchemy import text
    with sa_engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys())
        rows = [tuple(r) for r in result.fetchall()]
    answer = _summarize(question, sql, cols, rows)
    return sql, cols, rows, answer


def _summarize(question, sql, cols, rows):
    """One short synthesized answer over the (already safely executed) result."""
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model=MODEL, max_tokens=300,
            system="Answer the question in 1-3 plain sentences using only the query result given.",
            messages=[{"role": "user", "content":
                       f"Question: {question}\nSQL: {sql}\nColumns: {cols}\nRows (first 20): {rows[:20]}"}])
        return next(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        return None


def _ask_ledger_direct(question, cur, db):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=MODEL, max_tokens=500,
        system=("Write ONE Snowflake SELECT statement answering the question. "
                "Only SELECT - no DDL/DML. Fully qualify tables. Return only SQL, no fences.\n"
                + SCHEMA_CARD.format(db=db)),
        messages=[{"role": "user", "content": question}])
    text = next(b.text for b in msg.content if getattr(b, "type", "") == "text")
    sql = text.strip().strip("`").removeprefix("sql").strip()
    if not re.match(r"^\s*select\b", sql, re.I) or ";" in sql.rstrip(";"):
        raise ValueError(f"refusing non-SELECT SQL: {sql[:80]}")
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return sql, cols, cur.fetchall(), None


def ask_live(question, ticker, interaction_id):
    run = wsa.start_run(C.agent_id(), f"Ticker: {ticker}. {question}",
                        previous_interaction_id=interaction_id)
    result, run_final = wsa.wait_for_result(C.agent_id(), run["id"])
    out = result["output"]
    trust = out.get("trust") or {}
    return {"content": out.get("content"), "confidence": trust.get("confidence"),
            "claims": len(trust.get("claims") or []),
            "interaction_id": run_final.get("interaction_id")}
