"""Write this project's exchange outbox (contract v1.0, see exchange/EXCHANGE.md).

Aggregates only: counts of open cases by federal fiscal year and state, plus optional tag counts
(rules in exchange/tags.local.json, never committed) and counts in counties listed by a peer outbox.

Usage: python exchange/export_exchange.py [--peer ../<peer-folder>/exchange/outbox]
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: share this project's numbers with the companion UC-Placement project WITHOUT
# sharing any records. It writes aggregate counts (by fiscal year and state, children and young adults
# as separate measures) to exchange/outbox/, following the contract in exchange/EXCHANGE.md.
#
# Privacy rule: counts under 5 are marked "not publishable" so nothing small enough to point to a person
# is ever published. Local tag rules live in exchange/tags.local.json, which is never committed.
#
# Python ideas: argparse options, Counter keyed by tuples, writing CSV and JSON, a version check
# between two projects (a "contract").
# ===================================================================================================
import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, USPS, census, fiscal_year, read_csv, state_code  # noqa: E402

HERE = ROOT / "exchange"
OUTBOX = HERE / "outbox"
CONTRACT_VERSION = "1.0"  # both projects must speak the same major version of the file format
THRESHOLD = 5  # counts below this are flagged as not publishable
COLUMNS = ["geo_level", "state", "county_key", "county_name", "fiscal_year", "measure", "value", "publishable"]

def county_key(name, st):  # a comparable county key such as 'harris|TX' (lower case, no 'County')
    n = re.sub(r"\s+(county|parish|borough|census area|municipality)$", "", (name or "").strip().lower())
    return f"{n}|{st}" if n and st else ""


# Optional local rules ("tags") that count cases whose summary matches a pattern. Kept out of the
# public repository on purpose.
def load_tags():
    path = HERE / "tags.local.json"
    if not path.exists():
        return {}
    return {k: re.compile(v, re.I) for k, v in json.loads(path.read_text("utf-8")).items()}


# Read the companion project's outbox to learn which counties it lists for each year, after checking
# both sides use the same contract version.
def load_peer_counties(peer):
    """{(fiscal_year, county_key)} for county rows in a peer outbox, after a version check."""
    if not peer:
        return set(), None
    manifest = json.loads((peer / "manifest.json").read_text("utf-8"))
    if manifest["contract_version"].split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        raise SystemExit(f"peer contract {manifest['contract_version']} does not match {CONTRACT_VERSION}")
    rows = csv.DictReader(open(peer / "aggregates.csv", encoding="utf-8"))
    keys = {(int(r["fiscal_year"]), r["county_key"]) for r in rows
            if r["geo_level"] == "county" and r["fiscal_year"] and r["county_key"]}
    return keys, manifest["producer"]


# Count open cases into buckets keyed by (level, state, fiscal year, measure). Children and young
# adults land in different measures, so they can never be added together by mistake.
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peer", type=Path, help="a peer project's exchange/outbox folder")
    a = ap.parse_args()
    tags = load_tags()
    peer_counties, peer_name = load_peer_counties(a.peer) if a.peer else (set(), None)

    counts = collections.Counter()  # (geo_level, state, fy, measure) -> n
    skipped = collections.Counter()
    for p in read_csv("output/persons.csv"):
        # Children and adults never share a count: age_group comes from collect.py
        if p["status"] == "delisted":  # found since an earlier run: no longer an open case
            skipped["no longer listed (found)"] += 1
            continue
        group = p["age_group"]
        if group not in ("child", "adult"):
            skipped["age unknown or straddles 18"] += 1
            continue
        try:
            fy = fiscal_year(dt.date.fromisoformat(p["last_contact_date"][:10]))
        except ValueError:
            skipped["no last-contact date"] += 1
            continue
        st = state_code(p["last_contact_state"])
        if not st:
            skipped["state outside the 50 states, DC and PR"] += 1
        base = "open_cases_u18" if group == "child" else "open_cases_18_25"
        measures = [base]
        if group == "child":
            matched = [t for t, rx in tags.items() if rx.search(p["circumstances"])]
            measures += [f"open_cases_u18_tag:{t}" for t in matched]
            ck = county_key(p["last_contact_county"], st)
            if ck:
                counts[("national", "", fy, "open_cases_u18_with_county")] += 1
                if (fy, ck) in peer_counties:
                    counts[("national", "", fy, "open_cases_u18_in_peer_county_same_fy")] += 1
                    for t in matched:
                        counts[("national", "", fy, f"open_cases_u18_tag:{t}_in_peer_county_same_fy")] += 1
        for m in measures:
            counts[("national", "", fy, m)] += 1
            if st:
                counts[("state", st, fy, m)] += 1

    pop = collections.Counter()
    if (ROOT / "data/census/sc-est2024-agesex-civ.csv").exists():
        for name, v in census(0, 17)[0].items():
            if name in USPS:
                pop[USPS[name]] += v

    OUTBOX.mkdir(parents=True, exist_ok=True)
    with open(OUTBOX / "aggregates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        n = 0
        for (lvl, st, fy, m), v in sorted(counts.items(), key=lambda x: (x[0][3], x[0][0], x[0][1], x[0][2])):
            w.writerow([lvl, st, "", "", fy, m, v, str(v >= THRESHOLD).lower()])
            n += 1
        for st, v in sorted(pop.items()):
            w.writerow(["state", st, "", "", "", "census_pop_u18_2024", v, "true"])
            n += 1

    measures = {
        "open_cases_u18": "Open cases, under 18 when last seen, by fiscal year of last contact",
        "open_cases_18_25": "Open cases, aged 18-25 when last seen, by fiscal year of last contact",
        "open_cases_u18_with_county": "Under-18 open cases whose record names a county",
        "census_pop_u18_2024": "Census Bureau Vintage 2024 civilian population aged 0-17 (state)",
    }
    for t in tags:
        measures[f"open_cases_u18_tag:{t}"] = f"Under-18 open cases matching local tag rule '{t}'"
    if peer_counties:
        measures["open_cases_u18_in_peer_county_same_fy"] = f"Under-18 cases last seen in a county listed by {peer_name} for that fiscal year"
        for t in tags:
            measures[f"open_cases_u18_tag:{t}_in_peer_county_same_fy"] = f"Tag '{t}' cases in a county listed by {peer_name} for that fiscal year"
    manifest = {
        "producer": "MP",
        "contract_version": CONTRACT_VERSION,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source": "Open NamUs and NCMEC cases, ages 0-25, from output/persons.csv (see README for snapshot date)",
        "publication_threshold": THRESHOLD,
        "row_count": n,
        "peer_used": peer_name,
        "skipped_records": dict(skipped),
        "measures": measures,
    }
    (OUTBOX / "manifest.json").write_text(json.dumps(manifest, indent=1), "utf-8")
    print(f"wrote {n} rows to {OUTBOX} (tags: {sorted(tags) or 'none'}; peer: {peer_name or 'none'})")


if __name__ == "__main__":
    main()
