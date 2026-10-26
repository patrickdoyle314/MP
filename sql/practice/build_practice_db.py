"""Build a small dummy database for SQL practice (synthetic data; no real cases or people).

Tables (CSV in sql/practice/data/, loaded into sql/practice/practice.duckdb):
  regions(region_id, region_name)
  states(state_code, state_name, region_id)
  agencies(agency_id, agency_name, agency_type, state_code)
  case_types(case_type_id, case_type_name)
  cases(case_id, agency_id, case_type_id, age_group, reported_on, resolved_on)

Generated with NumPy from a fixed seed, so every build is identical.

Usage: python sql/practice/build_practice_db.py
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: build a small, entirely made-up database for practicing SQL joins and
# aggregates safely (no real cases or people). The fixed random seed makes every build identical.
#
# Python ideas: NumPy random generators, pandas DataFrames built from lists and arrays,
# np.select (choose a value by condition, like CASE WHEN), loading DataFrames into DuckDB tables.
# ===================================================================================================
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SEED = 20261023  # fixed seed: the same 'random' data every time, so tests are repeatable
N_CASES = 2000


def build_tables(seed: int = SEED, n_cases: int = N_CASES) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    regions = pd.DataFrame({"region_id": [1, 2, 3, 4], "region_name": ["Northeast", "Midwest", "South", "West"]})
    states = pd.DataFrame([
        ("NY", "New York", 1), ("PA", "Pennsylvania", 1), ("MA", "Massachusetts", 1),
        ("IL", "Illinois", 2), ("OH", "Ohio", 2), ("MN", "Minnesota", 2),
        ("TX", "Texas", 3), ("FL", "Florida", 3), ("GA", "Georgia", 3),
        ("CA", "California", 4), ("WA", "Washington", 4), ("AZ", "Arizona", 4),
    ], columns=["state_code", "state_name", "region_id"])
    n_agencies = 30
    agencies = pd.DataFrame({
        "agency_id": np.arange(1, n_agencies + 1),
        "agency_name": [f"Dummy Agency {i:02d}" for i in range(1, n_agencies + 1)],
        "agency_type": rng.choice(["Police department", "Sheriff's office", "State police"], n_agencies, p=[.6, .3, .1]),
        "state_code": rng.choice(states["state_code"], n_agencies),
    })
    case_types = pd.DataFrame({"case_type_id": [1, 2, 3, 4, 5],
                               "case_type_name": ["Ran away", "Family abduction", "Non-family abduction",
                                                  "Lost or injured", "Not stated"]})
    type_p = np.array([.55, .08, .02, .05, .30])
    reported = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 700, n_cases), unit="D")
    # Most cases resolve within weeks; abductions and "not stated" take longer and resolve less often
    case_type = rng.choice(case_types["case_type_id"], n_cases, p=type_p)
    # np.select picks a value per case by condition: runaways resolve fastest on average, abductions
    # slowest. Like SQL's CASE WHEN, but on a whole array at once.
    mean_days = np.select([case_type == 1, case_type == 2, case_type == 3], [12, 120, 300], default=60)
    days = rng.exponential(mean_days)
    resolve_p = np.select([case_type == 1, case_type == 2, case_type == 3], [.95, .7, .4], default=.8)
    resolved = rng.random(n_cases) < resolve_p
    resolved_on = (reported + pd.to_timedelta(np.ceil(days), unit="D")).where(resolved)
    cases = pd.DataFrame({
        "case_id": np.arange(1, n_cases + 1),
        "agency_id": rng.integers(1, n_agencies + 1, n_cases),
        "case_type_id": case_type,
        "age_group": rng.choice(["child", "adult"], n_cases, p=[.65, .35]),
        "reported_on": reported.date,
        "resolved_on": pd.Series(resolved_on).dt.date,
    })
    return {"regions": regions, "states": states, "agencies": agencies, "case_types": case_types, "cases": cases}


def main():
    tables = build_tables()
    (HERE / "data").mkdir(exist_ok=True)
    db = HERE / "practice.duckdb"
    db.unlink(missing_ok=True)
    con = duckdb.connect(str(db))
    for name, df in tables.items():
        df.to_csv(HERE / "data" / f"{name}.csv", index=False)
        con.register("frame", df)  # expose a pandas table to DuckDB, copy it into a real table, then let it go
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
        con.unregister("frame")
        print(f"{name}: {len(df)} rows")
    con.close()
    print(f"wrote {db.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
