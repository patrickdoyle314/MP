"""Open-case metrics with pandas and NumPy, children and young adults separately (never pooled).

1. How long open cases have been open, and the resolution rate that implies at each case age
   (from the open-case snapshot: under steady inflow, the density of open cases by age falls at the
   rate cases are resolved).
2. Cases found so far: cases that dropped off the public listings since weekly collection began.
3. FBI NCIC juvenile flows: records closed each year (inferred) and average days open
   (the same figures sql/ncic_flows.sql computes; tests check they agree).

Writes aggregates only to results/. Counts under 5 are shown as "<5" (the repository is public).

Usage: python analysis/open_case_metrics.py   (after collect.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SUPPRESS = 5
AGE_EDGES = np.array([0, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 30, 40, 50, 60])  # years since last seen


def suppress(n: int):
    return n if n >= SUPPRESS else f"<{SUPPRESS}"


# --------------------------------------------------------------------------- open-case snapshot

def load_cases() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "output/persons.csv", encoding="utf-8-sig",
                     usecols=["person_key", "age_group", "status", "last_contact_date", "sources"])
    df["last_contact"] = pd.to_datetime(df["last_contact_date"].str[:10], errors="coerce")
    return df[df["age_group"].isin(["child", "adult"])]


def latest_run_date() -> pd.Timestamp:
    runs = json.loads((ROOT / "data/state.json").read_text("utf-8"))["runs"]
    return pd.Timestamp(runs[-1]["date"])


def implied_resolution_rate(years_open: np.ndarray, edges: np.ndarray = AGE_EDGES) -> pd.DataFrame:
    """Open cases per year of case age in each bin, and the rate (per year) at which that density falls
    between neighbouring bins: -d ln(density) / d age. Assumes roughly steady inflow."""
    counts, _ = np.histogram(years_open, bins=edges)
    width = np.diff(edges)
    mid = (edges[:-1] + edges[1:]) / 2
    density = counts / width
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = -np.diff(np.log(density)) / np.diff(mid)
    return pd.DataFrame({
        "years_open_from": edges[:-1], "years_open_to": edges[1:], "open_cases": counts,
        "cases_per_year_of_age": np.round(density, 1),
        "implied_resolution_rate_per_year": np.round(np.append(rate, np.nan), 3),
    })


def snapshot_metrics(cases: pd.DataFrame, as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    open_ = cases[cases["status"] != "delisted"].dropna(subset=["last_contact"])
    open_ = open_.assign(years_open=(as_of - open_["last_contact"]).dt.days / 365.25)
    tables, summary = [], []
    for group, g in open_.groupby("age_group"):
        t = implied_resolution_rate(g["years_open"].to_numpy()).assign(age_group=group)
        tables.append(t)
        found = int(((cases["age_group"] == group) & (cases["status"] == "delisted")).sum())
        summary.append({"age_group": group, "open_cases": len(g),
                        "median_years_open": round(float(np.median(g["years_open"])), 1),
                        "share_open_under_1_year": round(float(np.mean(g["years_open"] < 1)), 3),
                        "found_since_weekly_collection_began": suppress(found)})
    by_age = pd.concat(tables, ignore_index=True)
    by_age["open_cases"] = by_age["open_cases"].map(suppress)
    cols = ["age_group"] + [c for c in by_age.columns if c != "age_group"]
    return by_age[cols], pd.DataFrame(summary)


# --------------------------------------------------------------------------- FBI NCIC flows

def ncic_flows() -> pd.DataFrame:
    """Juvenile NCIC records: closed in year t = active(t-1) + entered(t) - active(t), when both
    year-ends are published; average days open = 365 * active / entered."""
    n = pd.read_csv(ROOT / "models/ncic_juvenile_by_year.csv").sort_values("year")
    n = n.dropna(subset=["entries_u18"]).astype({"year": int})
    prev = n["active_u18_dec31"].shift(1)
    consecutive = n["year"].diff() == 1
    n["closed_u18"] = np.where(consecutive, prev + n["entries_u18"] - n["active_u18_dec31"], np.nan)
    n["avg_days_open"] = (365 * n["active_u18_dec31"] / n["entries_u18"]).round(1)
    n["active_change_pct"] = np.where(consecutive, (100 * (n["active_u18_dec31"] / prev - 1)).round(1), np.nan)
    for c in ("entries_u18", "active_u18_dec31", "closed_u18"):
        n[c] = n[c].round().astype("Int64")
    return n[["year", "entries_u18", "active_u18_dec31", "closed_u18", "avg_days_open", "active_change_pct"]]


def main():
    RESULTS.mkdir(exist_ok=True)
    by_age, summary = snapshot_metrics(load_cases(), latest_run_date())
    by_age.to_csv(RESULTS / "open_cases_by_years_open.csv", index=False)
    summary.to_csv(RESULTS / "open_case_summary.csv", index=False)
    flows = ncic_flows()
    flows.to_csv(RESULTS / "ncic_juvenile_flows.csv", index=False)
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(summary.to_string(index=False), "\n")
        print(by_age[by_age.age_group == "child"].to_string(index=False), "\n")
        print(flows.to_string(index=False))


if __name__ == "__main__":
    main()
