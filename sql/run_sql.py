"""Run a SQL file with DuckDB from the project root and save the result as CSV in results/.

Usage:
  python sql/run_sql.py sql/ncic_flows.sql
  python sql/run_sql.py sql/practice/caseload_by_region.sql --db sql/practice/practice.duckdb
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: run any .sql file in this project with DuckDB (a fast database that can query
# CSV files directly) and save the result to results/ as a CSV.
#
# Python ideas: duckdb.connect(), con.sql(...).df() to get a pandas table back, try/finally to always
# close the connection, a lambda (a one-line unnamed function).
# ===================================================================================================
import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent


def run(sql_file: Path, db: Path | None = None):
    con = duckdb.connect(str(db), read_only=True) if db else duckdb.connect()
    con.execute(f"SET file_search_path = '{ROOT.as_posix()}'")  # lets SQL refer to project files by relative path, e.g. 'models/x.csv'
    try:
        return con.sql(Path(sql_file).read_text("utf-8")).df()
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sql_file", type=Path)
    ap.add_argument("--db", type=Path, help="a DuckDB database file to query")
    a = ap.parse_args()
    resolve = lambda p: p if p.is_absolute() else ROOT / p  # make a path absolute relative to the project root
    df = run(resolve(a.sql_file), resolve(a.db) if a.db else None)
    out = ROOT / "results" / (a.sql_file.stem + ".csv")
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print(f"{len(df)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
