"""Stock-and-flow model of active juvenile missing-person records (FBI NCIC), 2015-2025.

The linear compartment form of the predator-prey idea (see paper/): records flow in (entries) and out
(located, returned, cancelled) at different speeds. Annual data can't see within-year exits, so each
model is:
    active(t) = a * entries(t) + sum_k S_k(t)
    S_k(t)    = S_k(t-1) * exp(-c_k) + p_k * entries(t) * (1 - exp(-c_k)) / c_k
  a        years a "fast" record stays open on average (fast share / fast rate), i.e. resolved within weeks
  p_k, c_k share of entries in slower compartment k and its exit rate per year
Entries arrive evenly through the year. 2021 entries (report not online) are interpolated.

Compared with two baselines:
  persistence  active(t) = active(t-1)
  ratio        active(t) = entries(t) * active(t-1) / entries(t-1)   (Little's law, last year's mean duration)
Backtest: fit on years up to Y-1, predict Y from Y's entries, for Y = 2020, 2022, 2023, 2024, 2025.

Juveniles only (under 18 at entry, as the FBI reports them). Usage: python models/stock_flow_ncic.py
"""
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent


def load():
    rows = list(csv.DictReader(open(HERE / "ncic_juvenile_by_year.csv", encoding="utf-8")))
    years = [int(r["year"]) for r in rows]
    ent = {int(r["year"]): float(r["entries_u18"]) for r in rows if r["entries_u18"]}
    act = {int(r["year"]): float(r["active_u18_dec31"]) for r in rows if r["active_u18_dec31"]}
    for y in years:  # interpolate missing entries (2021) for the dynamics only
        if y not in ent:
            ent[y] = (ent[y - 1] + ent[y + 1]) / 2
    return years, ent, act


def simulate(theta, k, years, ent):
    """theta = [log a, (logit p_k, log c_k)...]; slow stocks start at steady state for the first year."""
    a = math.exp(theta[0])
    comps = [(1 / (1 + math.exp(-theta[1 + 2 * i])), math.exp(theta[2 + 2 * i])) for i in range(k)]
    stocks = [p * ent[years[0]] / c for p, c in comps]
    out = {}
    for y in years:
        stocks = [s * math.exp(-c) + p * ent[y] * (1 - math.exp(-c)) / c for s, (p, c) in zip(stocks, comps)]
        out[y] = a * ent[y] + sum(stocks)
    return out, a, comps


STARTS = 12  # random restarts per fit; 40 gave the same optima on this data (checked 2026-10-25)


WARM_STARTS = 3  # random restarts added to a warm start (the previous backtest year's fit)


def fit(k, years, ent, act, fit_years, warm=None):
    """Best of several least-squares fits; `warm` (earlier data's fit) is tried first, with fewer random starts."""
    best = None
    rng = np.random.default_rng(0)
    x0s = [list(warm)] if warm is not None else []
    x0s += [[math.log(0.05)] + [v for _ in range(k) for v in (rng.uniform(-9, -4), rng.uniform(-5, 1))]
            for _ in range(WARM_STARTS if warm is not None else STARTS)]  # multi-start: the surface has flat directions
    for x0 in x0s:
        res = least_squares(lambda th: [math.log(simulate(th, k, years, ent)[0][y] / act[y]) for y in fit_years],
                            x0, bounds=([-8] + [-15, -8] * k, [0] + [0, 3] * k))
        if best is None or res.cost < best.cost:
            best = res
    return best


def chart(years, ent, act, pred, a, obs):
    """Active under-18 records: FBI figures vs the one-slow-compartment fit, split fast / slow."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Arial", "font.size": 9})
    BLUE, ORANGE, INK2, GRID = "#2a78d6", "#eb6834", "#52514e", "#e6e5e1"
    fig, ax = plt.subplots(figsize=(6.5, 2.7))
    fast = [a * ent[y] for y in years]
    slow = [pred[y] - a * ent[y] for y in years]
    ax.bar(years, fast, color=BLUE, width=0.6, edgecolor="white", linewidth=1.5, label="Fast group (closes in weeks)")
    ax.bar(years, slow, bottom=fast, color=ORANGE, width=0.6, edgecolor="white", linewidth=1.5,
           label="Slow group (half-life ~3 years)")
    ax.plot(obs, [act[y] for y in obs], "o", color="black", markersize=4, label="FBI: active on Dec 31")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, colors=INK2)
    ax.set_xticks(years, [str(y) if y != 2021 else "2021*" for y in years])
    ax.set_ylabel("Active records, under 18", color=INK2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(frameon=False, fontsize=8, loc="upper right", ncol=3, bbox_to_anchor=(1, 1.16))
    fig.tight_layout()
    out = HERE.parent / "report/charts/ncic_stock_flow.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)


def main():
    years, ent, act = load()
    obs = sorted(act)
    R = {"data_years": obs, "entries_2021_interpolated": ent[2021]}

    # Little's law snapshot
    R["mean_days_open"] = {y: round(365 * act[y] / ent[y], 1) for y in obs}

    # Full-sample fits
    fits = {}
    for k in (0, 1, 2):
        if k == 0:  # a only
            a = sum(act[y] for y in obs) / sum(ent[y] for y in obs)
            pred = {y: a * ent[y] for y in years}
            rss = sum(math.log(pred[y] / act[y]) ** 2 for y in obs)
            fits[k] = dict(params={"a_years": a}, rss=rss, n_params=1)
            continue
        res = fit(k, years, ent, act, obs)
        pred, a, comps = simulate(res.x, k, years, ent)
        rss = sum(math.log(pred[y] / act[y]) ** 2 for y in obs)
        fits[k] = dict(params={"a_days": round(365 * a, 1),
                               "compartments": [{"share_of_entries": p, "exit_rate_per_year": c,
                                                 "half_life_years": math.log(2) / c} for p, c in comps]},
                       rss=rss, n_params=1 + 2 * k,
                       fitted={y: round(pred[y]) for y in obs},
                       slow_share_of_active={y: round(1 - a * ent[y] / pred[y], 3) for y in obs})
        if k == 1:
            chart(years, ent, act, pred, a, obs)
    n = len(obs)
    for k, f in fits.items():
        f["aicc"] = n * math.log(f["rss"] / n) + 2 * f["n_params"] + (2 * f["n_params"] * (f["n_params"] + 1)) / max(1, n - f["n_params"] - 1)
    R["fits"] = fits

    # Backtest: one-year-ahead, refitting on earlier years only
    test_years = [2020, 2022, 2023, 2024, 2025]
    # k2 is not backtested: on yearly totals it always collapses onto k1 (see fits["2"])
    bt = {name: [] for name in ("persistence", "ratio", "k0", "k1")}
    warm = {}
    for y in test_years:
        prev = max(t for t in obs if t < y)
        train = [t for t in obs if t < y]
        truth = act[y]
        bt["persistence"].append((y, act[prev], truth))
        bt["ratio"].append((y, ent[y] * act[prev] / ent[prev], truth))
        a0 = sum(act[t] for t in train) / sum(ent[t] for t in train)
        bt["k0"].append((y, a0 * ent[y], truth))
        for k in (1,):
            if len(train) <= 1 + 2 * k:
                bt[f"k{k}"].append((y, None, truth))
                continue
            res = fit(k, years, ent, act, train, warm=warm.get(k))
            warm[k] = res.x  # the next (later) backtest year starts from this one; never from later data
            bt[f"k{k}"].append((y, simulate(res.x, k, years, ent)[0][y], truth))
    R["backtest"] = {}
    for name, rows in bt.items():
        errs = [abs(p - t) / t for _, p, t in rows if p is not None]
        R["backtest"][name] = {"mape_percent": round(100 * sum(errs) / len(errs), 2) if errs else None,
                               "by_year": {y: (round(p) if p is not None else None, int(t)) for y, p, t in rows}}

    (HERE / "stock_flow_results.json").write_text(json.dumps(R, indent=1), "utf-8")
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    main()
