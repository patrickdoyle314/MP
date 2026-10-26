# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
dates are when the change was made.

## [Unreleased]

Nothing yet.

## [0.9.0] - 2026-10-26

### Added
- `pipeline.py`: rebuilds every output in one process with per-step timings (`--collect`, `--from`, `--only`).
- `common.py`: shared helpers (state names and codes, fiscal years, dates, age bands, race coding, cached CSV
  and Census loaders, a disk cache) replacing copies in `insights.py`, `report/make_facts.py` and
  `exchange/export_exchange.py`.
- `race_ethnicity` and `with_other_children` columns in `output/persons.csv`, so later steps no longer
  re-read 6,800 raw case files.

### Changed
- `collect.py` caches each raw record's parsed form (`data/cache/normalized.pkl`, re-parsed only when the
  file changes; editing the script clears it), parses dates without `strptime`, and writes `timeline.json`
  compactly (24.6 → 20.7 MB, same content).
- `circumstances.py` compiles its patterns once and stops at the first matching cause.
- `models/stock_flow_ncic.py` warm-starts each backtest year from the previous year's fit (earlier data only)
  with 3 extra random starts.

### Performance
- Full rebuild about 28 s → **15 s** in one process (about 50 s before v0.8.0). Standalone: `collect.py`
  rebuild 8.2 → 3.0 s, `insights.py` 3.3 → 1.4 s, `models/stock_flow_ncic.py` 4.5 → 3.2 s,
  `circumstances.py` 3.7 → 3.1 s.
- Every output checked identical to before (persons, events, timeline content, circumstances, facts, insights,
  model results, dashboard data, exchange outbox, `results/`, Word report text), apart from the two new columns.

## [0.8.0] - 2026-10-25

### Changed
- Report, report data and dashboard data rebuilt from the Oct 25 weekly collection (139 cases found since
  collection began; 7,571 open child cases, 4,728 young adults).
- **Seasonality is per day:** monthly shares are adjusted for month length (and January 1, which is excluded).
  Children's July vs. February gap is +53% per day (+68% on raw shares). Raw shares kept as `raw_shares`.
- **Race comparisons also adjust for geography:** each group is compared with the population of the states its
  cases come from, as well as the nation (`race_state_adjusted`). Report and dashboard show both; the young-adult
  American Indian / Alaska Native ratio is 4.7x nationally and 2.4x against the states cases come from.
- README: the companion UC-Placement repository is public.

### Added
- `early_resolution` in `report/facts.json` and the report: share of NCMEC child cases found between the last two
  runs, by how long they had been open (23% of cases open ≤ 30 days within 3 days; 0.1% over 5 years).
- MODELING.md: math review of every calculation, with corrections, caveats and new angles.

### Performance
- Pipeline about 50 s → 28 s with identical outputs: `models/stock_flow_ncic.py` 20.6 s → 4.5 s (12 restarts,
  no backtest of the unidentifiable two-group model), `insights.py` 7.2 s → 3.3 s (raw records and Census
  tables read once).

## [0.7.0] - 2026-10-23

### Added
- `analysis/open_case_metrics.py` (pandas + NumPy): years open and implied resolution rate by case age,
  cases found so far, FBI juvenile flows; children and young adults separately; results in `results/`.
- `sql/ncic_flows.sql`: CTE and window functions (`LAG`, moving `AVG`) over the FBI juvenile figures.
- `sql/practice/`: dummy database (synthetic, seeded) and `caseload_by_region.sql` with four joins and
  aggregate functions; `sql/run_sql.py` runs any statement with DuckDB.
- `models/MODEL_CARD.md`: model card for the national stock-and-flow model.
- `tests/`: pytest checks that each SQL statement matches pandas.
- `requirements.txt`: pandas, DuckDB, pytest.
- `report/dashboard_data.py`: writes the interactive dashboard's datasets (`report/dashboard/*.json`):
  aggregate counts only, every row tagged child or adult so the dashboard shows one group at a time.

## [0.6.0] - 2026-10-22

### Added
- `models/stock_flow_ncic.py`: national stock-and-flow model of active juvenile records from FBI NCIC
  yearly statistics (2015–2020, 2022–2025), with one-year-ahead backtests; data in
  `models/ncic_juvenile_by_year.csv`, results in `models/stock_flow_results.json`, chart in the report.
- `requirements.txt`, including `matplotlib` and `python-docx` for reporting, `scipy` for analysis and models,
  and `libpysal` for spatial analysis (neighbor weights; brings in `geopandas`, `shapely`, `pandas`).

### Changed
- Word report rebuilt children-first and retitled *Missing Children in the United States*: Part 1 is children
  only (compared with Census ages 0–17); Part 2 is young adults (18–25, compared with ages 18–25). New
  insight on the national model; new source [9] (FBI NCIC yearly statistics).
- `insights.py`, `report/make_facts.py` and `report/charts.py` compute and draw children and young adults
  separately (charts end in `_child` / `_adult`), count only cases still open on the latest collection,
  and take the collection date from `data/state.json`.
- With children alone, over-representation versus population is Black 2.4x, Hispanic 1.6x, American Indian /
  Alaska Native 2.0x; for young adults, American Indian / Alaska Native is 4.7x (the pooled 0–25 figures
  were 2.2x, 1.5x and 2.6x).

### Fixed
- `exchange/export_exchange.py` now leaves out cases found since an earlier run (open cases only, as the
  contract says).

### Removed
- Pooled 0–25 charts (`report/charts/age_sex.png` and six others), replaced by child and adult versions.

## [0.5.0] - 2026-10-22

### Added
- `MODELING.md`: status of predictive modeling and ranked candidates (children only; adults separate).
- `probes/text_classifier_probe.py`: checks whether a classifier trained on NCMEC case types beats the keyword rules (it scores high only by learning poster wording and dates).
- `scheduled_run.py` and a weekly Windows scheduled task ("MP weekly collection", Sundays 10:00 AM;
  catches up after missed runs): collect, refresh derived files, log to `data/logs/`.
- Per-run counts (listed, new, relisted, no longer listed, delisted) per source in `data/state.json`.

## [0.4.1] - 2026-10-22

### Added
- README section "Built alongside another project", linking to the companion UC-Placement repository
  (private until its review is complete).

## [0.4.0] - 2026-10-22

### Added
- `age_group` column (`child` / `adult` / `unknown`) in `output/persons.csv`, `output/events.csv` and
  `output/circumstances.csv`. Children are under 18 for the whole recorded age range; adults are 18–25;
  records without an age, or whose age range straddles 18, are `unknown` (3 records).
- `exchange/`: aggregate exchange contract v1.0 (`EXCHANGE.md`) and `export_exchange.py`. Children and
  adults are separate measures; counts under 5 are marked unpublishable; optional local tag rules
  (`exchange/tags.local.json`) and peer-county counts (`--peer`).
- `CHANGELOG.md`; README sections on age groups, layout and the exchange.

### Changed
- Child counts now use the strict `age_group` rule. One record whose age range straddles 18 is no
  longer counted as a child (open under-18 cases with last contact in FY2014–FY2025: 2,893 → 2,892).

### Removed
- Local-only folders for an adjacent project moved out of this repository's folder (they were never
  committed).

## [0.3.0] - 2026-10-22

### Added
- Public GitHub repository (code and reports only; `data/` and `output/` are not committed).
- `paper/`: notes on Adam, Sokolowski & Banks (2009) with numerical checks (`verify_adam2009.py`).

## [0.2.0] - 2026-10-22

### Added
- `insights.py`: nine insights with Census Bureau Vintage 2024 population comparisons; `report/charts.py`
  (seven charts); `report/make_facts.py`.
- Word report: Insights section, Census source, limitations on population comparisons.

### Fixed
- A stray control character in a `collect.py` pattern that separates "her car was found" from the
  person being found; outputs rebuilt (no counts changed).
- Seasonality now leaves out the last 12 months and January 1 dates (placeholder dates).

### Removed
- The NamUs "missing from tribal land" field from analysis: its values are unreliable.

## [0.1.0] - 2026-10-21

### Added
- `collect.py`: open NamUs cases (age at disappearance ≤ 25) and NCMEC child posters; timelines
  (before / last contact / between / found); delisting detection between runs.
- `circumstances.py`: how, where and doing what, by keyword rules.
- Sourced Word report (`Missing Children and Young Adults - Circumstances Report.docx`).

### Fixed
- 265 NCMEC posters for unidentified deceased children excluded (12,618 → 12,353 people).
- "Found" detection no longer counts cars or belongings, "never returned home", or a parent returning home.
