"""Summarize output/*.csv into report/facts.json for build_report.py.

Children (age_group "child") and young adults ("adult", 18-25) are summarized separately and never
pooled. Only cases still open on the latest collection date are counted.

Usage: python report/make_facts.py
"""
import collections
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = json.loads((ROOT / "data/state.json").read_text("utf-8"))
LAST_RUN = dt.date.fromisoformat(STATE["runs"][-1]["date"])
GROUP_BANDS = {"child": ("0-11", "12-17"), "adult": ("18-25",)}


def load(p):
    return list(csv.DictReader(open(ROOT / p, encoding="utf-8-sig")))


def band(a):
    try:
        a = int(a)
    except ValueError:
        return None
    return "0-11" if a < 12 else "12-17" if a < 18 else "18-25"


def split(s):
    return [x for x in s.split("; ") if x]


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


def main():
    P = {p["person_key"]: p for p in load("output/persons.csv")}
    open_keys = {k for k, p in P.items() if p["status"] != "delisted"}
    C = [c for c in load("output/circumstances.csv") if c["person_key"] in open_keys]
    E = load("output/events.csv")
    ncmec_files = list((ROOT / "data/raw/ncmec").glob("*.json"))
    F = {
        "collected": f"{LAST_RUN:%B} {LAST_RUN.day}, {LAST_RUN.year}",
        "runs": len(STATE["runs"]),
        "first_run": STATE["runs"][0]["date"],
        "n_open": len(C),
        "delisted_so_far": sum(1 for p in P.values() if p["status"] == "delisted"),
        "delisted_children": sum(1 for p in P.values() if p["status"] == "delisted" and p["age_group"] == "child"),
        "namus_cases": sum(1 for f in (ROOT / "data/raw/namus").glob("*.json") if not f.stem.endswith(".delisted")),
        "ncmec_unidentified_removed": sum(
            json.load(open(f, encoding="utf-8"))["childBean"].get("caseType") == "unidentified" for f in ncmec_files),
        "unknown_age": sum(1 for c in C if c["age_group"] == "unknown"),
        "child": summarize(P, C, E, "child"),
        "adult": summarize(P, C, E, "adult"),
    }
    F["ncmec_cases"] = len(ncmec_files)
    (ROOT / "report/facts.json").write_text(json.dumps(F, indent=1), "utf-8")
    print(f"wrote report/facts.json: {F['n_open']} open ({F['child']['n']} children, {F['adult']['n']} adults, "
          f"{F['unknown_age']} unknown age); {F['delisted_so_far']} found so far")


if __name__ == "__main__":
    main()
