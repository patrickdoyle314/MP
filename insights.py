"""Compute deeper insights from the collected cases and Census population estimates.

Inputs : data/raw/{namus,ncmec}/*.json, output/persons.csv, output/circumstances.csv,
         data/census/sc-est2024-agesex-civ.csv, data/census/sc-est2024-alldata6.csv
Output : report/insights.json (read by report/build_report.py and report/charts.py)

Usage: python insights.py
"""
import collections
import csv
import datetime as dt
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLLECTED = dt.date(2026, 10, 21)
RECENT_FROM = 2016  # population comparisons use cases from the last ~10 years
AGE_MAX = 25

STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
RACE_ORDER = ["Hispanic", "White", "Black", "American Indian / Alaska Native", "Asian",
              "Native Hawaiian / Pacific Islander", "Two or more races"]
NAMUS_RACE = {"White / Caucasian": "White", "Black / African American": "Black",
              "American Indian / Alaska Native": "American Indian / Alaska Native", "Asian": "Asian",
              "Hawaiian / Pacific Islander": "Native Hawaiian / Pacific Islander"}
NCMEC_RACE = {"white": "White", "black": "Black", "hispanic": "Hispanic", "whiteHisp": "Hispanic",
              "blackHisp": "Hispanic", "asian": "Asian", "amInd": "American Indian / Alaska Native",
              "pacific": "Native Hawaiian / Pacific Islander", "biracial": "Two or more races"}
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


def load_csv(p):
    return list(csv.DictReader(open(ROOT / p, encoding="utf-8-sig")))


def age_of(p):
    try:
        return int(p["age_missing_min"])
    except ValueError:
        return None


def band(a):
    return None if a is None else "0-11" if a < 12 else "12-17" if a < 18 else "18-25"


def date_of(p):
    try:
        return dt.date.fromisoformat(p["last_contact_date"][:10])
    except ValueError:
        return None


def race_of(key):
    src, cid = key.split(":", 1)
    if src == "namus":
        d = json.load(open(ROOT / "data/raw/namus" / f"{cid}.json", encoding="utf-8"))
        names = {e["name"] for e in d["subjectDescription"].get("ethnicities") or []} - {"Other", "Uncertain"}
        if "Hispanic / Latino" in names:
            return "Hispanic"
        races = {NAMUS_RACE[n] for n in names if n in NAMUS_RACE}
        return "Two or more races" if len(races) > 1 else (races.pop() if races else None)
    b = json.load(open(ROOT / "data/raw/ncmec" / f"{cid}.json", encoding="utf-8"))["childBean"]
    return NCMEC_RACE.get(b.get("race"))


# --------------------------------------------------------------------------- census

def census():
    """Population aged 0-25 (2024 estimate): by state, and nationally by race/ethnicity."""
    by_state = collections.Counter()
    for r in csv.DictReader(open(ROOT / "data/census/sc-est2024-agesex-civ.csv", encoding="latin-1")):
        if r["SUMLEV"] == "040" and r["SEX"] == "0" and int(r["AGE"]) <= AGE_MAX:
            by_state[r["NAME"]] += int(r["POPEST2024_CIV"])
    race = collections.Counter()
    for r in csv.DictReader(open(ROOT / "data/census/sc-est2024-alldata6.csv", encoding="latin-1")):
        if r["SEX"] != "0" or int(r["AGE"]) > AGE_MAX:
            continue
        pop = int(r["POPESTIMATE2024"])
        if r["ORIGIN"] == "2":
            race["Hispanic"] += pop
        elif r["ORIGIN"] == "1":
            race[{"1": "White", "2": "Black", "3": "American Indian / Alaska Native", "4": "Asian",
                  "5": "Native Hawaiian / Pacific Islander", "6": "Two or more races"}[r["RACE"]]] += pop
    return by_state, race


# --------------------------------------------------------------------------- main

def main():
    P = {p["person_key"]: p for p in load_csv("output/persons.csv")}
    C = {c["person_key"]: c for c in load_csv("output/circumstances.csv")}
    pop_state, pop_race = census()
    I = {"collected": COLLECTED.isoformat(), "recent_from": RECENT_FROM}

    rows = []
    for k, p in P.items():
        a, d = age_of(p), date_of(p)
        rows.append(dict(key=k, p=p, c=C[k], age=a, band=band(a), date=d, sex=p["sex"].lower(),
                         type=C[k]["how_missing"], text=p["circumstances"]))
    recent = [r for r in rows if r["date"] and r["date"].year >= RECENT_FROM]
    I["n_all"], I["n_recent"] = len(rows), len(recent)

    # 1. Age and sex -----------------------------------------------------------
    ages = collections.Counter((r["age"], r["sex"]) for r in rows if r["age"] is not None)
    I["age_sex"] = [[a, ages[(a, "female")], ages[(a, "male")]] for a in range(0, AGE_MAX + 1)]
    teen = [r for r in rows if r["band"] == "12-17"]
    I["peak_age"] = max(range(AGE_MAX + 1), key=lambda a: ages[(a, "female")] + ages[(a, "male")])
    I["share_15_17"] = sum(ages[(a, s)] for a in (15, 16, 17) for s in ("female", "male")) / len(rows)
    I["female_share"] = {b: sum(r["sex"] == "female" for r in rows if r["band"] == b) /
                         max(1, sum(r["band"] == b for r in rows)) for b in ("0-11", "12-17", "18-25")}
    I["female_share_by_type"] = {}
    for t in ("Runaway / left voluntarily", "Outdoors / water (lost, drowning, accident)",
              "Possible foul play / homicide", "Family abduction", "Non-family abduction"):
        sub = [r for r in rows if r["type"] == t and r["sex"] in ("female", "male")]
        I["female_share_by_type"][t] = [sum(r["sex"] == "female" for r in sub), len(sub)]

    # 2. Race vs population (recent cases) -----------------------------------
    rc = collections.Counter()
    for r in recent:
        rc[race_of(r["key"]) or "Unknown"] += 1
    known = sum(v for k, v in rc.items() if k != "Unknown")
    pop_total = sum(pop_race.values())
    I["race"] = [[k, rc[k], rc[k] / known, pop_race[k] / pop_total, (rc[k] / known) / (pop_race[k] / pop_total)]
                 for k in RACE_ORDER]
    I["race_unknown"], I["race_known"] = rc["Unknown"], known
    I["race_by_source"] = {}
    for src in ("namus", "ncmec"):
        sc_ = collections.Counter(race_of(r["key"]) for r in recent if r["key"].startswith(src))
        kn = sum(v for k, v in sc_.items() if k)
        I["race_by_source"][src] = {k: sc_[k] / kn for k in RACE_ORDER} | {"n": kn}
    mig = re.compile(r"\b(?:border|crossing|crossed|migrant|immigra\w*|undocumented|smuggl\w*|coyote|"
                     r"Rio Grande|unaccompanied|refugee|ORR)\b", re.I)
    hisp = [r for r in recent if race_of(r["key"]) == "Hispanic"]
    I["hispanic_migration_related"] = [sum(bool(mig.search(r["text"])) for r in hisp), len(hisp)]
    I["pop_0_25"] = pop_total

    # 3. Per-capita by state (recent) ----------------------------------------
    sc = collections.Counter()
    for r in recent:
        s = r["p"]["last_contact_state"].strip()
        s = STATE_ABBR.get(s.upper(), s) if len(s) <= 2 else s
        sc[s] += 1
    rates = [[s, sc[s], pop_state[s], 100000 * sc[s] / pop_state[s]] for s in pop_state if pop_state[s]]
    rates.sort(key=lambda x: -x[3])
    I["state_rates"] = rates
    I["national_rate"] = 100000 * sum(sc[s] for s in pop_state) / sum(pop_state.values())
    I["state_unmatched"] = {s: v for s, v in sc.items() if s not in pop_state}
    split = collections.defaultdict(collections.Counter)
    for r in recent:
        s = r["p"]["last_contact_state"].strip()
        split[STATE_ABBR.get(s.upper(), s) if len(s) <= 2 else s][r["key"].split(":")[0]] += 1
    I["state_source_split"] = {s: dict(split[s]) for s, *_ in rates}

    # 4. Seasonality. Exact dates only (Jan 1 is often a placeholder), and cases from the last 12 months
    #    are left out: open recent cases pile up in the current month and would fake a peak.
    def months(sub):
        m = collections.Counter(r["date"].month for r in sub if r["date"] and (r["date"].month, r["date"].day) != (1, 1)
                                and (COLLECTED - r["date"]).days > 365)
        tot = sum(m.values())
        return [m[i] / tot if tot else 0 for i in range(1, 13)], tot
    I["jan1_share"] = sum(1 for r in rows if r["date"] and (r["date"].month, r["date"].day) == (1, 1)) / len(rows)
    I["season"] = {}
    for label, sub in (("All cases", rows),
                       ("Lost, drowned or accident outdoors", [r for r in rows if r["type"].startswith("Outdoors")])):
        shares, tot = months(sub)
        I["season"][label] = {"shares": shares, "n": tot}

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
        I["years_open_by_type"][t] = [statistics.median(y), len(y)]
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
            b = json.load(open(ROOT / "data/raw/ncmec" / f"{r['key'].split(':', 1)[1]}.json", encoding="utf-8"))["childBean"]
            sib += bool(b.get("otherChildList"))
    I["ncmec_with_companions"] = [sib, sum(r["key"].startswith("ncmec") for r in rows)]

    (ROOT / "report").mkdir(exist_ok=True)
    (ROOT / "report/insights.json").write_text(json.dumps(I, indent=1, default=str), "utf-8")
    return I


if __name__ == "__main__":
    I = main()
    s = json.dumps({k: v for k, v in I.items() if k not in ("age_sex", "state_rates")}, indent=0, default=str)
    print(s[:6000])
    print("top states:", [(x[0], x[1], round(x[3], 1)) for x in I["state_rates"][:8]])
    print("bottom states:", [(x[0], x[1], round(x[3], 1)) for x in I["state_rates"][-6:]])
