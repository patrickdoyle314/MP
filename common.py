"""Shared helpers for the MP pipeline: paths, states, dates, age bands, race coding and cached loaders.

Scripts in subfolders import it after putting the project root on sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: every script in the project needs the same small facts (state names and codes,
# what counts as a fiscal year, how ages are grouped, how race is coded). Keeping them in ONE place
# means a fix here fixes every report at once, and two reports can never disagree.
#
# Python ideas you will meet here:
#   - module-level constants (UPPER_CASE names) that other files import
#   - dictionaries ({key: value}) and a dictionary comprehension that flips one around
#   - small functions with docstrings, try/except for "this might fail" parsing
#   - decorators (@functools.lru_cache) that remember a function's answer
#   - pickle, a way to save a Python object to disk and load it back later
# ===================================================================================================
import collections
import csv
import datetime as dt
import functools
import hashlib
import json
import pickle
from pathlib import Path

# Path(__file__) is this file's own location. .resolve().parent is the folder it sits in, which is
# the project root. Building every other path from ROOT means the code works no matter which folder
# you run it from.
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
CACHE = DATA / "cache"

# Lookup table: full state name -> two-letter postal code. NamUs writes "Texas", NCMEC writes "TX";
# this table lets the code treat both the same. A dict lookup like USPS["Texas"] is instant, which
# matters when you do it for 12,000 cases.
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
# A dictionary comprehension: build a new dict by looping over an old one. Here we flip USPS around
# so we can also go from "TX" back to "Texas".
STATE_NAME = {code: name for name, code in USPS.items()}

# Race / ethnicity as the Census codes it: Hispanic is any race; other groups are non-Hispanic.
# Race and ethnicity are coded the way the Census Bureau codes them, so our case counts can be
# compared fairly with population counts: anyone Hispanic counts as Hispanic (of any race); every
# other group means non-Hispanic. Each source spells races its own way, so each gets a translation
# table below.
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

# enumerate(..., 1) pairs each month with its number starting at 1: ("Jan", 1), ("Feb", 2), ...
# Used to read NCMEC dates such as "Oct 20, 2026".
MONTH_ABBR = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


# --------------------------------------------------------------------------- states, dates, ages

# --------------------------------------------------------------------------- states, dates, ages
# These helpers "normalize" messy inputs into one standard form. (s or "") turns None into an empty
# string so .strip() never crashes on a missing value.
def state_code(s):
    """USPS code for a state name or code ('Texas', 'TX'), or None."""
    s = (s or "").strip()
    return s.upper() if s.upper() in STATE_NAME else USPS.get(s)


def state_name(s):
    """Full state name for a code; names and anything unknown pass through unchanged."""
    s = (s or "").strip()
    return STATE_NAME.get(s.upper(), s) if len(s) <= 2 else s


# The federal fiscal year runs October to September, and government data (ORR, FBI budgets) is
# reported that way. FY2023 = Oct 1, 2022 to Sep 30, 2023. A True/False inside arithmetic counts as
# 1/0, so d.year + (1 if ... else 0) adds one year for October-December dates.
def fiscal_year(d):
    """Federal fiscal year: October 1 starts the next year."""
    return d.year + (1 if d.month >= 10 else 0)


# Dates arrive in two formats. We try the common one first; if Python raises ValueError ("this is not
# that format"), we catch it and try the other. Returning None (no date) instead of crashing lets one
# bad record never stop a run over thousands.
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


# Age bands used throughout the reports. Children (0-11, 12-17) and young adults (18-25) are always
# analyzed separately, never pooled.
def age_band(age):
    """'0-11', '12-17', '18-25', or None for a missing or unparseable age."""
    try:
        a = int(age)
    except (TypeError, ValueError):
        return None
    return "0-11" if a < 12 else "12-17" if a < 18 else "18-25"


# NamUs can list several ethnicities for one person. set(...) removes duplicates, and
# "set - {...}" removes the uninformative answers. More than one race -> "Two or more races".
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
# --------------------------------------------------------------------------- loaders
# @functools.lru_cache (the line above) remembers the answer for each argument: the first call reads
# the file, later calls with the same file name return the saved rows instantly. csv.DictReader turns
# each row into a dict keyed by the column names, so code can say row["state"] instead of row[7].
def read_csv(rel):
    """Rows of a CSV under the project root, parsed once per process."""
    return list(csv.DictReader(open(ROOT / rel, encoding="utf-8-sig")))


def load_state():
    return json.loads((DATA / "state.json").read_text("utf-8"))


# "Open cases" always means open on the date of the latest weekly collection, read from the run log.
def last_run_date():
    """Date of the latest collection run; cases counted as open are open on this date."""
    return dt.date.fromisoformat(load_state()["runs"][-1]["date"])


# A tiny disk cache. It fingerprints the input files (name, size, last-modified time); if they have
# not changed since last time, it returns the saved answer instead of redoing slow work. `build` is a
# function passed in as an argument: Python treats functions as values you can hand around.
# hashlib.sha1 turns the fingerprint into a short id; pickle saves/loads the Python object itself.
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
# The Census population files are large (12+ MB). Reading them takes over a second, so the parsed
# tables are cached on disk and in memory. The inner `def build():` is a nested function: it is only
# called if the cache is missing or out of date.
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


# Population for any age range, e.g. census(0, 17) for children. It returns three tables at once
# (a tuple), which the caller can unpack: by_state, by_race, by_state_race = census(0, 17).
# collections.Counter is a dict that starts every count at 0, so "+=" just works.
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
