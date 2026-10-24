# Model card: juvenile missing-person records, stock-and-flow model

*Status: built and backtested. Last updated 2026-10-23. Code: `models/stock_flow_ncic.py`.*

## Purpose

Describe how long juvenile missing-person records stay open nationally, using the FBI's yearly totals.
It is the linear compartment form of the predator-prey idea studied in `paper/` (Adam, Sokolowski & Banks,
2009): records flow in when a child is reported missing and flow out when the record is closed.
**Children only** (the FBI's under-18 counts). Aggregate national figures; nothing about any individual.

## Data

| Item | Value |
|---|---|
| Source | FBI CJIS, *NCIC Missing Person and Unidentified Person Statistics*, yearly reports 2015–2020 and 2022–2025 |
| Figures | Under-18 records entered during the year; under-18 records active on December 31 |
| File | `models/ncic_juvenile_by_year.csv` (each row cites its report) |
| Gap | The 2021 report is not online; 2021 entries are interpolated for the model's dynamics only |

`sql/ncic_flows.sql` and `analysis/open_case_metrics.py` derive the same flows from this file:
records closed per year (active at start + entered − active at end) and average days open
(365 × active ÷ entered), 24–31 days in every year.

## Model

Records are split between a fast group, which closes within weeks, and a slow group:

$$
A_t = a\,E_t + S_t, \qquad
S_t = S_{t-1}\,e^{-c} + p\,E_t\,\frac{1 - e^{-c}}{c}
$$

| Symbol | Meaning | Estimate |
|---|---|---|
| $E_t$ | juvenile records entered in year *t* (data) | — |
| $A_t$ | juvenile records active on December 31 (data) | — |
| $a$ | average time a fast-group record stays open (years) | 13.3 days |
| $p$ | share of entries that join the slow group | 0.8% |
| $c$ | slow group's closure rate per year | 0.239 (half-life 2.9 years) |
| $S_t$ | slow group's active records at year end | 49–53% of active records every year |

Entries arrive evenly through the year; the slow group starts at its steady state. Parameters are fit by
least squares on $\log A_t$ with 40 random starts (`scipy.optimize.least_squares`).

**Model choice.** Versions with 0, 1 and 2 slow groups were compared. A second slow group collapses onto
the first: yearly totals can identify one slow timescale, not more. By AICc the simplest model (a
constant average duration) is preferred; the one-slow-group model is kept because it describes the
structure the open-case data also shows (resolution rates falling from about 3 per year for new cases to
about 0.01 per year for cases open 10 years or more; `results/open_cases_by_years_open.csv`).

## Evaluation

One year ahead, refitting on earlier years only (2020, 2022–2025):

| Method | Mean absolute % error |
|---|---|
| Same as last year | **7.8%** |
| Last year's average duration × this year's entries | 8.1% |
| Constant average duration | 9.8% |
| One slow group (this model) | 11.8% |

**The model explains structure but does not forecast better than simple rules.** Active juvenile records
fell 13.4% in 2024 and 15.7% in 2025, faster than entries (−6.9%, −7.4%), so something in how records close
changed; yearly totals cannot say what.

## Intended use

- Explaining why most missing children are found within weeks while a small share of records stays open
  for years.
- Context for the open-case analysis and the report (`report/`).

## Not intended for

- Forecasting the number of active records (use "same as last year").
- Anything about an individual case, or ages 18–25 (the FBI does not split them out the same way).

## Limitations

- Ten yearly points; 2021 missing.
- "Under 18" is as the FBI reports it.
- Records can close for reasons other than the child being found (for example, invalid records), which
  the totals don't separate.

## Reproduce

```bash
pip install -r requirements.txt
python models/stock_flow_ncic.py
python sql/run_sql.py sql/ncic_flows.sql
python -m pytest
```
