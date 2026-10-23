"""One scheduled collection run: collect, refresh derived files, log the result.

Meant for a weekly Windows scheduled task (see README > Scheduled runs). Steps:
  1. collect.py          new snapshot; cases that dropped off since the last run become "found" events
  2. circumstances.py    refresh output/circumstances.csv
  3. exchange export     refresh exchange/outbox (with --peer if given)
Each step's output goes to data/logs/<timestamp>.log; one summary line per run is appended to
data/logs/runs.csv. A lock file stops two runs overlapping.

Usage: python scheduled_run.py [--peer <peer outbox folder>]
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "data" / "logs"
LOCK = LOGS / "run.lock"
STALE_LOCK_HOURS = 6


def step(name, args, log):
    log.write(f"\n===== {name}: {' '.join(args)}  ({dt.datetime.now():%Y-%m-%d %H:%M:%S})\n")
    log.flush()
    started = time.time()
    rc = subprocess.run([sys.executable, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    log.write(f"===== {name} finished: exit {rc}, {time.time() - started:.0f}s\n")
    log.flush()
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peer", help="a peer project's exchange/outbox folder, passed to the exchange export")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)

    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < STALE_LOCK_HOURS * 3600:
        print(f"another run is in progress ({LOCK}); exiting")
        return 0
    LOCK.write_text(str(os.getpid()))
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    started = dt.datetime.now()
    try:
        with open(LOGS / f"{stamp}.log", "w", encoding="utf-8") as log:
            rc_collect = step("collect", ["collect.py", "--workers", "5"], log)
            rc_circ = step("circumstances", ["circumstances.py", "output/persons.csv"], log) if rc_collect == 0 else None
            export = ["exchange/export_exchange.py"] + (["--peer", a.peer] if a.peer else [])
            rc_export = step("exchange", export, log) if rc_collect == 0 else None

        run = {}
        if rc_collect == 0:
            run = json.loads((ROOT / "data/state.json").read_text("utf-8"))["runs"][-1]
        new_file = not (LOGS / "runs.csv").exists()
        with open(LOGS / "runs.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["started", "finished", "collect_exit", "circumstances_exit", "exchange_exit",
                            "namus_listed", "namus_new", "namus_delisted", "ncmec_listed", "ncmec_new",
                            "ncmec_delisted", "log"])
            nm, nc = run.get("namus", {}), run.get("ncmec", {})
            w.writerow([started.isoformat(timespec="seconds"), dt.datetime.now().isoformat(timespec="seconds"),
                        rc_collect, rc_circ, rc_export, nm.get("listed"), nm.get("new"), nm.get("delisted"),
                        nc.get("listed"), nc.get("new"), nc.get("delisted"), f"{stamp}.log"])
        return rc_collect
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
