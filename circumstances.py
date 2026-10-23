"""Keyword-classify each person's circumstances text: how they went missing, place, activity.

Usage: python circumstances.py output/persons.csv   (writes output/circumstances.csv)
"""
import csv, collections, json, re, sys, random

P = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))

TYPE = [  # first match wins, most specific first
    ("Family abduction", r"\b(?:(?:abduct|kidnap)\w*[^.]{0,60}\b(?:mother|father|parent|biological|custod\w*)\b|(?:abducted|kidnapped|taken) by (?:her|his|their) (?:biological |non-?custodial )?(?:mother|father|parent|mom|dad|grandmother|grandfather|aunt|uncle|step\w+)|non-?custodial|custodial interference|parental (?:abduction|kidnapping)|taken by (?:her|his|their) (?:mother|father|parent|mom|dad)|(?:mother|father|parent) (?:took|fled|absconded)|in the company of (?:her|his|their) (?:biological |non-?custodial )?(?:mother|father|parent|mom|dad)|violation of (?:a )?custody)\b"),
    ("Non-family abduction", r"\b(?:abduct\w*|kidnap\w*|forced (?:into|her|him)|taken by (?:an? )?(?:unknown|stranger|man|woman|male|female)|pulled (?:her|him) into|lured)\b"),
    ("Runaway / left voluntarily", r"\b(?:ran away|run ?away|left (?:home|the (?:home|residence|house)) (?:without|voluntarily)|left voluntarily|left on (?:her|his|their) own|climbed out (?:of )?(?:a |the |her |his )?window|snuck out|walked away from|left (?:the |her |his )?(?:group home|foster|placement|facility|shelter))\b"),
    ("Possible foul play / homicide", r"\b(?:foul play|homicide|murder\w*|suspect\w*|killed|shot)\b"),
    ("Outdoors / water (lost, drowning, accident)", r"\b(?:drown\w*|swept|swimming|hiking|lost in|fell (?:into|off)|kayak\w*|canoe\w*|boat\w*|river|ocean|lake)\b"),
]
PLACE = [
    ("Home / family residence", r"\b(?:home|residence|house|apartment|bedroom|backyard|front yard)\b"),
    ("Foster / group home / shelter / facility", r"\b(?:foster|group home|placement|shelter|residential|facility|juvenile (?:hall|detention)|treatment center|DCFS|CPS|youth home|children'?s home)\b"),
    ("School / college", r"\b(?:school|campus|college|university|class(?:es)?|dorm\w*)\b"),
    ("Friend's / relative's home", r"\b(?:friend'?s (?:home|house|residence|apartment)|(?:grand(?:mother|father|parent)|aunt|uncle|cousin|relative|boyfriend|girlfriend)'?s (?:home|house|residence|apartment))\b"),
    ("Street / walking / bus", r"\b(?:walking|walked|street|road|highway|bus stop|on foot|sidewalk|hitchhik\w*|intersection)\b"),
    ("Store / mall / restaurant", r"\b(?:store|mall|shop\w*|restaurant|gas station|convenience|walmart|mcdonald'?s|market)\b"),
    ("Workplace", r"\b(?:work(?:place)?|job|shift|employer)\b"),
    ("Party / bar / club", r"\b(?:party|bar|club|nightclub|concert|festival)\b"),
    ("Park / outdoors / water", r"\b(?:park|woods|forest|trail|river|lake|beach|ocean|creek|campground|camping)\b"),
    ("Vehicle / transit", r"\b(?:vehicle|car|truck|bus|train|airport|greyhound|ride)\b"),
    ("Hospital", r"\b(?:hospital|medical center|clinic|emergency room)\b"),
]
ACTIVITY = [
    ("Left home (often after argument / at night)", r"\b(?:left (?:home|the (?:home|residence|house)|(?:her|his|their) (?:home|residence))|walked out|snuck out|climbed out)\b"),
    ("Went to / from school", r"\b(?:(?:to|from|at|for|attend\w*|walk\w* to) school|school bus|after school|before school)\b"),
    ("Discovered gone (bed / morning / wellness check)", r"\b(?:went to (?:bed|sleep)|(?:was|were) not in (?:her|his|their) (?:bed|room)|woke up|following morning|next morning|wellness check|bed check|room was empty)\b"),
    ("Walking / on foot", r"\b(?:walking|walked|on foot|jogging|hitchhik\w*)\b"),
    ("Visiting friend / boyfriend / girlfriend", r"\b(?:friend|boyfriend|girlfriend|hang(?:ing)? out)\b"),
    ("Argument / family conflict", r"\b(?:argument|argued|fight|dispute|upset|disagreement)\b"),
    ("Going to / leaving work", r"\b(?:to work|from work|at work|work shift|left work|for work)\b"),
    ("Party / night out", r"\b(?:party|bar|club|night out|drinking)\b"),
    ("Driving / riding in a vehicle", r"\b(?:driving|drove|got into (?:a|an|the)|picked (?:her|him|them) up|ride|hitchhik\w*)\b"),
    ("Playing outside", r"\b(?:playing|played|bike|bicycle|outside)\b"),
    ("Traveling / moving", r"\b(?:(?<!may be )(?<!may have )(?<!possibly )traveling|flew|flight|moved to|(?:on|from) a trip|vacation|took a bus)\b"),
    ("Swimming / hiking / outdoors", r"\b(?:swimming|hiking|fishing|camping|boating|kayak\w*)\b"),
]
BOILERPLATE = re.compile(r"^\W*\S+(?: \S+){0,3} (?:was|were) last seen (?:on|in) [^.]{0,40}\.?\W*$", re.I)

def classify(text, table):
    return [name for name, rx in table if re.search(rx, text, re.I)]

rows = []
for p in P:
    t = re.sub(r"\s+", " ", p["circumstances"].replace("[NCMEC]", " ")).strip()
    ct = p.get("case_type", "")
    nc = {"endangeredRunaway": "Runaway / left voluntarily", "familyAbduct": "Family abduction",
          "nonFamilyAbduct": "Non-family abduction", "lostInjuredMissing": "Outdoors / water (lost, drowning, accident)"}.get(ct)
    types = classify(t, TYPE)
    rows.append(dict(p=p, text=t, thin=len(t) < 25 or bool(BOILERPLATE.match(t)),
                     type=nc or (types[0] if types else "Not stated"),
                     place=classify(t, PLACE), act=classify(t, ACTIVITY)))

def age_band(p):
    try:
        a = int(p["age_missing_min"])
    except ValueError:
        return "?"
    return "0-11" if a < 12 else "12-17" if a < 18 else "18-25"

out = {"n": len(rows), "thin": sum(r["thin"] for r in rows)}
rich = [r for r in rows if not r["thin"]]
out["rich"] = len(rich)
out["type_all"] = collections.Counter(r["type"] for r in rows).most_common()
for band in ("0-11", "12-17", "18-25"):
    rb = [r for r in rich if age_band(r["p"]) == band]
    out[f"band_{band}"] = dict(
        n=len(rb),
        type=collections.Counter(r["type"] for r in rb).most_common(),
        place=collections.Counter(x for r in rb for x in r["place"]).most_common(),
        act=collections.Counter(x for r in rb for x in r["act"]).most_common(),
    )
out["place_rich"] = collections.Counter(x for r in rich for x in r["place"]).most_common()
out["act_rich"] = collections.Counter(x for r in rich for x in r["act"]).most_common()
out["no_place"] = sum(not r["place"] for r in rich)
out["no_act"] = sum(not r["act"] for r in rich)
abd = [r for r in rich if r["type"] == "Non-family abduction"]
out["abd_place"] = collections.Counter(x for r in abd for x in r["place"]).most_common()
out["abd_act"] = collections.Counter(x for r in abd for x in r["act"]).most_common()
out["abd_n"] = len(abd)

def pct(c, n): return ", ".join(f"{k} {v} ({100*v/n:.0f}%)" for k, v in c)
print("persons", out["n"], "| any place/activity stated:", sum(bool(r["place"] or r["act"]) for r in rows))
print("TYPE all:", pct(out["type_all"], out["n"]))
for band in ("0-11", "12-17", "18-25"):
    b = out[f"band_{band}"]; n = b["n"]
    print(f"\n== {band} (n={n} with text)\n type: {pct(b['type'], n)}\n place: {pct(b['place'][:7], n)}\n act: {pct(b['act'][:7], n)}")
print("\nNon-family abduction n=", out["abd_n"], "\n place:", out["abd_place"][:6], "\n act:", out["abd_act"][:6])
random.seed(4)
print("\n--- samples ---")
for label in ("Non-family abduction", "Family abduction", "Outdoors / water (lost, drowning, accident)"):
    sm = [r for r in rich if r["type"] == label]
    for r in random.sample(sm, min(4, len(sm))):
        print(f"[{label}] {r['place'][:2]} {r['act'][:2]} | {r['text'][:200]}")

with open("output/circumstances.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["person_key", "age_group", "first_name", "last_name", "age_missing", "last_contact_date",
                "last_contact_state", "how_missing", "places_mentioned", "activities_mentioned", "url"])
    for r in rows:
        p = r["p"]
        w.writerow([p["person_key"], p["age_group"], p["first_name"], p["last_name"], p["age_missing_min"],
                    p["last_contact_date"], p["last_contact_state"], r["type"],
                    "; ".join(r["place"]), "; ".join(r["act"]), p["url"]])
print("\nwrote output/circumstances.csv")
