"""Compute deeper insights from the collected cases and Census population estimates.

Children (0-17) and young adults (18-25) are computed separately and never pooled; each is compared
with the Census population of the same ages.

Inputs : output/persons.csv, output/circumstances.csv, Census files in data/census/ (via common.py)
Output : report/insights.json (read by report/build_report.py, report/charts.py, report/dashboard_data.py)

Usage: python insights.py
"""
import collections
import json
import re
import statistics

from common import RACE_ORDER, ROOT, age_band, census, last_run_date, parse_date, read_csv, state_name

COLLECTED = last_run_date()  # cases are "open" as of the latest collection run
RECENT_FROM = 2016  # population comparisons use cases from the last ~10 years

COUNTRIES = ("Mexico|Guatemala|Honduras|El Salvador|Nicaragua|Costa Rica|Panama|Belize|Cuba|Haiti|"
             "Dominican Republic|Jamaica|Trinidad|Colombia|Venezuela|Ecuador|Peru|Bolivia|Brazil|Argentina|"
             "Chile|Paraguay|Uruguay|Canada|England|United Kingdom|Ireland|France|Germany|Italy|Spain|"
             "Portugal|Greece|Netherlands|Poland|Ukraine|Russia|Romania|Turkey|Israel|Lebanon|Syria|Jordan|"
             "Iraq|Iran|Saudi Arabia|Kuwait|Yemen|Egypt|Libya|Tunisia|Algeria|Morocco|Nigeria|Ghana|Kenya|"
             "Somalia|Ethiopia|Sudan|Senegal|Liberia|Sierra Leone|South Africa|India|Pakistan|Bangladesh|"
             "Afghanistan|Nepal|Sri Lanka|China|Japan|Korea|Taiwan|Vietnam|Cambodia|Laos|Thailand|"
             "Philippines|Indonesia|Malaysia|Australia|New Zealand|Fiji|Samoa|Tonga")
COUNTRY_RE = re.compile(rf"\b({COUNTRIES})\b")
DIGITAL_RE = re.compile(r"\b(?:snap ?chat|instagram|facebook|tik ?tok|twitter|social media|text(?:ed|s|ing)?|"
                        r"cell ?phone|phone (?:was|has been|pinged|went)|pinged|messag\w+|online|internet|"
                        r"app\b|whatsapp|discord|dating)\b", re.I)
FOSTER_RE = re.compile(r"\b(?:foster|group home|placement|shelter|residential (?:facility|treatment)|"
                       r"DCFS|CPS|DHS custody|state custody|youth home|children'?s home)\b", re.I)


def age_of(p):
    try:
        return int(p["age_missing_min"])
    except ValueError:
        return None


# --------------------------------------------------------------------------- main

GROUPS = {"child": (0, 17), "adult": (18, 25)}  # analyzed apart; never pooled


def main():
    P = {p["person_key"]: p for p in read_csv("output/persons.csv")}
    C = {c["person_key"]: c for c in read_csv("output/circumstances.csv")}
    out = {"collected": COLLECTED.isoformat(), "recent_from": RECENT_FROM}
    for group, (lo, hi) in GROUPS.items():
        rows = []
        for k, p in P.items():
            if p["age_group"] != group or p["status"] == "delisted":  # open cases only
                continue
            a, d = age_of(p), parse_date(p["last_contact_date"])
            rows.append(dict(key=k, p=p, c=C[k], age=a, band=age_band(a), date=d, sex=p["sex"].lower(),
                             race=p["race_ethnicity"] or None,
                             type=C[k]["how_missing"], text=p["circumstances"]))
        out[group] = compute(rows, lo, hi, *census(lo, hi))
    (ROOT / "report").mkdir(exist_ok=True)
    (ROOT / "report/insights.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    return out


def compute(rows, lo, hi, pop_state, pop_race, pop_state_race):
    """All insights for one age group; population comparisons use the same ages (lo-hi)."""
    I = {"ages": [lo, hi]}
    recent = [r for r in rows if r["date"] and r["date"].year >= RECENT_FROM]
    I["n_all"], I["n_recent"] = len(rows), len(recent)
    bands = ("0-11", "12-17") if hi < 18 else ("18-25",)

    # 1. Age and sex -----------------------------------------------------------
    ages = collections.Counter((r["age"], r["sex"]) for r in rows if r["age"] is not None)
    I["age_sex"] = [[a, ages[(a, "female")], ages[(a, "male")]] for a in range(lo, hi + 1)]
    teen = [r for r in rows if r["band"] == "12-17"]
    I["peak_age"] = max(range(lo, hi + 1), key=lambda a: ages[(a, "female")] + ages[(a, "male")])
    top3 = sorted(range(lo, hi + 1), key=lambda a: -(ages[(a, "female")] + ages[(a, "male")]))[:3]
    I["top3_ages"] = sorted(top3)
    I["top3_ages_share"] = sum(ages[(a, s)] for a in top3 for s in ("female", "male")) / len(rows)
    I["female_share"] = {b: sum(r["sex"] == "female" for r in rows if r["band"] == b) /
                         max(1, sum(r["band"] == b for r in rows)) for b in bands}
    I["female_share_all"] = sum(r["sex"] == "female" for r in rows) / len(rows)
    I["female_share_by_type"] = {}
    for t in ("Runaway / left voluntarily", "Outdoors / water (lost, drowning, accident)",
              "Possible foul play / homicide", "Family abduction", "Non-family abduction"):
        sub = [r for r in rows if r["type"] == t and r["sex"] in ("female", "male")]
        I["female_share_by_type"][t] = [sum(r["sex"] == "female" for r in sub), len(sub)]

    # 2. Race vs population (recent cases) -----------------------------------
    rc = collections.Counter()
    for r in recent:
        rc[r["race"] or "Unknown"] += 1
    known = sum(v for k, v in rc.items() if k != "Unknown")
    pop_total = sum(pop_race.values())
    I["race"] = [[k, rc[k], rc[k] / known, pop_race[k] / pop_total, (rc[k] / known) / (pop_race[k] / pop_total)]
                 for k in RACE_ORDER]
    I["race_unknown"], I["race_known"] = rc["Unknown"], known
    I["race_by_source"] = {}
    for src in ("namus", "ncmec"):
        sc_ = collections.Counter(r["race"] for r in recent if r["key"].startswith(src))
        kn = sum(v for k, v in sc_.items() if k)
        I["race_by_source"][src] = {k: sc_[k] / kn for k in RACE_ORDER} | {"n": kn}
    mig = re.compile(r"\b(?:border|crossing|crossed|migrant|immigra\w*|undocumented|smuggl\w*|coyote|"
                     r"Rio Grande|unaccompanied|refugee|ORR)\b", re.I)
    hisp = [r for r in recent if r["race"] == "Hispanic"]
    I["hispanic_migration_related"] = [sum(bool(mig.search(r["text"])) for r in hisp), len(hisp)]
    # Cases come disproportionately from some states; compare each race with the population of the states
    # the cases come from (weighted by each state's share of known-race cases), not only with the nation.
    st_cases = collections.Counter()
    for r in recent:
        if r["race"]:
            st = r["p"]["last_contact_state"].strip()
            st = state_name(st)
            if pop_state.get(st):
                st_cases[st] += 1
    n_st = sum(st_cases.values())
    expected = {k: sum(w / n_st * pop_state_race[(st, k)] / pop_state[st] for st, w in st_cases.items())
                for k in RACE_ORDER}
    I["race_state_adjusted"] = [[k, rc[k] / known, expected[k], (rc[k] / known) / expected[k] if expected[k] else None]
                                for k in RACE_ORDER]
    I["pop_group"] = pop_total

    # 3. Per-capita by state (recent) ----------------------------------------
    sc = collections.Counter()
    for r in recent:
        s = r["p"]["last_contact_state"].strip()
        s = state_name(s)
        sc[s] += 1
    rates = [[s, sc[s], pop_state[s], 100000 * sc[s] / pop_state[s]] for s in pop_state if pop_state[s]]
    rates.sort(key=lambda x: -x[3])
    I["state_rates"] = rates
    I["national_rate"] = 100000 * sum(sc[s] for s in pop_state) / sum(pop_state.values())
    I["state_unmatched"] = {s: v for s, v in sc.items() if s not in pop_state}
    split = collections.defaultdict(collections.Counter)
    for r in recent:
        s = r["p"]["last_contact_state"].strip()
        split[state_name(s)][r["key"].split(":")[0]] += 1
    I["state_source_split"] = {s: dict(split[s]) for s, *_ in rates}

    # 4. Seasonality. Exact dates only (Jan 1 is often a placeholder), and cases from the last 12 months
    #    are left out: open recent cases pile up in the current month and would fake a peak.
    # Months differ in length (and January 1 is excluded), so shares are adjusted to cases per day before
    # comparing months; raw shares are kept as raw_shares.
    days = [30, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    def months(sub):
        m = collections.Counter(r["date"].month for r in sub if r["date"] and (r["date"].month, r["date"].day) != (1, 1)
                                and (COLLECTED - r["date"]).days > 365)
        tot = sum(m.values())
        raw = [m[i] / tot if tot else 0 for i in range(1, 13)]
        per_day = [m[i] / days[i - 1] for i in range(1, 13)]
        s = sum(per_day)
        return [v / s if s else 0 for v in per_day], raw, tot
    I["jan1_share"] = sum(1 for r in rows if r["date"] and (r["date"].month, r["date"].day) == (1, 1)) / len(rows)
    I["season"] = {}
    for label, sub in (("All cases", rows),
                       ("Lost, drowned or accident outdoors", [r for r in rows if r["type"].startswith("Outdoors")])):
        shares, raw, tot = months(sub)
        I["season"][label] = {"shares": shares, "raw_shares": raw, "n": tot}

    # 5. How long cases stay open ---------------------------------------------
    yrs = [(COLLECTED - r["date"]).days / 365.25 for r in rows if r["date"]]
    I["years_open_median"] = statistics.median(yrs)
    I["years_open_buckets"] = [[lab, sum(lo <= y < hi for y in yrs)] for lab, lo, hi in (
        ("Under 1 year", 0, 1), ("1-5 years", 1, 5), ("5-10 years", 5, 10), ("10-20 years", 10, 20),
        ("20-40 years", 20, 40), ("40+ years", 40, 999))]
    I["years_open_by_type"] = {}
    for t in ("Runaway / left voluntarily", "Family abduction", "Non-family abduction",
              "Outdoors / water (lost, drowning, accident)", "Possible foul play / homicide", "Not stated"):
        y = [(COLLECTED - r["date"]).days / 365.25 for r in rows if r["type"] == t and r["date"]]
        I["years_open_by_type"][t] = [statistics.median(y) if y else None, len(y)]
    I["source_recent_share"] = {}
    for src in ("namus", "ncmec"):
        y = [(COLLECTED - r["date"]).days / 365.25 for r in rows if r["key"].startswith(src) and r["date"]]
        I["source_recent_share"][src] = [statistics.median(y), sum(v < 1 for v in y) / len(y), len(y)]

    # 6. Family abductions abroad ---------------------------------------------
    fam = [r for r in rows if r["type"] == "Family abduction"]
    cc = collections.Counter()
    abroad = 0
    for r in fam:
        found = {("Korea" if m == "Korea" else m) for m in COUNTRY_RE.findall(r["text"])}
        found.discard("Puerto Rico")
        if found:
            abroad += 1
            cc.update(found)
    I["fam_n"], I["fam_abroad"], I["fam_countries"] = len(fam), abroad, cc.most_common(10)

    # 8. Foster care / group homes among teens --------------------------------
    teen_detail = [r for r in teen if r["c"]["places_mentioned"] or r["c"]["activities_mentioned"]]
    teen_run = [r for r in teen if r["type"].startswith("Runaway")]
    I["foster_teen"] = [sum(bool(FOSTER_RE.search(r["text"])) for r in teen), len(teen), len(teen_detail)]
    I["foster_teen_runaway"] = [sum(bool(FOSTER_RE.search(r["text"])) for r in teen_run), len(teen_run)]

    # 9. Digital trail by era ---------------------------------------------------
    eras = (("Before 2000", 0, 2000), ("2000-2009", 2000, 2010), ("2010-2019", 2010, 2020), ("2020-2026", 2020, 2100))
    I["digital"] = []
    for lab, lo, hi in eras:
        sub = [r for r in rows if r["date"] and lo <= r["date"].year < hi and len(r["text"]) > 60]
        I["digital"].append([lab, sum(bool(DIGITAL_RE.search(r["text"])) for r in sub), len(sub)])

    # 10. Missing together -----------------------------------------------------
    sib = 0
    for r in rows:
        if r["key"].startswith("ncmec"):
            sib += r["p"]["with_other_children"] == "1"
    I["ncmec_with_companions"] = [sib, sum(r["key"].startswith("ncmec") for r in rows)]
    return I


if __name__ == "__main__":
    out = main()
    for g in GROUPS:
        I = out[g]
        print(f"== {g}: n={I['n_all']} recent={I['n_recent']} peak={I['peak_age']} female={I['female_share_all']:.0%}")
        print("  race x:", {r[0]: round(r[4], 2) for r in I["race"]})
        print("  years open by type:", {k: v[0] and round(v[0], 1) for k, v in I["years_open_by_type"].items()})
        print("  top states:", [(x[0], x[1], round(x[3], 1)) for x in I["state_rates"][:5]])
