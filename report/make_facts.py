"""Summarize output/*.csv into report/facts.json for build_report.py.

Usage: python report/make_facts.py
"""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLLECTED = "October 21, 2026"


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


P = {p["person_key"]: p for p in load("output/persons.csv")}
C = load("output/circumstances.csv")
E = load("output/events.csv")
ncmec_listed = len(list((ROOT / "data/raw/ncmec").glob("*.json")))
ncmec_unidentified = sum(
    json.load(open(f, encoding="utf-8"))["childBean"].get("caseType") == "unidentified"
    for f in (ROOT / "data/raw/ncmec").glob("*.json"))

F = {
    "n": len(C), "collected": COLLECTED,
    "namus_cases": sum(1 for f in (ROOT / "data/raw/namus").glob("*.json") if not f.stem.endswith(".delisted")),
    "ncmec_cases": ncmec_listed, "ncmec_unidentified_removed": ncmec_unidentified,
    "both": sum(p["sources"] == "namus+ncmec" for p in P.values()),
    "any_detail": sum(bool(c["places_mentioned"] or c["activities_mentioned"]) for c in C),
    "coords": sum(bool(p["last_contact_lat"]) for p in P.values()),
    "type": collections.Counter(c["how_missing"] for c in C).most_common(),
    "ncmec_label": collections.Counter(p["case_type"] for p in P.values()
                                       if "ncmec" in p["sources"] and p["case_type"]).most_common(),
}
era = collections.Counter()
for p in P.values():
    y = p["last_contact_date"][:4]
    if y.isdigit():
        y = int(y)
        era["Before 1990" if y < 1990 else "1990-2009" if y < 2010 else "2010-2019" if y < 2020 else "2020-2026"] += 1
F["era"] = [(k, era[k]) for k in ("Before 1990", "1990-2009", "2010-2019", "2020-2026")]

F["bands"] = {}
for b in ("0-11", "12-17", "18-25"):
    L = [c for c in C if band(c["age_missing"]) == b]
    F["bands"][b] = {
        "n": len(L),
        "type": collections.Counter(c["how_missing"] for c in L).most_common(),
        "place": collections.Counter(x for c in L for x in split(c["places_mentioned"])).most_common(6),
        "act": collections.Counter(x for c in L for x in split(c["activities_mentioned"])).most_common(6),
        "any": sum(bool(c["places_mentioned"] or c["activities_mentioned"]) for c in L),
    }

NF = [c for c in C if c["how_missing"] == "Non-family abduction"]
F["nf"] = {
    "n": len(NF),
    "place": collections.Counter(x for c in NF for x in split(c["places_mentioned"])).most_common(6),
    "act": collections.Counter(x for c in NF for x in split(c["activities_mentioned"])).most_common(5),
    "band": collections.Counter(band(c["age_missing"]) for c in NF).most_common(),
    "pre1990": sum(P[c["person_key"]]["last_contact_date"][:4] < "1990" for c in NF),
}
F["timeline"] = {
    "before_people": len({e["person_key"] for e in E if e["phase"] == "before"}),
    "between_people": len({e["person_key"] for e in E if e["phase"] == "between"}),
    "between_types": collections.Counter(e["event_type"] for e in E if e["phase"] == "between").most_common(),
    "prior_history": sum(e["event_type"] == "prior_history" for e in E),
    "vehicles": sum(e["event_type"] == "vehicle" for e in E),
    "companions": sum(e["event_type"] == "companion" for e in E),
}
(ROOT / "report/facts.json").write_text(json.dumps(F, indent=1), "utf-8")
print("wrote report/facts.json:", F["n"], "persons")
