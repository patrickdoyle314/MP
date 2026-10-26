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

Changes are recorded in [`CHANGELOG.md`](CHANGELOG.md).

## Built alongside another project

This project is being built alongside **[UC-Placement](https://github.com/patrickdoyle314/UC-Placement)**,
a separate service-planning project (public since October 25, 2026). The two stay separate: each has its own data, code, README
and changelog. They communicate only through aggregate tables under the shared contract in
[`exchange/EXCHANGE.md`](exchange/EXCHANGE.md); no individual records pass between them.

## Children and adults are kept apart

Every person and event carries an `age_group`:

| `age_group` | rule | count (2026-10-21 data) |
|---|---|---|
| `child` | under 18 for the whole recorded age range | 7,622 |
| `adult` | 18–25 | 4,728 |
| `unknown` | no age, or an age range that straddles 18 | 3 |

**Rule:** every figure about children is computed from `child` records only. Adult records are kept,
labeled and reported separately as context, never pooled into a child figure. `unknown` records are
in neither group.

The Word report follows the same rule: Part 1 is children only, compared with the Census population
aged 0–17; Part 2 is young adults (18–25), compared with the population aged 18–25. `insights.py`,
`report/make_facts.py` and `report/charts.py` compute and draw each group separately, and count only
cases still open on the latest collection date.

## Layout

```
pipeline.py           rebuild everything in one process, with timings
common.py             shared helpers: states, dates, age bands, race coding, cached loaders
collect.py            collect NamUs + NCMEC cases, build timelines (output/)
scheduled_run.py      one weekly run: collect, refresh derived files, log (data/logs/)
circumstances.py      classify how, where and doing what (output/circumstances.csv)
insights.py           insights with Census comparisons (report/insights.json)
report/               Word report builder, charts, summary JSONs
paper/                notes and checks for Adam, Sokolowski & Banks (2009)
MODELING.md           predictive modeling status and ranked candidates
models/               national stock-and-flow model (FBI NCIC), data, results, MODEL_CARD.md
analysis/             pandas + NumPy open-case metrics
sql/                  SQL statements (DuckDB), dummy practice database
results/              aggregate outputs of analysis/ and sql/
tests/                pytest checks
requirements.txt      Python packages: SciPy, libpysal, matplotlib and python-docx, among others
probes/               quick feasibility checks for model candidates
exchange/             aggregate exchange with adjacent projects (see below)
data/, output/        downloaded and generated data (not committed)
```

## Exchange with adjacent projects

This project shares **aggregates only** with adjacent projects through the file contract in
[`exchange/EXCHANGE.md`](exchange/EXCHANGE.md) (v1.0). `exchange/export_exchange.py` writes
`exchange/outbox/` (not committed): counts of open cases by fiscal year and state, with children
(`open_cases_u18`) and adults (`open_cases_18_25`) as separate measures. Counts under 5 are marked
unpublishable. A peer's outbox can be read with `--peer` to count cases in the counties that peer lists.
Local tag rules live in `exchange/tags.local.json`, which is never committed.

```bash
python exchange/export_exchange.py --peer ../<peer-project>/exchange/outbox
```

## Run

```bash
pip install -r requirements.txt    # collection, analysis (SciPy), spatial (libpysal), reporting (matplotlib, python-docx)
python collect.py                  # full run, ~15–30 min the first time
python collect.py --offline        # rebuild outputs from cached raw data
python collect.py --max-age 21     # change the NamUs age cut-off
```

Re-runs are incremental. NamUs records are re-downloaded only when their `modifiedDateTime`
changes. NCMEC records are downloaded once; use `--refresh` to re-download everything.

## Scheduled runs

A Windows scheduled task, **"MP weekly collection"**, runs `scheduled_run.py` every **Sunday at
10:00 AM**. If the computer is off or asleep then, it runs as soon as it is back on and online. Each run:

1. collects a new snapshot (`collect.py`); cases that dropped off since the last run become `found` events
2. refreshes `output/circumstances.csv` and the exchange outbox
3. writes a full log to `data/logs/<date>_<time>.log` and one summary line to `data/logs/runs.csv`
   (cases listed, new and delisted per source)

`data/state.json` keeps each run's counts under `runs`, the history the survival model needs.

```powershell
Start-ScheduledTask -TaskName "MP weekly collection"     # run now
Get-ScheduledTaskInfo -TaskName "MP weekly collection"   # last and next run
Disable-ScheduledTask -TaskName "MP weekly collection"   # pause
Set-ScheduledTask -TaskName "MP weekly collection" -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At 7pm)  # change time
Unregister-ScheduledTask -TaskName "MP weekly collection"  # remove
```

The task runs as the signed-in user (no stored password) and only while that user is signed in.

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

The Word report (`Missing Children and Young Adults - Circumstances Report.docx`) and every other output
are generated from the data. One command rebuilds everything, in one process, in about 15 seconds:

```bash
python pipeline.py                     # rebuild all outputs, report and dashboard data
python pipeline.py --collect           # collect new data first
python pipeline.py --from insights     # start at a step; --only charts report runs just those
```

The steps, in order (each is also a script you can run on its own): `collect.py --offline` (rebuild from
cached raw data), `circumstances.py`, `report/make_facts.py`, `insights.py`, `models/stock_flow_ncic.py`,
`report/charts.py`, `report/build_report.py`, `report/dashboard_data.py`, `exchange/export_exchange.py`,
`analysis/open_case_metrics.py`.

**Speed.** `collect.py` keeps each raw record's parsed form in `data/cache/normalized.pkl`, re-parsing only
files that changed (editing `collect.py` clears it); Census tables are cached in `data/cache/` too. Shared
helpers (states, dates, age bands, race coding, cached loaders) live in `common.py`.

The report is titled *Missing Children in the United States*: children first, young adults in their own
part. `insights.py` also reads two Census Bureau population-estimate files in `data/census/`,
downloaded from https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/asrh/.
Charts use `matplotlib` and the report uses `python-docx` (both in `requirements.txt`).

## Analysis, SQL and tests

| Path | What it is |
|---|---|
| `analysis/open_case_metrics.py` | pandas + NumPy: how long open cases have been open and the resolution rate that implies, cases found so far, and FBI juvenile flows; children and young adults separately. Writes `results/` (counts under 5 shown as "<5") |
| `sql/ncic_flows.sql` | SQL with a CTE and window functions (`LAG`, moving `AVG`): juvenile records closed per year and average days open, from the FBI figures |
| `sql/practice/` | A dummy database (synthetic data, no real cases) and `caseload_by_region.sql`: four joins with aggregate functions (`COUNT`, `AVG`, `MEDIAN`, `SUM(CASE …)`, `HAVING`) |
| `sql/run_sql.py` | Runs a SQL file with DuckDB and saves the result in `results/` |
| `models/MODEL_CARD.md` | Model card for the national stock-and-flow model |
| `tests/` | pytest: each SQL statement must match the same calculation in pandas |

```bash
python analysis/open_case_metrics.py
python sql/run_sql.py sql/ncic_flows.sql
python sql/practice/build_practice_db.py
python sql/run_sql.py sql/practice/caseload_by_region.sql --db sql/practice/practice.duckdb
python -m pytest
```

## National model (`models/`)

`models/stock_flow_ncic.py` fits yearly FBI NCIC juvenile figures (entries and records active on
December 31, 2015–2025; 2021 not online) with a fast group and a slow group, the linear compartment
form of the predator-prey idea, and backtests it one year ahead. Figures and sources are in
`models/ncic_juvenile_by_year.csv`; results in `models/stock_flow_results.json`. See `MODELING.md`.

## Responsible use

All data is published by NamUs and NCMEC to help find these people. Many subjects are
minors. Keep this dataset for research and case-awareness, don't republish it outside
those purposes, and send tips to the listed agency or NCMEC (1-800-THE-LOST), not to
families directly.
