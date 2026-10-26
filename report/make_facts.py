"""Summarize output/*.csv into report/facts.json for build_report.py.

Children (age_group "child") and young adults ("adult", 18-25) are summarized separately and never
pooled. Only cases still open on the latest collection date are counted.

Usage: python report/make_facts.py
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: summarize the case tables into report/facts.json: counts by how people went
# missing, by age band, places and activities mentioned, timeline counts, cases found so far and the
# early-resolution figures. Children and young adults are summarized separately; only cases still open
# on the latest collection date are counted.
#
# Python ideas: functions that return dicts, collections.Counter(...).most_common(), dict lookups with
# .get(), generator expressions inside sum(), reading shared helpers from common.py.
# ===================================================================================================
import collections
import datetime as dt
import json
import sys
from pathlib import Path

# This script lives in report/, so we add the project root to Python's search path before importing
# the shared helpers in common.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, age_band, disk_cached, load_state, read_csv  # noqa: E402

STATE = load_state()
LAST_RUN = dt.date.fromisoformat(STATE["runs"][-1]["date"])
GROUP_BANDS = {"child": ("0-11", "12-17"), "adult": ("18-25",)}  # which age bands belong to each group (children are split 0-11 and 12-17)


band = age_band


# NCMEC's search also returns posters for unidentified deceased children. They are not missing-person
# cases, so they are counted (to report them) and excluded. The count is cached because it means opening
# 3,700 files.
def unidentified_posters(files):
    """NCMEC posters for unidentified deceased children (not missing-person cases); counted once per change."""
    return disk_cached("ncmec_unidentified", files, lambda: sum(
        json.load(open(f, encoding="utf-8"))["childBean"].get("caseType") == "unidentified" for f in files), "1")


def split(s):
    return [x for x in s.split("; ") if x]


# All summary figures for one age group. P = persons, C = circumstances, E = events.
def summarize(P, C, E, group):
    C = [c for c in C if c["age_group"] == group]
    keys = {c["person_key"] for c in C}
    persons = {k: P[k] for k in keys}
    G = {"n": len(C),
         "both": sum(p["sources"] == "namus+ncmec" for p in persons.values()),
         "any_detail": sum(bool(c["places_mentioned"] or c["activities_mentioned"]) for c in C),
         "coords": sum(bool(p["last_contact_lat"]) for p in persons.values()),
         "type": collections.Counter(c["how_missing"] for c in C).most_common(),
         "ncmec_label": collections.Counter(p["case_type"] for p in persons.values()
                                            if "ncmec" in p["sources"] and p["case_type"]).most_common()}
    era = collections.Counter()
    for p in persons.values():
        y = p["last_contact_date"][:4]
        if y.isdigit():
            y = int(y)
            era["Before 1990" if y < 1990 else "1990-2009" if y < 2010 else "2010-2019" if y < 2020 else "2020-2026"] += 1
    G["era"] = [(k, era[k]) for k in ("Before 1990", "1990-2009", "2010-2019", "2020-2026")]
    G["bands"] = {}
    for b in GROUP_BANDS[group]:
        L = [c for c in C if band(c["age_missing"]) == b]
        G["bands"][b] = {
            "n": len(L),
            "type": collections.Counter(c["how_missing"] for c in L).most_common(),
            "place": collections.Counter(x for c in L for x in split(c["places_mentioned"])).most_common(6),
            "act": collections.Counter(x for c in L for x in split(c["activities_mentioned"])).most_common(6),
            "any": sum(bool(c["places_mentioned"] or c["activities_mentioned"]) for c in L),
        }
    NF = [c for c in C if c["how_missing"] == "Non-family abduction"]
    G["nf"] = {"n": len(NF),
               "place": collections.Counter(x for c in NF for x in split(c["places_mentioned"])).most_common(6),
               "band": collections.Counter(band(c["age_missing"]) for c in NF).most_common(),
               "pre1990": sum(P[c["person_key"]]["last_contact_date"][:4] < "1990" for c in NF)}
    Eg = [e for e in E if e["person_key"] in keys]
    G["timeline"] = {
        "before_people": len({e["person_key"] for e in Eg if e["phase"] == "before"}),
        "between_people": len({e["person_key"] for e in Eg if e["phase"] == "between"}),
        "between_types": collections.Counter(e["event_type"] for e in Eg if e["phase"] == "between").most_common(),
        "prior_history": sum(e["event_type"] == "prior_history" for e in Eg),
    }
    return G


# First real outcome data: of NCMEC child cases listed at the previous weekly run, what share were found
# by the latest run, grouped by how long the case had been open. next(...) picks the first band whose
# upper limit fits.
def early_resolution(P):
    """Children on NCMEC at the previous run: share found by the latest run, by how long the case had been open."""
    runs = [r["date"] for r in STATE["runs"]]
    if len(runs) < 2:
        return None
    prev, last = runs[-2], runs[-1]
    bands = (("0-30 days", 30), ("31-90 days", 90), ("91-365 days", 365), ("1-5 years", 1826), ("over 5 years", 10 ** 6))
    at_risk, found = collections.Counter(), collections.Counter()
    for cid, c in STATE["ncmec"].items():
        w = c.get("delisted")
        if c["first_listed"] > prev or (w and w["window_end"] <= prev):
            continue  # not yet listed at the previous run, or already found before it
        p = P.get(f"ncmec:{cid}")
        if not p or p["age_group"] != "child" or not p["last_contact_date"]:
            continue
        days = (dt.date.fromisoformat(prev) - dt.date.fromisoformat(p["last_contact_date"][:10])).days
        band = next(b for b, hi in bands if days <= hi)
        at_risk[band] += 1
        found[band] += bool(w and w["window_end"] == last)
    gap = (dt.date.fromisoformat(last) - dt.date.fromisoformat(prev)).days
    return {"from": prev, "to": last, "days": gap,
            "bands": [[b, found[b], at_risk[b]] for b, _ in bands]}


def main():  # load the tables, keep open cases, summarize each group, write facts.json
    P = {p["person_key"]: p for p in read_csv("output/persons.csv")}
    open_keys = {k for k, p in P.items() if p["status"] != "delisted"}
    C = [c for c in read_csv("output/circumstances.csv") if c["person_key"] in open_keys]
    E = read_csv("output/events.csv")
    ncmec_files = sorted((ROOT / "data/raw/ncmec").glob("*.json"))
    F = {
        "collected": f"{LAST_RUN:%B} {LAST_RUN.day}, {LAST_RUN.year}",
        "runs": len(STATE["runs"]),
        "first_run": STATE["runs"][0]["date"],
        "n_open": len(C),
        "delisted_so_far": sum(1 for p in P.values() if p["status"] == "delisted"),
        "delisted_children": sum(1 for p in P.values() if p["status"] == "delisted" and p["age_group"] == "child"),
        "namus_cases": sum(1 for f in (ROOT / "data/raw/namus").glob("*.json") if not f.stem.endswith(".delisted")),
        "ncmec_unidentified_removed": unidentified_posters(ncmec_files),
        "unknown_age": sum(1 for c in C if c["age_group"] == "unknown"),
        "child": summarize(P, C, E, "child"),
        "adult": summarize(P, C, E, "adult"),
    }
    F["ncmec_cases"] = len(ncmec_files)
    F["early_resolution"] = early_resolution(P)
    (ROOT / "report/facts.json").write_text(json.dumps(F, indent=1), "utf-8")
    print(f"wrote report/facts.json: {F['n_open']} open ({F['child']['n']} children, {F['adult']['n']} adults, "
          f"{F['unknown_age']} unknown age); {F['delisted_so_far']} found so far")


if __name__ == "__main__":
    main()
