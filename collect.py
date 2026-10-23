"""Collect public missing-person case data for children and young adults (US).

Sources (both public, no login):
  * NamUs  - National Missing and Unidentified Persons System (DOJ/NIJ), www.namus.gov
  * NCMEC  - National Center for Missing & Exploited Children poster search, missingkids.org

Each run:
  1. Lists every open case (NamUs: age at disappearance <= --max-age; NCMEC: all child posters).
  2. Downloads each case's detail record (cached in data/raw/, re-fetched only when changed).
  3. Diffs against earlier runs (data/state.json). Cases that drop off a public listing are
     almost always resolved (found alive or deceased), so a delisting is recorded as a
     "found" event with the date window in which it happened.
  4. Writes output/persons.csv, output/events.csv and output/timeline.json.

Usage:
  python collect.py                 # both sources
  python collect.py --source namus  # one source
  python collect.py --max-age 21 --workers 4
  python collect.py --offline       # rebuild outputs from cached raw data, no network
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
STATE_FILE = ROOT / "data" / "state.json"
OUT = ROOT / "output"

NAMUS = "https://www.namus.gov"
NCMEC_API = "https://api.missingkids.org/missingkids/servlet/JSONDataServlet"
NCMEC_SEARCH = dict(action="publicSearch", searchLang="en_US", LanguageId="en_US",
                    subjToSearch="child", missState="All", missCountry="US")
UA = "Mozilla/5.0 (public missing-persons research collector)"

TODAY = dt.date.today().isoformat()


# --------------------------------------------------------------------------- http

_local = threading.local()


def session() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = UA
    return _local.s


def fetch(method: str, url: str, *, tries: int = 5, **kw) -> requests.Response:
    for attempt in range(tries):
        try:
            r = session().request(method, url, timeout=60, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code}")
            return r
        except (requests.RequestException, ValueError) as e:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt + 1)
    raise RuntimeError("unreachable")


def fetch_json(method: str, url: str, **kw):
    for attempt in range(4):
        r = fetch(method, url, **kw)
        try:
            return r.json()
        except ValueError:  # NCMEC occasionally returns an empty body; retry
            time.sleep(2 ** attempt + 1)
    raise RuntimeError(f"non-JSON response from {url}")


def parallel(fn, items, workers: int, label: str):
    done, errors = 0, []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fn, it): it for it in items}
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:  # keep going; report at the end
                errors.append((futs[f], repr(e)))
            if done % 250 == 0 or done == len(items):
                print(f"  {label}: {done}/{len(items)}", flush=True)
    for it, err in errors[:20]:
        print(f"  ! {label} {it}: {err}", file=sys.stderr)
    if errors:
        print(f"  ! {len(errors)} {label} fetches failed (re-run to retry)", file=sys.stderr)


# --------------------------------------------------------------------------- NamUs

def namus_list(max_age: int) -> dict[str, str]:
    """{case_id: modifiedDateTime} for open cases with age-at-missing <= max_age."""
    results, count, page = [], None, 5000  # API caps a page at 10000
    while count is None or len(results) < count:
        body = {
            "take": page, "skip": len(results),
            "projections": ["namus2Number", "modifiedDateTime"],
            "predicates": [{"field": "computedMissingMinAge", "operator": "LessThanOrEqualTo",
                            "value": max_age}],
            "orderSpecifications": [{"field": "namus2Number", "direction": "Ascending"}],
        }
        data = fetch_json("POST", f"{NAMUS}/api/CaseSets/NamUs/MissingPersons/Search", json=body)
        if "results" not in data:
            raise RuntimeError(f"NamUs search failed: {data}")
        count = data["count"]
        if not data["results"]:
            break
        results += data["results"]
    out = {str(r["namus2Number"]): r.get("modifiedDateTime") or "" for r in results}
    if len(out) != count:
        raise RuntimeError(f"NamUs returned {len(out)} of {count} cases")
    return out


def namus_fetch(case_id: str, modified: str, refresh: bool):
    path = RAW / "namus" / f"{case_id}.json"
    if path.exists() and not refresh:
        if json.loads(path.read_text("utf-8")).get("modifiedDateTime") == modified:
            return
    data = fetch_json("GET", f"{NAMUS}/api/CaseSets/NamUs/MissingPersons/Cases/{case_id}")
    path.write_text(json.dumps(data, indent=1), "utf-8")


def namus_check_delisted(case_id: str) -> dict:
    """Ask NamUs about a case that dropped off the listing. Returns what it says."""
    r = fetch("GET", f"{NAMUS}/api/CaseSets/NamUs/MissingPersons/Cases/{case_id}")
    info = {"http_status": r.status_code}
    if r.ok:
        try:
            d = r.json()
            info.update(caseIsResolved=d.get("caseIsResolved"),
                        publication=(d.get("publicationStatus") or {}).get("name"))
            (RAW / "namus" / f"{case_id}.delisted.json").write_text(json.dumps(d, indent=1), "utf-8")
        except ValueError:
            pass
    return info


# --------------------------------------------------------------------------- NCMEC

def ncmec_list() -> dict[str, dict]:
    """{'PREFIX-CASE-SEQ': search row} for every open child poster."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    _local.s = s  # pagination is tied to the session cookie
    first = fetch_json("GET", NCMEC_API, params={**NCMEC_SEARCH, "search": "new"})
    rows = list(first["persons"])
    for page in range(2, first["totalPages"] + 1):
        d = fetch_json("GET", NCMEC_API, params={**NCMEC_SEARCH, "goToPage": page})
        rows += d["persons"]
        if page % 25 == 0:
            print(f"  ncmec list: page {page}/{first['totalPages']}", flush=True)
        time.sleep(0.2)
    del _local.s
    out = {f"{p['orgPrefix']}-{p['caseNumber']}-{p.get('seqNumber', 1)}": p for p in rows}
    if len(out) < first["totalRecords"] * 0.98:
        raise RuntimeError(f"NCMEC listing incomplete: {len(out)} of {first['totalRecords']}")
    return out


def ncmec_fetch(key: str, row: dict, refresh: bool):
    path = RAW / "ncmec" / f"{key}.json"
    if path.exists() and not refresh:
        return
    d = fetch_json("GET", NCMEC_API, params=dict(
        action="childDetail", orgPrefix=row["orgPrefix"], caseNum=row["caseNumber"],
        seqNum=row.get("seqNumber", 1), caseLang="en_US", searchLang="en_US", LanguageId="en_US"))
    if d.get("status") != "success" or "childBean" not in d:
        raise RuntimeError(f"bad detail for {key}: {str(d)[:120]}")
    path.write_text(json.dumps(d, indent=1), "utf-8")


# --------------------------------------------------------------------------- state / found

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text("utf-8"))
    return {"runs": [], "namus": {}, "ncmec": {}}


def update_state(state: dict, source: str, current: set[str], namus_max_age: int | None,
                 workers: int) -> dict:
    """Update listing history; return this run's counts for the run log."""
    cases = state[source]
    stats = {"listed": len(current), "new": 0, "relisted": 0, "no_longer_listed": 0, "delisted": 0}
    for cid in current:
        if cid not in cases:
            stats["new"] += 1
        c = cases.setdefault(cid, {"first_listed": TODAY})
        c["last_listed"] = TODAY
        if c.get("status") == "delisted":  # came back (e.g. re-opened / re-published)
            c.setdefault("history", []).append({"relisted": TODAY, "was": c.pop("delisted")})
            stats["relisted"] += 1
        c["status"] = "listed"

    gone = [cid for cid, c in cases.items() if c.get("status") == "listed" and cid not in current]
    stats["no_longer_listed"] = len(gone)
    if not gone:
        return stats
    print(f"  {source}: {len(gone)} previously listed cases are no longer listed")

    def mark(cid):
        c = cases[cid]
        info = {"window_start": c["last_listed"], "window_end": TODAY}
        if source == "namus":
            info.update(namus_check_delisted(cid))
            # Still published & unresolved -> it only fell outside the age filter; not delisted.
            if info.get("publication") == "Published" and info.get("caseIsResolved") is False:
                return
        c["status"] = "delisted"
        c["delisted"] = info

    parallel(mark, gone, workers, f"{source} delisting check")
    stats["delisted"] = sum(1 for cid in gone if cases[cid].get("status") == "delisted")
    return stats


# --------------------------------------------------------------------------- narrative mining

MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
         r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
MONTH_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_PATTERNS = [  # (regex, precision)
    (re.compile(rf"\b({MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d\d)\b", re.I), "day"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/((?:19|20)?\d\d)\b"), "day_numeric"),
    (re.compile(rf"\b({MONTH})\s+(?:of\s+)?((?:19|20)\d\d)\b", re.I), "month"),
    (re.compile(rf"\b(?:on|by|around|about)\s+({MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!,?\s*\d)",
                re.I), "day_no_year"),
    (re.compile(r"\b(?:in|since|during|until|of|by)\s+((?:19|20)\d\d)\b"
                r"(?!\s*(?:block|[NSEW]\.?\s|north|south|east|west|hours|hrs))", re.I),
     "year"),  # not "1906 block" / "1900 hours"
]
DOB_RE = re.compile(r"\b(?:DOB|D\.O\.B\.|born|birth(?:day|date)?|date of birth)\W{0,3}(?:of|on|is)?\W{0,3}"
                    r"(?:\d{1,2}\s*)?$", re.I)

STATES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|"
          "Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|"
          "Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|"
          "New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|"
          "Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|"
          "Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia|"
          "Puerto Rico|Mexico|Canada")
PLACE_RE = re.compile(rf"\b(?:in|to|near|at|from|of)\s+((?:[A-Z][\w.'-]*\s?){{1,4}}),\s*({STATES}|[A-Z]{{2}})\b")

# The person themself found / identified (vs. their car, phone, belongings - see EVIDENCE_RE).
PERSON_FOUND_RE = re.compile(
    r"\b(?P<subj>[Hh]e|[Ss]he|[Tt]hey|[Tt]he (?:child|teen|juvenile|girl|boy)|[A-Z][a-z]+) (?:"
    r"(?:was|were|has been|have been) (?:later |eventually |safely )?"
    r"(?:found|located|recovered|identified)(?! abandoned| missing)\b|"
    r"(?:later |eventually |safely )?returned home\b|turned (?:herself|himself|themselves) in\b)|"
    r"\b(?:remains|body) (?:was|were|has been|have been|of [\w ]+? (?:was|were)) "
    r"(?:found|located|recovered|discovered|identified)\b")
NOT_RETURNED_RE = re.compile(r"\b(?:never|not|no longer|failed to|\w+n\W{0,3}t)\b[\w ]{0,15}\breturn", re.I)
LAST_SEEN_RE = re.compile(r"\b(?:last (?:seen|known|contact|heard)|went missing|disappeared|missing since|"
                          r"has been missing|left (?:his|her|their|the) (?:home|residence|house))\b", re.I)
EVIDENCE_RE = re.compile(
    r"\b(?:vehicle|car|truck|van|suv|motorcycle|bike|bicycle|phone|cell ?phone|purse|wallet|"
    r"backpack|bag|belongings|clothing|shoes?|keys|card|receipts?|items?|jacket|note)\b.{0,60}?"
    r"\b(?:was|were|has been|have been|later)\b.{0,20}?\b(?:found|located|recovered|discovered|"
    r"used|abandoned|purchased|pinged)\b", re.I)
PRIOR_RE = re.compile(r"\b(?:previously|history of|has run away|had run away|ran away (?:before|"
                      r"several times|multiple times|in the past)|prior (?:runaway|incident|"
                      r"disappearance)s?|run away before|on (?:a|one) previous occasion|"
                      r"had been reported missing)\b", re.I)
AFTER_RE = re.compile(r"\b(?:sighting|sighted|possibly (?:in|traveling|living)|may (?:be|have) "
                      r"(?:in(?! need)|traveling|travel(?:l)?ed|living|with|gone)|believed to (?:be|have)|"
                      r"reportedly (?:seen|spotted)|unconfirmed|may still be(?! in need)|later seen|"
                      r"was (?:also )?seen (?:again|later)|last (?:heard from|spoke)|"
                      r"phone (?:pinged|was last used)|used (?:her|his|their) (?:bank|card))\b", re.I)


def parse_date(m: re.Match, precision: str, ref_year: int | None):
    g = m.groups()
    try:
        if precision == "day":
            return dt.date(int(g[2]), MONTH_NUM[g[0][:3].lower()], int(g[1])), "day"
        if precision == "day_numeric":
            y = int(g[2]) + (0 if len(g[2]) == 4 else (1900 if int(g[2]) > 30 else 2000))
            return dt.date(y, int(g[0]), int(g[1])), "day"
        if precision == "month":
            return dt.date(int(g[1]), MONTH_NUM[g[0][:3].lower()], 1), "month"
        if precision == "day_no_year" and ref_year:
            return dt.date(ref_year, MONTH_NUM[g[0][:3].lower()], int(g[1])), "day_year_assumed"
        if precision == "year":
            return dt.date(int(g[0]), 1, 1), "year"
    except (ValueError, KeyError):
        pass
    return None, None


def compare(d: dt.date, prec: str, ref: dt.date) -> int:
    """-1 before, 0 same (at the coarser precision), 1 after."""
    if prec == "year":
        a, b = d.year, ref.year
    elif prec == "month":
        a, b = (d.year, d.month), (ref.year, ref.month)
    else:
        a, b = d, ref
    return (a > b) - (a < b)


def person_found(sent: str, names: set[str]) -> bool:
    """True if the sentence says the missing person (not their car, etc.) was found."""
    if NOT_RETURNED_RE.search(sent):
        return False
    for m in PERSON_FOUND_RE.finditer(sent):
        subj = (m.group("subj") or "").lower()
        if "returned home" in m.group(0) and subj not in names:
            continue  # "she returned home" usually means a parent coming home
        if not subj or subj in ("he", "she", "they") or subj.startswith("the ") or subj in names:
            return True
    return False


def mine_narrative(text: str, last_contact: dt.date | None, field: str,
                   names: tuple[str, ...] = ()) -> list[dict]:
    """Turn free-text circumstances into dated / phase-tagged events."""
    if not text:
        return []
    events = []
    names_lc = {n.lower() for n in names if n}
    text = re.sub(r"\s+", " ", text).strip()
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", text):
        found_hint = person_found(sent, names_lc)
        evidence = bool(EVIDENCE_RE.search(sent))
        if found_hint and evidence and not re.search(
                r"\b(?:remains|body|he|she|they)\b (?:was|were|has|have)", sent, re.I):
            found_hint = False  # "Her Jeep was found ..." is evidence, not the person
        prior = bool(PRIOR_RE.search(sent))
        after = bool(AFTER_RE.search(sent))
        if found_hint:
            etype = "remains_found" if re.search(r"\b(?:remains|body)\b", sent, re.I) else "person_found"
        elif evidence:
            etype = "evidence"
        elif prior:
            etype = "prior_history"
        elif after:
            etype = "sighting_or_lead"
        else:
            etype = "narrative"
        dates, spans = [], []
        for rx, prec in DATE_PATTERNS:
            for m in rx.finditer(sent):
                if DOB_RE.search(sent[max(0, m.start() - 30):m.start()]):
                    continue  # someone's date of birth, not an event
                if any(s <= m.start() < e for s, e in spans):
                    continue  # already covered by a more precise pattern
                d, p = parse_date(m, prec, last_contact.year if last_contact else None)
                if d:
                    dates.append((d, p))
                    spans.append(m.span())
        place = PLACE_RE.search(sent)
        loc = {"city": place.group(1).strip(), "state": place.group(2)} if place else {}

        base = dict(event_type=etype, description=sent, **loc, derived_from=f"narrative:{field}")
        if dates:
            d, p = min(dates)
            if found_hint:
                phase = "found"
            elif last_contact is None:
                phase = "unknown"
            else:
                c = compare(d, p, last_contact)
                phase = {-1: "before", 0: "last_contact", 1: "between"}[c]
                if LAST_SEEN_RE.search(sent) and abs((d - last_contact).days) <= 31:
                    phase = "last_contact"  # text restates last contact with a slightly different date
            events.append(dict(base, phase=phase, date=d.isoformat(), date_precision=p,
                               confidence="low" if phase == "found" else "medium"))
        elif found_hint:
            events.append(dict(base, phase="found", confidence="low"))
        elif prior:
            events.append(dict(base, phase="before", confidence="medium"))
        elif evidence or after:
            events.append(dict(base, phase="between", confidence="low"))
    return events


# --------------------------------------------------------------------------- normalize

def _d(s: str | None) -> dt.date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y %I:%M:%S %p"):
        try:
            return dt.datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    return None


def _name(o) -> str:
    return (o or {}).get("name", "") if isinstance(o, dict) else ""


def normalize_namus(d: dict, st: dict) -> tuple[dict, list[dict]]:
    sid, sdesc = d.get("subjectIdentification") or {}, d.get("subjectDescription") or {}
    sight = d.get("sighting") or {}
    addr = sight.get("address") or {}
    geo = ((sight.get("publicGeolocation") or {}).get("coordinates")) or {}
    agency = (d.get("investigatingAgencies") or [{}])[0]
    last = _d(sight.get("date"))
    circ = (d.get("circumstances") or {}).get("circumstancesOfDisappearance", "")
    cid = str(d["id"])
    person = dict(
        person_key=f"namus:{cid}", sources="namus", case_type="", namus_id=d.get("idFormatted", ""),
        ncmec_id="", ncic="",
        first_name=sid.get("firstName", ""), middle_name=sid.get("middleName", ""),
        last_name=sid.get("lastName", ""), nicknames=sid.get("nicknames", ""),
        sex=_name(sdesc.get("sex")), race=_name(sdesc.get("primaryEthnicity")), dob=sid.get("dateOfBirth", ""),
        age_missing_min=sid.get("computedMissingMinAge", ""),
        age_missing_max=sid.get("computedMissingMaxAge", ""),
        last_contact_date=sight.get("date", ""), last_contact_city=addr.get("city", ""),
        last_contact_county=_name(addr.get("county")), last_contact_state=_name(addr.get("state")),
        last_contact_zip=addr.get("zipCode", ""),
        last_contact_lat=geo.get("lat", ""), last_contact_lon=geo.get("lon", ""),
        possible_location="", circumstances=circ,
        status="resolved" if d.get("caseIsResolved") else st.get("status", "listed"),
        first_listed=st.get("first_listed", ""), last_listed=st.get("last_listed", ""),
        delisted_window=_window(st), agency=agency.get("name", ""),
        agency_case_number=agency.get("caseNumber", ""),
        record_modified=d.get("modifiedDateTime", ""),
        url=f"https://www.namus.gov/MissingPersons/Case#/{cid}",
    )
    events = [dict(phase="last_contact", date=sight.get("date", ""), date_precision="day",
                   city=addr.get("city", ""), state=_name(addr.get("state")),
                   lat=geo.get("lat", ""), lon=geo.get("lon", ""),
                   event_type="last_contact",
                   description="Date and place of last contact (NamUs structured field)",
                   derived_from="structured", confidence="high")]
    names = (sid.get("firstName", ""), sid.get("lastName", ""))
    events += mine_narrative(circ, last, "circumstances", names)
    for note in d.get("notes") or []:
        text = note.get("description") or note.get("text") or note.get("note") or ""
        events += mine_narrative(text, last, "notes", names)
    for v in d.get("vehicles") or []:
        desc = " ".join(str(v.get(k, "")) for k in ("vehicleYear", "vehicleColor", "vehicleMake",
                                                     "vehicleModel", "comment") if v.get(k))
        if desc:
            events.append(dict(phase="last_contact", event_type="vehicle", description=f"Vehicle: {desc}",
                               derived_from="structured:vehicles", confidence="high"))
    events += _delist_events(st)
    return person, events


def normalize_ncmec(d: dict, key: str, st: dict) -> tuple[dict, list[dict]]:
    b = d["childBean"]
    last = _d(b.get("missingDate"))
    ncmec_url = ("https://www.missingkids.org/poster/"
                 f"{b['orgPrefix']}/{b['caseNumber']}/{b.get('seqNumber', 1)}")
    person = dict(
        person_key=f"ncmec:{key}", sources="ncmec", case_type=b.get("caseType", ""),
        namus_id=b.get("namUs", ""), ncmec_id=key,
        ncic=b.get("ncic", ""), first_name=b.get("firstName", ""),
        middle_name=b.get("middleName", ""), last_name=b.get("lastName", ""), nicknames="",
        sex=b.get("sex", ""), race=b.get("race", ""),
        dob=_d(b.get("birthDate")).isoformat() if _d(b.get("birthDate")) else "",
        age_missing_min=b.get("approxAge") or "", age_missing_max="",
        last_contact_date=last.isoformat() if last else "", last_contact_city=b.get("missingCity", ""),
        last_contact_county=b.get("missingCounty", ""), last_contact_state=b.get("missingState", ""),
        last_contact_zip="", last_contact_lat="", last_contact_lon="",
        possible_location=b.get("possibleLocation", ""),
        circumstances=" ".join(x for x in (b.get("circumstance"), b.get("profileNarrative")) if x),
        status=st.get("status", "listed"), first_listed=st.get("first_listed", ""),
        last_listed=st.get("last_listed", ""), delisted_window=_window(st),
        agency=(b.get("altContact") or "").replace("\r\n", " ").strip(), agency_case_number="",
        record_modified="", url=ncmec_url,
    )
    if not person["age_missing_min"] and last and _d(b.get("birthDate")):
        bd = _d(b.get("birthDate"))
        person["age_missing_min"] = last.year - bd.year - ((last.month, last.day) < (bd.month, bd.day))
    events = [dict(phase="last_contact", date=person["last_contact_date"], date_precision="day",
                   city=b.get("missingCity", ""), state=b.get("missingState", ""),
                   event_type="last_contact",
                   description="Missing-from place and date (NCMEC structured field)",
                   derived_from="structured", confidence="high")]
    if b.get("possibleLocation"):
        events.append(dict(phase="between", event_type="possible_location", description=f"Possible location: {b['possibleLocation']}",
                           derived_from="structured:possibleLocation", confidence="medium"))
    for fld in ("circumstance", "profileNarrative"):
        events += mine_narrative(b.get(fld, ""), last, fld, (b.get("firstName", ""), b.get("lastName", "")))
    for c in b.get("otherChildList") or []:
        nm = " ".join(x for x in (c.get("firstName"), c.get("lastName")) if x)
        events.append(dict(phase="last_contact", event_type="companion", description=f"Missing with / companion case: {nm}",
                           derived_from="structured:otherChildList", confidence="high"))
    events += _delist_events(st)
    return person, events


def _window(st: dict) -> str:
    w = st.get("delisted")
    return f"{w['window_start']}..{w['window_end']}" if w else ""


def _delist_events(st: dict) -> list[dict]:
    w = st.get("delisted")
    if not w:
        return []
    extra = " NamUs reports the case as resolved." if w.get("caseIsResolved") else ""
    return [dict(phase="found", event_type="delisted_from_database", date=w["window_end"], date_precision=f"between {w['window_start']} and",
                 description="Case removed from the public listing between collection runs "
                             f"(public databases remove cases once the person is located).{extra}",
                 derived_from="snapshot_diff",
                 confidence="high" if w.get("caseIsResolved") else "medium")]


def age_group(p: dict) -> str:
    """'child' (under 18 for the whole recorded age range), 'adult' (18-25), else 'unknown'."""
    try:
        lo = int(p["age_missing_min"])
    except (TypeError, ValueError):
        return "unknown"
    try:
        hi = int(p["age_missing_max"])
    except (TypeError, ValueError):
        hi = lo
    if hi < 18:
        return "child"
    if lo >= 18:
        return "adult"
    return "unknown"  # age range straddles 18


def build_outputs(state: dict):
    persons: dict[str, dict] = {}
    events: dict[str, list[dict]] = {}

    for f in sorted((RAW / "namus").glob("*.json")):
        if f.stem.endswith(".delisted"):
            continue
        d = json.loads(f.read_text("utf-8"))
        p, ev = normalize_namus(d, state["namus"].get(f.stem, {}))
        for e in ev:
            e["source"] = "namus"
        persons[p["person_key"]], events[p["person_key"]] = p, ev

    namus_index = {p["namus_id"]: k for k, p in persons.items()}
    for f in sorted((RAW / "ncmec").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        if d["childBean"].get("caseType") == "unidentified":
            continue  # unidentified-remains poster, not a missing child
        p, ev = normalize_ncmec(d, f.stem, state["ncmec"].get(f.stem, {}))
        for e in ev:
            e["source"] = "ncmec"
        nid = p["namus_id"].strip().upper()
        if nid and not nid.startswith("MP"):
            nid = f"MP{nid}"
        target = namus_index.get(nid)
        if target:  # same child in both databases: merge onto the NamUs record
            base = persons[target]
            base["sources"] = "namus+ncmec"
            base["ncmec_id"], base["ncic"], base["case_type"] = p["ncmec_id"], p["ncic"], p["case_type"]
            for k in ("dob", "possible_location", "race"):
                base[k] = base[k] or p[k]
            base["circumstances"] = "\n\n".join(x for x in (base["circumstances"],
                                                            f"[NCMEC] {p['circumstances']}") if x.strip())
            base["url"] += f" | {p['url']}"
            if p["status"] == "delisted" or base["status"] == "delisted":
                base["status"] = "delisted"
                base["delisted_window"] = base["delisted_window"] or p["delisted_window"]
            events[target] += ev
        else:
            persons[p["person_key"]], events[p["person_key"]] = p, ev

    # Children and adults are analyzed apart: every child figure uses age_group == "child" only.
    for k in list(persons):
        persons[k] = {"person_key": k, "age_group": age_group(persons[k]),
                      **{f: v for f, v in persons[k].items() if f != "person_key"}}

    OUT.mkdir(exist_ok=True)
    order = {"before": 0, "last_contact": 1, "between": 2, "found": 3, "unknown": 4}
    ev_cols = ["person_key", "age_group", "seq", "phase", "event_type", "date", "date_precision", "city", "state",
               "lat", "lon", "description", "derived_from", "confidence", "source"]
    timeline = []
    with open(OUT / "events.csv", "w", newline="", encoding="utf-8-sig") as fe:
        w = csv.DictWriter(fe, ev_cols, extrasaction="ignore")
        w.writeheader()
        for key, p in persons.items():
            evs = sorted(events[key], key=lambda e: (order[e["phase"]], e.get("date") or "9999"))
            for i, e in enumerate(evs, 1):
                e["person_key"], e["age_group"], e["seq"] = key, p["age_group"], i
                w.writerow(e)
            timeline.append({**p, "events": evs})
            p["n_before"] = sum(e["phase"] == "before" for e in evs)
            p["n_between"] = sum(e["phase"] == "between" for e in evs)
            p["n_found"] = sum(e["phase"] == "found" for e in evs)

    cols = list(next(iter(persons.values())).keys()) if persons else []
    with open(OUT / "persons.csv", "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, cols)
        w.writeheader()
        w.writerows(persons.values())
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1, default=str), "utf-8")

    n_ev = sum(len(v) for v in events.values())
    by_phase = {ph: sum(e["phase"] == ph for v in events.values() for e in v) for ph in order}
    print(f"\nWrote {len(persons)} persons, {n_ev} events -> {OUT}")
    print("  events by phase:", by_phase)
    print("  persons by status:",
          {s: sum(p["status"] == s for p in persons.values()) for s in ("listed", "delisted", "resolved")})


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["namus", "ncmec", "all"], default="all")
    ap.add_argument("--max-age", type=int, default=25, help="NamUs: max age at disappearance (default 25)")
    ap.add_argument("--workers", type=int, default=4, help="parallel detail downloads per source")
    ap.add_argument("--refresh", action="store_true", help="re-download every detail record")
    ap.add_argument("--offline", action="store_true", help="only rebuild outputs from cached data")
    ap.add_argument("--limit", type=int, help="test mode: fetch only N cases per source, skip state update")
    a = ap.parse_args()

    for s in ("namus", "ncmec"):
        (RAW / s).mkdir(parents=True, exist_ok=True)
    state = load_state()

    if not a.offline:
        run = {"date": TODAY, "source": a.source, "max_age": a.max_age}
        if a.source in ("namus", "all"):
            print(f"NamUs: listing open cases, age at disappearance <= {a.max_age} ...")
            ids = namus_list(a.max_age)
            print(f"  {len(ids)} cases")
            if a.limit:
                ids = dict(list(ids.items())[:a.limit])
            parallel(lambda c: namus_fetch(c, ids[c], a.refresh), list(ids), a.workers, "namus details")
            if not a.limit:
                run["namus"] = update_state(state, "namus", set(ids), a.max_age, a.workers)
        if a.source in ("ncmec", "all"):
            print("NCMEC: listing open child posters ...")
            rows = ncmec_list()
            print(f"  {len(rows)} cases")
            if a.limit:
                rows = dict(list(rows.items())[:a.limit])
            parallel(lambda k: ncmec_fetch(k, rows[k], a.refresh), list(rows), a.workers, "ncmec details")
            if not a.limit:
                run["ncmec"] = update_state(state, "ncmec", set(rows), None, a.workers)
        if a.limit:
            build_outputs(state)
            return
        state["runs"].append(run)
        print("  run counts:", {s: run[s] for s in ("namus", "ncmec") if s in run})
        STATE_FILE.write_text(json.dumps(state, indent=1), "utf-8")

    build_outputs(state)


if __name__ == "__main__":
    main()
