# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
dates are when the change was made.

## [Unreleased]

### To do
- Rebuild `insights.py` and the Word report children-first, with adult figures in their own section.

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
