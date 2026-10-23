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
| 2 | **Stock-and-flow model** (the linear compartment form of the predator-prey idea) | National active juvenile records from new reports and closures | FBI NCIC annual statistics, several years (entries, removals, active records by age); public PDFs | **Feasible now** with downloads. At least three compartments (days, years, decades), not one rate |
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

`pip install scikit-learn scipy` for the probes.
