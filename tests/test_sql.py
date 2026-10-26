"""SQL statements must agree with the same calculation in pandas."""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: automatic checks (run with `pytest`). They prove the SQL statements and the
# pandas code compute the same numbers, so either can be trusted.
#
# Python ideas: pytest test functions (any function named test_...), assert statements, a fixture
# (shared setup built once and handed to tests), np.allclose for comparing decimals.
# ===================================================================================================
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis import open_case_metrics
from sql import run_sql
from sql.practice import build_practice_db

ROOT = Path(__file__).resolve().parent.parent


def test_ncic_sql_matches_pandas():  # the SQL and pandas versions of the FBI flows must agree year by year
    sql = run_sql.run(ROOT / "sql/ncic_flows.sql").set_index("year")
    pdf = open_case_metrics.ncic_flows().set_index("year")
    assert list(sql.index) == list(pdf.index)
    both = sql["closed_u18"].notna()
    assert (both == pdf["closed_u18"].notna()).all()
    assert np.allclose(sql.loc[both, "closed_u18"].astype(float), pdf.loc[both, "closed_u18"].astype(float))
    assert np.allclose(sql["avg_days_open"], pdf["avg_days_open"])


def test_ncic_closed_is_flow_identity():  # closed = active at start + entered - active at end, checked for 2025
    sql = run_sql.run(ROOT / "sql/ncic_flows.sql")
    row = sql[sql.year == 2025].iloc[0]
    prev = sql[sql.year == 2024].iloc[0]
    assert row.closed_u18 == prev.active_u18_dec31 + row.entries_u18 - row.active_u18_dec31


@pytest.fixture(scope="module")  # build the practice database once, in a temporary folder, for the tests below
def practice_db(tmp_path_factory):
    import duckdb
    db = tmp_path_factory.mktemp("practice") / "practice.duckdb"
    con = duckdb.connect(str(db))
    tables = build_practice_db.build_tables()
    for name, df in tables.items():
        con.register("frame", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
        con.unregister("frame")
    con.close()
    return db, tables


# Recompute the SQL query's joins and totals with pandas merges and groupby; every row must match.
def test_practice_query_matches_pandas(practice_db):
    db, t = practice_db
    sql = run_sql.run(ROOT / "sql/practice/caseload_by_region.sql", db)
    df = (t["cases"].merge(t["agencies"], on="agency_id").merge(t["states"], on="state_code")
          .merge(t["regions"], on="region_id").merge(t["case_types"], on="case_type_id"))
    df = df[df.age_group == "child"]
    df["days"] = (pd.to_datetime(df.resolved_on) - pd.to_datetime(df.reported_on)).dt.days
    g = df.groupby(["region_name", "case_type_name"]).agg(
        cases=("case_id", "size"), resolved=("resolved_on", "count"), avg_days=("days", "mean"),
        agencies=("agency_id", "nunique"))
    g = g[g.cases >= 5].reset_index()
    m = sql.merge(g, on=["region_name", "case_type_name"])
    assert len(m) == len(sql) == len(g)
    assert (m.cases_x == m.cases_y).all() and (m.resolved_x == m.resolved_y).all()
    assert (m.agencies_reporting == m.agencies).all()
    assert np.allclose(m.avg_days_to_resolve, m.avg_days.round(1))


def test_practice_data_is_deterministic():
    a, b = build_practice_db.build_tables(), build_practice_db.build_tables()
    pd.testing.assert_frame_equal(a["cases"], b["cases"])
