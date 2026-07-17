"""Post a ticker's scorecard summary to Slack (the 'agents act' layer).

Usage: python slack_post.py NVDA [MSFT ...]   # or no args = all ingested tickers
"""
import os
import sys

import requests

import config  # noqa: F401
from setup_snowflake import connect

VERDICT_EMOJI = {"beat": "🟢", "miss": "🔴", "inline": "🟡", "not_guided": "⚪"}


def scorecard(cur, db, ticker):
    cur.execute(f"""
        SELECT fiscal_quarter, basis, guided_range_raw, guided_value_raw,
               actual_value_raw, metric_verdict
        FROM {db}.LEDGER.V_HEADLINE_DEDUP
        WHERE ticker = %s
        ORDER BY report_date DESC""", (ticker,))
    return cur.fetchall()


def post(ticker, rows, webhook):
    lines = [f"*{ticker} — guidance vs actuals* (revenue, most recent first)"]
    for fq, _metric, grange, gval, aval, verdict in rows[:8]:
        emoji = VERDICT_EMOJI.get(verdict, "⚪")
        lines.append(f"{emoji} *{fq}*: guided {grange or gval or 'n/a'} → actual {aval or 'n/a'} ({verdict})")
    beats = sum(1 for r in rows if r[5] == "beat")
    misses = sum(1 for r in rows if r[5] == "miss")
    lines.append(f"_Track record: {beats} beats / {misses} misses over {len(rows)} quarters. "
                 f"Every number cited — full audit trail in the Earnings Desk app._")
    r = requests.post(webhook, json={"text": "\n".join(lines)}, timeout=30)
    r.raise_for_status()


def main():
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("SLACK_WEBHOOK_URL is not set; configure .env to enable Slack posting.")
    db = os.environ.get("SNOWFLAKE_DATABASE", "EARNINGS_DESK")
    conn = connect(); cur = conn.cursor()
    tickers = sys.argv[1:]
    if not tickers:
        cur.execute(f"SELECT DISTINCT ticker FROM {db}.LEDGER.GUIDANCE_LEDGER")
        tickers = [r[0] for r in cur.fetchall()]
    for t in sorted(tickers):
        rows = scorecard(cur, db, t)
        if rows:
            post(t, rows, webhook)
            print(f"posted {t} ({len(rows)} quarters)")
    conn.close()


if __name__ == "__main__":
    main()
