# Missing children & young adults (US): public case data

`collect.py` collects every open public missing-person case for people aged 25 or younger
at disappearance from two official public databases. It then turns each case into a
timeline: **before** → **last contact** → **between** → **found**.

| Source | What it covers | Access |
|---|---|---|
| [NamUs](https://www.namus.gov/MissingPersons/Search) (US DOJ / NIJ) | All ages; filtered to age at disappearance ≤ 25 (`--max-age`) | Public JSON API used by the NamUs website |
| [NCMEC](https://www.missingkids.org/gethelpnow/search) (missingkids.org) | Children (mostly under 18, some 18–20) | Public JSON API used by the poster search |

When a child appears in both, NCMEC records the NamUs number. The two records are then
merged into a single person (`sources = namus+ncmec`).

## Run

```bash
pip install requests
python collect.py                  # full run, ~15–30 min the first time
python collect.py --offline        # rebuild outputs from cached raw data
python collect.py --max-age 21     # change the NamUs age cut-off
```

Re-runs are incremental. NamUs records are re-downloaded only when their `modifiedDateTime`
changes. NCMEC records are downloaded once; use `--refresh` to re-download everything.

## Outputs (`output/`)

- **persons.csv**: one row per person. Name, sex, race, age at disappearance, last-contact
  date/city/county/state/lat/lon, NCMEC "possible location", full circumstances text,
  agency and case number, status, listing dates, links, and counts of before/between/found events.
- **events.csv**: one row per timeline point, ordered per person by phase, then date.
- **timeline.json**: the same data nested by person, for programmatic use.

### Event columns

| column | meaning |
|---|---|
| `phase` | `before` (prior to disappearance), `last_contact`, `between` (after last contact, before resolution), `found` |
| `event_type` | `last_contact`, `vehicle`, `companion`, `possible_location`, `prior_history`, `sighting_or_lead`, `evidence` (car/phone/items found or used), `person_found`, `remains_found`, `delisted_from_database`, `narrative` |
| `date`, `date_precision` | ISO date. Precision is `day`, `month`, `year` or `day_year_assumed` |
| `derived_from` | `structured` (database field), `narrative:<field>` (mined from case text), `snapshot_diff` |
| `confidence` | `high` = database field, `medium`/`low` = text extraction; check against `description` |

## Where each data point comes from, and the limits

- **Last location / last time**: structured fields in both databases. Reliable.
- **Before / between**: the databases have no structured history. These are mined from
  the free-text circumstances: sentences with dates are placed before or after the
  last-contact date, plus keyword cues ("history of running away", "vehicle was found
  abandoned", "may be traveling to…"). Many cases have only one line of text, so many
  people have no before/between events at all. Text extraction makes mistakes; the
  `description` column always holds the original sentence.
- **Found events mined from text on cases that are still open** are not resolutions. They
  are usually partial remains (the case stays open until identification is complete),
  remains or a body found in a related incident, or an earlier episode in which the person
  was located and later went missing again. Treat `found` events whose `derived_from` starts with `narrative`
  as leads; only `snapshot_diff` events mean the case was closed.
- **Found (when/where)**: both databases **remove cases once the person is located**, and
  neither publishes the outcome. The collector keeps `data/state.json`. When a case drops
  off between two runs, it records a `found / delisted_from_database` event whose date is
  the window between the two runs. NamUs is then asked about the case directly to confirm
  it is resolved and not just outside the age filter. **The first run cannot detect
  any found cases.** Schedule regular runs (e.g. daily or weekly); the shorter the
  interval, the tighter the found-date window. The *place* where someone was found is
  almost never published.

## Rebuilding the report

The Word report (`Missing Children and Young Adults - Circumstances Report.docx`) is generated
from the data. After a new collection, run these in order:

```bash
python collect.py
python circumstances.py output/persons.csv
python report/make_facts.py
python insights.py
python report/charts.py
python report/build_report.py
```

`insights.py` also reads two Census Bureau population-estimate files in `data/census/`,
downloaded from https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/asrh/.
The report builder needs `python-docx` and the charts need `matplotlib`.

## Responsible use

All data is published by NamUs and NCMEC to help find these people. Many subjects are
minors. Keep this dataset for research and case-awareness, don't republish it outside
those purposes, and send tips to the listed agency or NCMEC (1-800-THE-LOST), not to
families directly.
