"""Backfill the 8-quarter ledger: 24 runs (12 tickers x 2 chunks), 4 concurrent, resumable.

Re-running skips any (ticker, chunk) whose raw JSON already exists in data/raw/.
Usage: python backfill.py [TICKER ...]   (no args = full watchlist)
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import config as C
import wsa


def run_input(ticker, name, fiscal_note, window):
    return (f"Ticker: {ticker} ({name}). Build the guidance-vs-actuals record for the "
            f"{C.CHUNKS[window]} as of today ({date.today().isoformat()}), most recent first. "
            f"For each quarter: the guidance management issued with the prior quarter's results "
            f"(revenue, gross margin, opex, EPS if guided; forward outlook metrics if no formal "
            f"quarterly guidance), the actually reported values for those metrics, and a verdict. "
            f"{fiscal_note}").strip()


def one_chunk(agent_id, ticker, name, note, window):
    out = C.RAW_DIR / f"{ticker}_{window}.json"
    if out.exists():
        return ticker, window, "skipped (exists)", 0
    for attempt in (1, 2, 3):
        t0 = time.time()
        try:
            run = wsa.start_run(agent_id, run_input(ticker, name, note, window))
            result, run_final = wsa.wait_for_result(agent_id, run["id"])
            out.write_text(json.dumps({"run_id": run["id"],
                                       "interaction_id": run_final.get("interaction_id"),
                                       "ticker": ticker, "window": window,
                                       "wall_clock_s": int(time.time() - t0),
                                       "result": result}, indent=1))
            return ticker, window, "ok", int(time.time() - t0)
        except Exception as e:  # RunFailed, HTTP 422s from the result endpoint, transient network
            print(f"  ! {ticker}/{window} attempt {attempt} failed: {e}", flush=True)
            time.sleep(10)
    return ticker, window, "FAILED after 3 attempts", 0


def main():
    agent_id = C.agent_id()
    tickers = sys.argv[1:] or [t for t, _, _ in C.WATCHLIST]
    jobs = [(t, n, f, w) for t, n, f in C.WATCHLIST if t in tickers for w in C.CHUNKS]
    print(f"{len(jobs)} chunks over {len(tickers)} tickers (4 concurrent)")
    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one_chunk, agent_id, t, n, f, w) for t, n, f, w in jobs]
        for fut in as_completed(futures):
            ticker, window, status, secs = fut.result()
            done += 1
            print(f"[{done}/{len(jobs)}] {ticker}/{window}: {status} ({secs}s)", flush=True)
    print("backfill pass complete - rerun to retry any FAILED chunks")


if __name__ == "__main__":
    main()
