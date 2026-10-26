# Predictive modeling: status and candidates

*Assessed 2026-10-22.* All candidates are for **children** (`age_group == "child"`); the same models can be
run for adults as a separate analysis, never pooled.

## What exists today

Nothing predictive. The analysis is descriptive: counts, keyword classification (`circumstances.py`),
binomial tests and rank correlations (`insights.py`). The predator-prey model from Adam, Sokolowski & Banks
(2009) is only re-derived and checked against the paper (`paper/verify_adam2009.py`), not fitted to our data.

The main blocker: no case has been seen to close yet. Models of whether and when a child is found need
outcome labels, which only repeated runs produce (a case dropping off a public listing is the "found"
signal). **Since 2026-10-22 a weekly scheduled run builds this history** (README > Scheduled runs); each
run's listed, new and delisted counts are kept in `data/state.json` and `data/logs/runs.csv`.

Each delisting is known only to a window (between two runs), so time to resolution is **interval-censored**
at weekly resolution; cases still open are right-censored; cases first seen already open are
left-truncated. The survival model must handle all three.

## Candidates, ranked

| # | Candidate | Predicts | Data it needs | Ready? |
|---|---|---|---|---|
| 1 | **Time to resolution** (survival analysis) | How long cases stay open, by age band, sex, how they went missing, state, source | Repeated collection runs (weekly), so closed cases are observed | **After runs.** Needs left-truncation handling (we only see cases still open on day one) and a "long-term open" fraction (cure model), since the resolution rate drops from about 1.1/year to 0.011/year as cases age |
| 2 | **Stock-and-flow model** (the linear compartment form of the predator-prey idea) | National active juvenile records from new reports and closures | FBI NCIC annual statistics, 2015–2025 | **Built** (see below). Yearly totals identify one slow group, not three; it explains structure but doesn't beat “same as last year” |
| 3 | **New-case counts by month** (Poisson / negative binomial) | Seasonal and trend pattern of new disappearances | New-case dates from repeated runs; the open-case snapshot is biased toward recent and unresolved cases | **After runs** |
| 4 | **Text classifier** for how a child went missing | Runaway / family abduction / etc. from the case summary | Hand-labeled NamUs summaries | **Not as-is.** See probe below |
| 5 | True predator-prey coupling (one group drawing others in) | Recruitment between missing children | Links between cases over time | **No.** Nothing in public data measures it |

**Off-limits:** individual risk scores, or anything that predicts where a particular child is. These are
public case listings of real children.

## Probe results

### Text classifier (`probes/text_classifier_probe.py`)
550 children have an NCMEC case type and a summary (67% endangered runaway). Five-fold cross-validation:

| method | precision | recall | F1 | ROC-AUC |
|---|---|---|---|---|
| keyword rule (`circumstances.py`) | 0.571 | 0.011 | 0.021 | — |
| TF-IDF + logistic regression | 0.927 | 0.927 | 0.927 | 0.929 |

The high score is **misleading.** The strongest runaway cues are "2026", "last seen", "tattoo" and "hoodie":
the wording and recency of NCMEC's current poster template, not running away. NamUs summaries are written
differently (11% all-caps vs 67%), so the model would not transfer. What the probe does show: NCMEC's runaway
label carries information that the poster text doesn't, which is why the keyword rule finds 1% of them.

## Requirements

`pip install -r requirements.txt`.

## Candidate 2 built: national stock-and-flow model (2026-10-22)

`models/stock_flow_ncic.py`, on FBI NCIC juvenile (under 18) figures for 2015–2020 and 2022–2025
(2021 entries interpolated; report not online).

| Finding | Value |
|---|---|
| Average time a juvenile record stays open (active ÷ entries) | 24–31 days a year; highest 2020–2022, lowest 2025 |
| Fast group | about 99.2% of records; closes in about 13 days on average |
| Slow group | about 0.8% of records; half-life about 2.9 years |
| Slow group's share of active records | 49–53% every year |
| Second slow group | Not identifiable: it collapses onto the first; AICc prefers the simplest model |

**Backtest, one year ahead (mean absolute % error):** same as last year 7.8%; last year's duration × this
year's entries 8.1%; constant duration 9.8%; one slow group 11.8%. **The model explains structure but
does not forecast better than simple rules.** Active juvenile records fell 13% (2024) and 16% (2025),
faster than entries, so something in how records close changed; yearly totals cannot say what.
Monthly data, or the age of active records, would be needed to go further.

## Math review (2026-10-25)

Every calculation behind the report and dashboard was re-checked. Corrections and new angles:

| # | Check | Finding | Action |
|---|---|---|---|
| 1 | **Seasonality** compared raw monthly shares | Months differ in length (February 28.25 days; January loses Jan 1, excluded as a placeholder). Raw July vs. February for children: +68%; per day: **+53%**. Young adults: June vs. December +40% per day (the raw low month was January) | Fixed: shares are now per-day adjusted; raw shares kept as `raw_shares` |
| 2 | **Race vs. population** compared with the national population | Cases are concentrated in a few states (TX, FL, TN, VA...) whose populations differ from the nation's. Against the population of the states the cases come from (each state weighted by its share of cases): children Black 2.33x → **2.25x**, Hispanic 1.57x → 1.42x, American Indian / Alaska Native 2.08x → 1.85x; young adults American Indian / Alaska Native **4.74x → 2.41x**, Hispanic 1.40x → 1.15x | Added `race_state_adjusted`; report and dashboard show both. The children's gaps are mostly not geography; about half the young-adult Native gap is |
| 3 | **Early resolution** (new data from weekly runs) | Of NCMEC child cases listed Oct 22, found by Oct 25: 23% of those open ≤ 30 days, 7% at 31–90 days, 1% at 3–12 months, 0.1% over 5 years | Added to facts and report. Confirms the fast/slow structure the national model assumes |
| 4 | **NamUs freshness** | NamUs's public API has published no new case since Oct 13, 2026 (newest ID 163715, any age); our listing matches it exactly. Existing records are still edited and re-downloaded | Data note; not a collector fault |
| 5 | **Little's law** (mean days open = active ÷ entries) | Assumes steady state. FBI entries and removals match within 0.5% every year (e.g. 2023: 563,389 vs 563,644) | Holds |
| 6 | **FBI "under 18" active records** | The reports don't say whether age is at entry or current age; records aging past 18 would leave the juvenile count and look like closures | Caveat on the slow group's size |
| 7 | **Slow group's share of active records** | Depends on assuming the slow stock was in steady state in 2015 | Caveat; the yearly data can't separate it |
| 8 | **Years open by cause** | Medians describe cases still open (survivors); resolved runaways have left, so open runaway cases look recent | Already stated; kept |
| 9 | **UC alignment tests** (4 binomial tests) | Timing p = 0.004 survives a Bonferroni correction for 4 tests (0.017). Siblings in one case are not independent, which slightly overstates certainty | Caveat for the alignment notes |
| 10 | **Code speed** | Pipeline 50 s → about 28 s: `stock_flow_ncic.py` 20.6 s → 4.5 s (12 restarts instead of 40, no backtest of the unidentifiable two-group model; same fit and errors), `insights.py` 7.2 s → 3.3 s (raw records and Census tables read once) | Outputs checked identical before and after |
