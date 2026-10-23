"""Draw the insight charts (PNG) from report/insights.json for the Word report.

Colors are slots 1-2 of the dataviz reference palette (validated there for CVD separation);
the population reference series uses a neutral grey because it is a baseline, not an identity.

Usage: python report/charts.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ALL = json.loads((HERE / "insights.json").read_text("utf-8"))
OUT = HERE / "charts"
OUT.mkdir(exist_ok=True)

BLUE, ORANGE, GREY_REF = "#2a78d6", "#eb6834", "#a8adb5"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
plt.rcParams.update({
    "font.family": "Arial", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "axes.linewidth": 0.8,
    "svg.fonttype": "none",
})
W = 6.5  # inches: page text width


def frame(ax, grid_axis="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left" if grid_axis == "x" else "bottom"].set_color(GRID)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=220, facecolor="white")
    plt.close(fig)


def hbar(ax, labels, values, color=BLUE, fmt="{:.0f}", xmax=None):
    y = range(len(labels))
    ax.barh(list(y), values, height=0.58, color=color, edgecolor="white", linewidth=1.5)
    ax.set_yticks(list(y), labels)
    ax.invert_yaxis()
    xmax = xmax or max(values) * 1.18
    ax.set_xlim(0, xmax)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.012, yi, fmt.format(v), va="center", ha="left", color=INK, fontsize=8.5,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
    frame(ax, "x")


def draw(I, sfx):
    """All charts for one age group; files end in sfx (e.g. _child)."""
    # 1. Age at disappearance, by sex --------------------------------------------
    rows = I["age_sex"]
    ages = [r[0] for r in rows]
    fig, ax = plt.subplots(figsize=(W, 2.7))
    for idx, (label, color) in enumerate((("Female", BLUE), ("Male", ORANGE)), start=1):
        vals = [r[idx] for r in rows]
        ax.plot(ages, vals, color=color, linewidth=2, marker="o", markersize=3.2, label=label)
        peak = max(range(len(vals)), key=vals.__getitem__)
        if idx == 1:
            ax.annotate(f"{label}: {vals[peak]:,} at age {ages[peak]}", (ages[peak], vals[peak]),
                        xytext=(8, 4), textcoords="offset points", ha="left", va="center", fontsize=8.5, color=INK)
        else:  # open space right of the peak; thin leader line back to the point
            ax.annotate(f"{label}: {vals[peak]:,} at age {ages[peak]}", (ages[peak], vals[peak]),
                        xytext=(-60, -38), textcoords="offset points", ha="right", va="center", fontsize=8.5, color=INK,
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8, shrinkA=2, shrinkB=4))
    ax.set_xlabel("Age when they went missing")
    ax.set_ylabel("Open cases")
    ax.set_xticks(range(ages[0], ages[-1] + 1, 2 if len(ages) > 10 else 1))
    ax.legend(frameon=False, loc="upper left")
    frame(ax)
    save(fig, "age_sex" + sfx)

    # 2. Share female by how they went missing ------------------------------------
    lab = {"Runaway / left voluntarily": "Ran away / left on their own",
           "Possible foul play / homicide": "Possible foul play / homicide",
           "Family abduction": "Taken by a parent or relative",
           "Non-family abduction": "Abducted by a non-family member",
           "Outdoors / water (lost, drowning, accident)": "Lost, drowned or accident outdoors"}
    items = sorted(((lab[k], 100 * f / n) for k, (f, n) in I["female_share_by_type"].items() if n >= 10), key=lambda x: -x[1])
    fig, ax = plt.subplots(figsize=(W, 0.45 * len(items) + 0.6))
    hbar(ax, [i[0] for i in items], [i[1] for i in items], fmt="{:.0f}% female", xmax=100)
    ax.axvline(50, color=MUTED, linewidth=1, linestyle=(0, (3, 3)), zorder=1)
    ax.text(50, -0.75, "50%", ha="center", va="bottom", color=MUTED, fontsize=8)
    ax.set_xlabel("Share of cases who are female")
    save(fig, "female_share" + sfx)

    # 3. Race / ethnicity: cases vs population ------------------------------------
    keep = ["Black", "Hispanic", "American Indian / Alaska Native", "White", "Asian"]
    race = {r[0]: r for r in I["race"]}
    XMAX = max(100 * max(race[k][2], race[k][3]) for k in keep) + 12
    fig, ax = plt.subplots(figsize=(W, 2.9))
    h = 0.36
    for i, k in enumerate(keep):
        case, pop = 100 * race[k][2], 100 * race[k][3]
        ax.barh(i - h / 2, case, height=h, color=BLUE, edgecolor="white", linewidth=1.5,
                label="Share of open cases since 2016" if i == 0 else None)
        ax.barh(i + h / 2, pop, height=h, color=GREY_REF, edgecolor="white", linewidth=1.5,
                label=f"Share of U.S. population aged {I['ages'][0]}-{I['ages'][1]} (2024)" if i == 0 else None)
        ax.text(case + 0.8, i - h / 2, f"{case:.1f}%", va="center", fontsize=8.5)
        ax.text(pop + 0.8, i + h / 2, f"{pop:.1f}%", va="center", fontsize=8.5, color=INK2)
        ax.text(XMAX - 1, i, f"{race[k][4]:.1f}x", va="center", ha="right", fontsize=9, fontweight="bold",
                color=INK if race[k][4] >= 1 else INK2)
    ax.text(XMAX - 1, -0.85, "Cases vs\npopulation", ha="right", va="bottom", fontsize=7.5, color=MUTED)
    ax.set_yticks(range(len(keep)), [k.replace(" / ", " /\n") if len(k) > 20 else k for k in keep])
    ax.invert_yaxis()
    ax.set_xlim(0, XMAX)
    ax.set_xlabel("Percent")
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(0.86, 0.0), fontsize=8)
    frame(ax, "x")
    save(fig, "race" + sfx)

    # 4. Median years open, by how they went missing ------------------------------
    lab4 = dict(lab, **{"Not stated": "Not stated in the record"})
    items = sorted(((lab4[k], v[0]) for k, v in I["years_open_by_type"].items() if v[0] is not None and v[1] >= 10), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(W, 2.4))
    hbar(ax, [i[0] for i in items], [i[1] for i in items], fmt="{:.0f} years")
    ax.set_xlabel("Median years since last seen (open cases)")
    save(fig, "years_open" + sfx)

    # 5. Month of disappearance ----------------------------------------------------
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig, ax = plt.subplots(figsize=(W, 2.5))
    for (label, color) in (("All cases", BLUE), ("Lost, drowned or accident outdoors", ORANGE)):
        s = [100 * v for v in I["season"][label]["shares"]]
        ax.plot(range(12), s, color=color, linewidth=2, marker="o", markersize=3.2,
                label=f"{label} (n={I['season'][label]['n']:,})")
        pk = max(range(12), key=s.__getitem__)
        ax.annotate(f"{s[pk]:.1f}%", (pk, s[pk]), xytext=(0, 7), textcoords="offset points", ha="center",
                    fontsize=8.5)
    ax.axhline(100 / 12, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(11.4, 100 / 12 + 0.15, "even spread", ha="right", va="bottom", fontsize=7.5, color=MUTED)
    ax.set_xticks(range(12), months)
    ax.set_ylabel("Share of cases (%)")
    ax.set_ylim(0, max(14, max(100 * max(v["shares"]) for v in I["season"].values()) * 1.15))
    ax.legend(frameon=False, loc="lower center", ncol=2, fontsize=8)
    frame(ax)
    save(fig, "season" + sfx)

    # 6. Digital trail by era ---------------------------------------------------
    eras = [d[0] for d in I["digital"]]
    vals = [100 * d[1] / d[2] for d in I["digital"]]
    fig, ax = plt.subplots(figsize=(W, 2.3))
    ax.bar(range(len(eras)), vals, width=0.55, color=BLUE, edgecolor="white", linewidth=1.5)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.15, f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(range(len(eras)), [f"{e}\n({d[2]:,} cases)" for e, d in zip(eras, I["digital"])])
    ax.set_ylabel("% of cases")
    ax.set_ylim(0, max(vals) * 1.3)
    frame(ax)
    save(fig, "digital" + sfx)

    # 7. Countries named in family abductions -----------------------------------
    top = I["fam_countries"][:8]
    if not top:
        return
    fig, ax = plt.subplots(figsize=(W, 2.3))
    hbar(ax, [c for c, _ in top], [v for _, v in top], fmt="{:.0f}")
    ax.set_xlabel("Family-abduction cases naming the country")
    save(fig, "countries" + sfx)


for group in ("child", "adult"):
    draw(ALL[group], f"_{group}")
print("charts written to", OUT)
