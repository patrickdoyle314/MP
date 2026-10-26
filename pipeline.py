"""Rebuild everything from the collected data in one process, with timings.

Each step is an ordinary script, run here exactly as `python <script> <args>` would run it, but in
one interpreter so pandas, NumPy, SciPy and matplotlib load once. Collection itself (network) runs
only with --collect; otherwise the first step rebuilds the outputs from cached raw data.

Usage:
  python pipeline.py                     # rebuild all outputs, report and dashboard data
  python pipeline.py --collect           # collect new data first (as the weekly run does)
  python pipeline.py --from insights     # start at a step
  python pipeline.py --only charts report
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: one command to rebuild every output (data tables, report, charts, dashboard data)
# in the right order, with a timing for each step, so a refresh is quick and repeatable.
#
# Python ideas: a list of tuples as a simple "recipe", runpy (run another script from inside Python),
# try/finally to always restore settings, sys.argv (the command-line arguments a script sees).
# ===================================================================================================
import argparse
import os
import runpy
import sys
import time

import common

ROOT = common.ROOT
PEER = ROOT.parent / "UC-Placement" / "exchange" / "outbox"

# The recipe. Each step is (short name, script, arguments). Order matters: every step reads files that
# earlier steps wrote (for example, the report needs the insights).
STEPS = [  # (name, script, arguments); order matters: each step reads what earlier ones wrote
    ("rebuild", "collect.py", ["--offline"]),
    ("circumstances", "circumstances.py", ["output/persons.csv"]),
    ("facts", "report/make_facts.py", []),
    ("insights", "insights.py", []),
    ("model", "models/stock_flow_ncic.py", []),
    ("charts", "report/charts.py", []),
    ("report", "report/build_report.py", []),
    ("dashboard", "report/dashboard_data.py", []),
    ("exchange", "exchange/export_exchange.py", ["--peer", str(PEER)] if PEER.exists() else []),
    ("metrics", "analysis/open_case_metrics.py", []),
]


# runpy.run_path runs a script exactly as "python script.py" would, but inside this same process, so
# heavy libraries (pandas, matplotlib, SciPy) load only once for the whole rebuild. We temporarily set
# sys.argv (the script's command-line arguments) and restore everything in `finally`.
def run_step(script, args, quiet):
    """Run one script as __main__; returns its exit code."""
    common.read_csv.cache_clear()  # never hand a step a table an earlier step has since rewritten
    old_argv, old_path = sys.argv, list(sys.path)
    sys.argv = [str(ROOT / script), *args]
    sys.path.insert(0, str((ROOT / script).parent))
    out = open(os.devnull, "w") if quiet else None
    old_stdout = sys.stdout
    try:
        if out:
            sys.stdout = out
        runpy.run_path(str(ROOT / script), run_name="__main__")
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.stdout = old_stdout
        if out:
            out.close()
        sys.argv, sys.path[:] = old_argv, old_path


# Parse options, pick the steps to run, then run them in order and stop at the first failure.
# time.perf_counter() is a precise stopwatch for timing each step.
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect", action="store_true", help="collect new data from NamUs and NCMEC first")
    ap.add_argument("--from", dest="start", choices=[s[0] for s in STEPS], help="start at this step")
    ap.add_argument("--only", nargs="+", choices=[s[0] for s in STEPS], help="run only these steps")
    ap.add_argument("--verbose", action="store_true", help="show each step's own output")
    a = ap.parse_args()

    os.chdir(ROOT)
    steps = list(STEPS)
    if a.collect:
        steps[0] = ("collect", "collect.py", ["--workers", "5"])
    if a.start:
        steps = steps[[s[0] for s in steps].index(a.start):]
    if a.only:
        steps = [s for s in steps if s[0] in a.only]

    total = time.perf_counter()
    for name, script, args in steps:
        t = time.perf_counter()
        rc = run_step(script, args, quiet=not a.verbose)
        print(f"{time.perf_counter() - t:6.1f}s  {name:13s} {'ok' if rc == 0 else f'FAILED (exit {rc})'}", flush=True)
        if rc:
            return rc
    print(f"{time.perf_counter() - total:6.1f}s  total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
