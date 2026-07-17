"""Databricks Delta layer: schema + tables + helpers (idempotent)."""
import json

from databricks import sql as dbsql

import config as C

DDL = [
    "CREATE SCHEMA IF NOT EXISTS {s}",
    """CREATE TABLE IF NOT EXISTS {s}.discovery_runs (
        chunk_id STRING, retailer STRING, subcategory STRING, run_id STRING,
        status STRING, item_count INT, wall_clock_s INT, error STRING,
        completed_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS {s}.catalog (
        sku_key STRING, product_name STRING, brand STRING, retailer STRING,
        subcategory STRING, price_usd DOUBLE, price_raw STRING, rating DOUBLE,
        rating_raw STRING, review_count INT, review_count_raw STRING,
        product_url STRING, source_url STRING, observed_at STRING,
        chunk_id STRING, run_id STRING)""",
    """CREATE TABLE IF NOT EXISTS {s}.review_themes (
        sku_key STRING, product_name STRING, retailer STRING, found BOOLEAN,
        kind STRING, theme STRING, quote STRING, quote_source_url STRING,
        run_id STRING, observed_at STRING)""",
    """CREATE TABLE IF NOT EXISTS {s}.gaps (
        gap_id STRING, gap_statement STRING, price_band STRING, subcategory STRING,
        demand_evidence STRING, verdict STRING, evidence_summary STRING,
        closest_matches STRING, verify_run_id STRING, interaction_id STRING,
        linear_issue_id STRING, linear_issue_url STRING, created_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS {s}.merch_rules (
        rule STRING, taught_at TIMESTAMP)""",
]


def connect():
    return dbsql.connect(server_hostname=C.DBX_HOST, http_path=C.DBX_HTTP_PATH,
                         access_token=C.DBX_TOKEN)


def setup():
    with connect() as conn, conn.cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt.format(s=C.DBX_SCHEMA))
        cur.execute(f"SHOW TABLES IN {C.DBX_SCHEMA}")
        print(f"{len(cur.fetchall())} tables ready in {C.DBX_SCHEMA}")


def insert_rows(table, rows):
    """Parameterized batch insert."""
    if not rows:
        return
    cols = list(rows[0].keys())
    ph = ", ".join(["?"] * len(cols))
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO {C.DBX_SCHEMA}.{table} ({', '.join(cols)}) VALUES ({ph})",
            [[r[c] for c in cols] for r in rows])


def query(sql_text, params=None):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql_text, params or [])
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()


if __name__ == "__main__":
    setup()
