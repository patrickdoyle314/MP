"""Shared helpers for the MP pipeline: paths, states, dates, age bands, race coding and cached loaders.

Scripts in subfolders import it after putting the project root on sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""
import collections
import csv
import datetime as dt
import functools
import hashlib
import json
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
CACHE = DATA / "cache"

USPS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
}
STATE_NAME = {code: name for name, code in USPS.items()}

# Race / ethnicity as the Census codes it: Hispanic is any race; other groups are non-Hispanic.
RACE_ORDER = ["Hispanic", "White", "Black", "American Indian / Alaska Native", "Asian",
              "Native Hawaiian / Pacific Islander", "Two or more races"]
NAMUS_RACE = {"White / Caucasian": "White", "Black / African American": "Black",
              "American Indian / Alaska Native": "American Indian / Alaska Native", "Asian": "Asian",
              "Hawaiian / Pacific Islander": "Native Hawaiian / Pacific Islander"}
NCMEC_RACE = {"white": "White", "black": "Black", "hispanic": "Hispanic", "whiteHisp": "Hispanic",
              "blackHisp": "Hispanic", "asian": "Asian", "amInd": "American Indian / Alaska Native",
              "pacific": "Native Hawaiian / Pacific Islander", "biracial": "Two or more races"}
CENSUS_RACE = {"1": "White", "2": "Black", "3": "American Indian / Alaska Native", "4": "Asian",
               "5": "Native Hawaiian / Pacific Islander", "6": "Two or more races"}

MONTH_ABBR = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


# --------------------------------------------------------------------------- states, dates, ages

def state_code(s):
    """USPS code for a state name or code ('Texas', 'TX'), or None."""
    s = (s or "").strip()
    return s.upper() if s.upper() in STATE_NAME else USPS.get(s)


def state_name(s):
    """Full state name for a code; names and anything unknown pass through unchanged."""
    s = (s or "").strip()
    return STATE_NAME.get(s.upper(), s) if len(s) <= 2 else s


def fiscal_year(d):
    """Federal fiscal year: October 1 starts the next year."""
    return d.year + (1 if d.month >= 10 else 0)


def parse_date(s):
    """ISO dates ('2026-10-22...') and NCMEC dates ('Oct 20, 2026 12:00:00 AM'); None if neither."""
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:  # 'Oct 20, 2026 12:00:00 AM'
        mon, day, year = s.split(" ", 3)[:3]
        return dt.date(int(year), MONTH_ABBR[mon], int(day.rstrip(",")))
    except (ValueError, KeyError):
        return None


def age_band(age):
    """'0-11', '12-17', '18-25', or None for a missing or unparseable age."""
    try:
        a = int(age)
    except (TypeError, ValueError):
        return None
    return "0-11" if a < 12 else "12-17" if a < 18 else "18-25"


def namus_race(ethnicities):
    """Race / ethnicity from NamUs's list of ethnicity names, coded as the Census does."""
    names = set(ethnicities) - {"Other", "Uncertain"}
    if "Hispanic / Latino" in names:
        return "Hispanic"
    races = {NAMUS_RACE[n] for n in names if n in NAMUS_RACE}
    return "Two or more races" if len(races) > 1 else (races.pop() if races else "")


def ncmec_race(code):
    return NCMEC_RACE.get(code or "", "")


# --------------------------------------------------------------------------- loaders

@functools.lru_cache(maxsize=None)
def read_csv(rel):
    """Rows of a CSV under the project root, parsed once per process."""
    return list(csv.DictReader(open(ROOT / rel, encoding="utf-8-sig")))


def load_state():
    return json.loads((DATA / "state.json").read_text("utf-8"))


def last_run_date():
    """Date of the latest collection run; cases counted as open are open on this date."""
    return dt.date.fromisoformat(load_state()["runs"][-1]["date"])


def disk_cached(name, sources, build, version=""):
    """build() once per change of the source files (path, size, mtime) or version; result kept in data/cache."""
    key = hashlib.sha1(json.dumps(
        [version] + [[str(p), p.stat().st_size, p.stat().st_mtime_ns] for p in sources]).encode()).hexdigest()
    path = CACHE / f"{name}.pkl"
    if path.exists():
        try:
            saved_key, value = pickle.loads(path.read_bytes())
            if saved_key == key:
                return value
        except Exception:  # corrupt or from an older format: rebuild
            pass
    value = build()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps((key, value), protocol=pickle.HIGHEST_PROTOCOL))
    return value


@functools.lru_cache(maxsize=None)
def census_tables():
    """Census Vintage 2024 estimates: {(state name, age): pop} and {(state name, race, age): pop}."""
    agesex = DATA / "census/sc-est2024-agesex-civ.csv"
    alldata = DATA / "census/sc-est2024-alldata6.csv"

    def build():
        by_state_age, by_state_race_age = collections.Counter(), collections.Counter()
        for r in csv.DictReader(open(agesex, encoding="latin-1")):
            if r["SUMLEV"] == "040" and r["SEX"] == "0":
                by_state_age[(r["NAME"], int(r["AGE"]))] += int(r["POPEST2024_CIV"])
        for r in csv.DictReader(open(alldata, encoding="latin-1")):
            if r["SEX"] != "0" or r["ORIGIN"] not in ("1", "2"):
                continue
            race = "Hispanic" if r["ORIGIN"] == "2" else CENSUS_RACE[r["RACE"]]
            by_state_race_age[(r["NAME"], race, int(r["AGE"]))] += int(r["POPESTIMATE2024"])
        return dict(by_state_age), dict(by_state_race_age)

    return disk_cached("census_tables", [agesex, alldata], build, version="1")


def census(lo, hi):
    """Population aged lo-hi: by state name, nationally by race, and by (state name, race)."""
    by_state_age, by_state_race_age = census_tables()
    by_state, race, state_race = collections.Counter(), collections.Counter(), collections.Counter()
    for (st, age), v in by_state_age.items():
        if lo <= age <= hi:
            by_state[st] += v
    for (st, rc, age), v in by_state_race_age.items():
        if lo <= age <= hi:
            race[rc] += v
            state_race[(st, rc)] += v
    return by_state, race, state_race
