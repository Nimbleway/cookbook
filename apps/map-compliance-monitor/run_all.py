"""One-command pipeline: setup agent → discover → compute violations → act.

  python run_all.py                 # full catalog (resumable)
  python run_all.py --limit 5       # small batch

Discovery is live (WSA runs). compute + actions are local/deterministic.
The `max`-effort re-run for thin SKUs is intentionally NOT run here — it is
permission-gated (run `python discover.py --skus <ids> --effort max --force`
only after explicit approval).
"""
import argparse
import subprocess
import sys

import config as C


def run(cmd: list[str]):
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run([sys.executable, *cmd])
    if r.returncode != 0:
        sys.exit(f"step failed: {cmd}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(["setup_agent.py"])
    disc = ["discover.py"]
    if args.limit:
        disc += ["--limit", str(args.limit)]
    run(disc)
    run(["compute_violations.py"])
    run(["actions.py"])
    print(f"\nDone. Dashboard: streamlit run app.py   (data in {C.DATA})")


if __name__ == "__main__":
    main()
