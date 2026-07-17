"""Create the EARNINGS_DESK database + ledger tables (idempotent)."""
import os

import snowflake.connector

import config  # noqa: F401  (loads .env)

DDL = [
    "CREATE DATABASE IF NOT EXISTS {db}",
    "CREATE SCHEMA IF NOT EXISTS {db}.LEDGER",
    """CREATE TABLE IF NOT EXISTS {db}.LEDGER.RUNS (
        run_id STRING PRIMARY KEY,
        interaction_id STRING,
        ticker STRING,
        quarter_window STRING,
        status STRING,
        effort STRING,
        overall_confidence STRING,
        started_at TIMESTAMP_NTZ,
        completed_at TIMESTAMP_NTZ,
        wall_clock_s INTEGER,
        raw_result VARIANT,
        ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    )""",
    """CREATE TABLE IF NOT EXISTS {db}.LEDGER.GUIDANCE_LEDGER (
        ticker STRING,
        fiscal_quarter STRING,
        report_date DATE,
        metric STRING,
        metric_raw STRING,
        guided_value_raw STRING,
        guided_range_raw STRING,
        guided_low FLOAT,
        guided_mid FLOAT,
        guided_high FLOAT,
        actual_value_raw STRING,
        actual_value_num FLOAT,
        metric_verdict STRING,
        quarter_verdict STRING,
        notes STRING,
        guidance_source_url STRING,
        actual_source_url STRING,
        run_id STRING,
        ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (ticker, fiscal_quarter, metric)
    )""",
    """CREATE OR REPLACE VIEW {db}.LEDGER.V_HEADLINE AS
    WITH rev AS (
        SELECT ticker, fiscal_quarter, report_date, guided_range_raw, guided_value_raw,
               actual_value_raw, metric_verdict, 'total revenue' AS basis
        FROM {db}.LEDGER.GUIDANCE_LEDGER WHERE metric = 'revenue' AND guided_low IS NOT NULL
    ), rev_actual_only AS (
        SELECT ticker, fiscal_quarter, report_date, actual_value_raw, actual_value_num
        FROM {db}.LEDGER.GUIDANCE_LEDGER
        WHERE metric = 'revenue' AND guided_low IS NULL AND actual_value_num IS NOT NULL
    ), seg AS (
        SELECT ticker, fiscal_quarter, report_date,
               SUM(guided_low) AS glow, SUM(guided_high) AS ghigh,
               SUM(actual_value_num) AS act,
               COUNT(*) AS n, COUNT(actual_value_num) AS n_act
        FROM {db}.LEDGER.GUIDANCE_LEDGER
        WHERE metric LIKE '%revenue%' AND metric != 'revenue'
        GROUP BY 1, 2, 3
    ), main AS (
    SELECT * FROM rev
    UNION ALL
    SELECT s.ticker, s.fiscal_quarter, s.report_date,
           'segments summed: $' || ROUND(s.glow / 1e9, 1) || 'B-$' || ROUND(s.ghigh / 1e9, 1) || 'B',
           NULL,
           '$' || ROUND(s.act / 1e9, 1) || 'B (' || s.n || ' segments)',
           CASE WHEN s.act > s.ghigh THEN 'beat'
                WHEN s.act < s.glow THEN 'miss' ELSE 'inline' END,
           'segment sum (' || s.n || ')'
    FROM seg s
    WHERE s.n_act = s.n AND s.glow IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM rev r
                      WHERE r.ticker = s.ticker AND r.fiscal_quarter = s.fiscal_quarter)
    UNION ALL
    SELECT s.ticker, s.fiscal_quarter, s.report_date,
           'segments guided: $' || ROUND(s.glow / 1e9, 1) || 'B-$' || ROUND(s.ghigh / 1e9, 1) || 'B',
           NULL,
           a.actual_value_raw,
           CASE WHEN a.actual_value_num > s.ghigh THEN 'beat'
                WHEN a.actual_value_num < s.glow THEN 'miss' ELSE 'inline' END,
           'segments vs total'
    FROM seg s
    JOIN rev_actual_only a
      ON a.ticker = s.ticker AND a.fiscal_quarter = s.fiscal_quarter
    WHERE s.glow IS NOT NULL AND s.n_act < s.n
      AND NOT EXISTS (SELECT 1 FROM rev r
                      WHERE r.ticker = s.ticker AND r.fiscal_quarter = s.fiscal_quarter)
    )
    SELECT * FROM main
    UNION ALL
    -- catch-all: any (ticker, quarter) not covered above (outlook-style guiders:
    -- banks, TSLA, JNJ) — headline = the agent's quarter verdict over the guided outlook
    SELECT g.ticker, g.fiscal_quarter, MAX(g.report_date),
           MAX(g.guided_range_raw), MAX(g.guided_value_raw), MAX(g.actual_value_raw),
           CASE
             WHEN SUM(IFF(g.metric_verdict = 'beat', 1, 0)) > SUM(IFF(g.metric_verdict = 'miss', 1, 0))
                  AND SUM(IFF(g.metric_verdict IN ('beat','miss','inline'), 1, 0)) > 0 THEN 'beat'
             WHEN SUM(IFF(g.metric_verdict = 'miss', 1, 0)) > SUM(IFF(g.metric_verdict = 'beat', 1, 0)) THEN 'miss'
             WHEN SUM(IFF(g.metric_verdict IN ('beat','miss','inline'), 1, 0)) > 0 THEN 'inline'
             ELSE 'not_guided'
           END,
           'outlook majority (' || SUM(IFF(g.metric_verdict IN ('beat','miss','inline'), 1, 0))
               || '/' || COUNT(*) || ' graded)'
    FROM {db}.LEDGER.GUIDANCE_LEDGER g
    WHERE NOT EXISTS (SELECT 1 FROM main m
                      WHERE m.ticker = g.ticker AND m.fiscal_quarter = g.fiscal_quarter)
    GROUP BY g.ticker, g.fiscal_quarter""",
    """CREATE OR REPLACE VIEW {db}.LEDGER.V_HEADLINE_DEDUP AS
    SELECT * FROM {db}.LEDGER.V_HEADLINE
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ticker, report_date
        ORDER BY CASE WHEN basis LIKE 'total%' THEN 0
                      WHEN basis LIKE 'segment%' THEN 1 ELSE 2 END) = 1""",
    """CREATE TABLE IF NOT EXISTS {db}.LEDGER.CLAIMS (
        claim_id STRING PRIMARY KEY,
        run_id STRING,
        ticker STRING,
        json_path STRING,
        confidence STRING,
        reasoning STRING,
        citation_url STRING,
        citation_title STRING,
        excerpt STRING,
        ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    )""",
]


def connect():
    kwargs = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        role=os.environ.get("SNOWFLAKE_ROLE") or None,
    )
    key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    if key_path:  # key-pair auth (no MFA prompts); path relative to the app dir
        from pathlib import Path

        from cryptography.hazmat.primitives import serialization
        p = Path(__file__).parent / key_path
        key = serialization.load_pem_private_key(p.read_bytes(), password=None)
        kwargs["private_key"] = key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())
    else:
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    return snowflake.connector.connect(**kwargs)


def main():
    db = os.environ.get("SNOWFLAKE_DATABASE", "EARNINGS_DESK")
    wh = os.environ.get("SNOWFLAKE_WAREHOUSE", "EARNINGS_WH")
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"""CREATE WAREHOUSE IF NOT EXISTS {wh}
        WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE""")
    cur.execute(f"USE WAREHOUSE {wh}")
    for stmt in DDL:
        cur.execute(stmt.format(db=db))
    cur.execute(f"SELECT COUNT(*) FROM {db}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='LEDGER'")
    print(f"connected as {os.environ['SNOWFLAKE_USER']}; {cur.fetchone()[0]} ledger tables ready in {db}")
    conn.close()


if __name__ == "__main__":
    main()
