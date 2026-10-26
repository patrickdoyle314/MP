"""Write the dashboard's datasets (aggregate counts only, no names) to report/dashboard/*.json.

Every row carries `group` ("child" or "adult") so the dashboard shows one group at a time and never
pools them. Reads report/facts.json, report/insights.json, models/*.json and output/persons.csv.

Usage: python report/dashboard_data.py   (after make_facts.py, insights.py, models/stock_flow_ncic.py)
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report/dashboard"
F = json.loads((ROOT / "report/facts.json").read_text("utf-8"))
INS = json.loads((ROOT / "report/insights.json").read_text("utf-8"))
SF = json.loads((ROOT / "models/stock_flow_results.json").read_text("utf-8"))
GROUPS = {"child": "Children (under 18)", "adult": "Young adults (18–25)"}
LABEL = {
    "Not stated": "Not stated in the record",
    "Runaway / left voluntarily": "Ran away / left on their own",
    "Outdoors / water (lost, drowning, accident)": "Lost, drowned or accident outdoors",
    "Family abduction": "Taken by a parent or relative",
    "Possible foul play / homicide": "Possible foul play / homicide",
    "Non-family abduction": "Abducted by a non-family member",
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RACES = ["Black", "Hispanic", "American Indian / Alaska Native", "White", "Asian"]


def main():
    found = {g: 0 for g in GROUPS}
    for p in csv.DictReader(open(ROOT / "output/persons.csv", encoding="utf-8-sig")):
        if p["status"] == "delisted" and p["age_group"] in found:
            found[p["age_group"]] += 1
    D = {k: [] for k in ("summary", "how_missing", "age_sex", "race", "years_open", "season", "states", "ncic")}
    for g, label in GROUPS.items():
        Fg, Ig = F[g], INS[g]
        stated = [(k, v) for k, v in Fg["type"] if k != "Not stated"]
        race = {r[0]: r for r in Ig["race"]}
        top_race = max(RACES, key=lambda r: race[r][4])
        D["summary"].append({
            "group": g, "label": label, "ages": f"{Ig['ages'][0]}–{Ig['ages'][1]}", "collected": F["collected"],
            "open_cases": Fg["n"], "not_stated_share": round(dict(Fg["type"]).get("Not stated", 0) / Fg["n"], 4),
            "top_cause": LABEL[stated[0][0]], "top_cause_share": round(stated[0][1] / Fg["n"], 4),
            "peak_age": Ig["peak_age"], "female_share": round(Ig["female_share_all"], 4),
            "found_since_start": found[g], "first_run": F["first_run"],
            "top_overrep_race": top_race, "top_overrep_ratio": round(race[top_race][4], 2),
        })
        for k, v in Fg["type"]:
            D["how_missing"].append({"group": g, "category": LABEL[k], "cases": v, "share": round(v / Fg["n"], 4)})
        for a, f, m in Ig["age_sex"]:
            D["age_sex"].append({"group": g, "age": a, "female": f, "male": m})
        for r in RACES:
            adj = {x[0]: x for x in Ig["race_state_adjusted"]}[r]
            D["race"].append({"group": g, "race": r, "case_share": round(race[r][2], 4),
                              "pop_share": round(race[r][3], 4), "ratio": round(race[r][4], 2),
                              "pop_share_case_states": round(adj[2], 4),
                              "ratio_state_adjusted": round(adj[3], 2) if adj[3] else None})
        for k, (med, n) in Ig["years_open_by_type"].items():
            if med is not None and n >= 10:
                D["years_open"].append({"group": g, "category": LABEL[k], "median_years": round(med, 1), "cases": n})
        s_all = Ig["season"]["All cases"]["shares"]
        s_out = Ig["season"]["Lost, drowned or accident outdoors"]["shares"]
        for i in range(12):
            D["season"].append({"group": g, "month_num": i + 1, "month": MONTHS[i],
                                "all_cases": round(s_all[i], 4), "outdoors": round(s_out[i], 4)})
        split = Ig["state_source_split"]
        for st, n, pop, rate in Ig["state_rates"]:
            D["states"].append({"group": g, "state": st, "cases": n, "rate_per_100k": round(rate, 1),
                                "from_namus": split.get(st, {}).get("namus", 0),
                                "from_ncmec": split.get(st, {}).get("ncmec", 0)})
    rows = list(csv.DictReader(open(ROOT / "models/ncic_juvenile_by_year.csv", encoding="utf-8")))
    fit = SF["fits"]["1"]
    a_years = fit["params"]["a_days"] / 365
    for r in rows:
        y = int(r["year"])
        entries = float(r["entries_u18"]) if r["entries_u18"] else SF["entries_2021_interpolated"]
        fitted = fit["fitted"].get(str(y))
        fast = round(a_years * entries)
        D["ncic"].append({"year": y, "entries_u18": int(entries), "entries_interpolated": not r["entries_u18"],
                          "active_u18": int(r["active_u18_dec31"]) if r["active_u18_dec31"] else None,
                          "model_fast": fast if fitted else None,
                          "model_slow": (fitted - fast) if fitted else None})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in D.items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
        print(f"{name}.json: {len(data)} rows")


if __name__ == "__main__":
    main()
