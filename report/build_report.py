"""Build "Missing Children and Young Adults - Circumstances Report.docx" from report/facts.json.

Usage: python report/build_report.py
"""
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips

HERE = Path(__file__).resolve().parent
F = json.loads((HERE / "facts.json").read_text("utf-8"))
INS = json.loads((HERE / "insights.json").read_text("utf-8"))
OUT = HERE.parent / "Missing Children and Young Adults - Circumstances Report.docx"

NAVY, GREY, LINK, LIGHT, RULE = "1F3A5F", "5A6472", "1F5FA8", "E8EEF5", "B8C4D2"
W = 9360  # text width in twips (US Letter, 1" margins)


def fmt(n):
    return f"{n:,}"


def pct(n, d):
    return f"{round(100 * n / d)}%"


SOURCES = [
    ("NamUs (National Missing and Unidentified Persons System), U.S. Department of Justice, National "
     "Institute of Justice. Missing Persons search and public case records.",
     "https://www.namus.gov/MissingPersons/Search", f"Accessed {F['collected']}."),
    ("National Center for Missing & Exploited Children (NCMEC). Public missing-child poster search.",
     "https://www.missingkids.org/gethelpnow/search", f"Accessed {F['collected']}."),
    ("FBI Criminal Justice Information Services. 2023 NCIC Missing Person and Unidentified Person "
     "Statistics (published Feb. 7, 2024).",
     "https://le.fbi.gov/file-repository/2023-ncic-missing-person-and-unidentified-person-statistics.pdf", ""),
    ("NCMEC. “NCMEC Releases New Data: 2024 in Numbers.” May 8, 2025.",
     "https://www.missingkids.org/blog/2025/ncmec-releases-new-data-2024-in-numbers", ""),
    ("NCMEC. “They’re Missing Too: Why Runaway Children Need Our Help.” Nov. 6, 2025.",
     "https://www.missingkids.org/blog/2025/theyre-missing-too-why-runaway-children-need-our-help", ""),
    ("NCMEC. “Non-family Abductions & Attempts.”",
     "https://www.missingkids.org/theissues/nonfamily", f"Accessed {F['collected']}."),
    ("This project’s analysis of sources [1] and [2] (and [8] for population comparisons): collect.py "
     "(data collection), circumstances.py (classification), insights.py (insights), output/persons.csv, "
     "output/events.csv, output/circumstances.csv, report/insights.json.",
     None, f"Data collected {F['collected']}."),
    ("U.S. Census Bureau, Population Estimates Program, Vintage 2024. State population estimates by single "
     "year of age and sex (file SC-EST2024-AGESEX-CIV, civilian population) and by age, sex, race and Hispanic "
     "origin (file SC-EST2024-ALLDATA6), 2024 estimates.",
     "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/asrh/", "Accessed October 22, 2026."),
]

TYPE_LABEL = {
    "Not stated": "Not stated in the record",
    "Runaway / left voluntarily": "Ran away / left on their own",
    "Outdoors / water (lost, drowning, accident)": "Lost, drowned or accident outdoors",
    "Family abduction": "Taken by a parent or relative",
    "Possible foul play / homicide": "Possible foul play / homicide",
    "Non-family abduction": "Abducted by a non-family member",
}
NCMEC_LABEL = {
    "endangeredRunaway": "Endangered runaway", "missing": "Missing", "endangeredMissing": "Endangered missing",
    "familyAbduct": "Family abduction", "lostInjuredMissing": "Lost, injured or otherwise missing",
    "nonFamilyAbduct": "Non-family abduction", "unknown": "Unknown",
}

# --------------------------------------------------------------------------- low-level helpers

doc = Document()


def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), str(v))
    return e


def style_run(r, size=11, bold=False, italic=False, color=None, underline=False):
    r.font.name = "Arial"
    r.font.size = Pt(size)
    r.font.bold = bold or None
    r.font.italic = italic or None
    r.font.underline = underline or None
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return r


def add_link(p, text, url, size=11):
    r_id = p.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = _el("w:hyperlink", **{"r:id": r_id})
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rpr.append(_el("w:rFonts", **{"w:ascii": "Arial", "w:hAnsi": "Arial", "w:cs": "Arial"}))
    rpr.append(_el("w:color", **{"w:val": LINK}))
    rpr.append(_el("w:sz", **{"w:val": size * 2}))
    rpr.append(_el("w:u", **{"w:val": "single"}))
    r.append(rpr)
    t = _el("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    h.append(r)
    p._p.append(h)


def fill(p, parts, size=11):
    """parts: str | ("b", text) | ("i", text) | ("cite", [n..]) | ("link", text, url)."""
    for part in parts:
        if isinstance(part, str):
            style_run(p.add_run(part), size)
        elif part[0] == "b":
            style_run(p.add_run(part[1]), size, bold=True)
        elif part[0] == "cite":
            style_run(p.add_run(" [" + "], [".join(map(str, part[1])) + "]"), 9, color=GREY)
        elif part[0] == "link":
            add_link(p, part[1], part[2], size)
    return p


def spacing(p, before=0, after=7, line=1.2):
    pf = p.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), line
    return p


def para(parts, after=7):
    return spacing(fill(doc.add_paragraph(), parts), after=after)


def h1(text):
    return doc.add_heading(text, level=1)


def h2(text):
    return doc.add_heading(text, level=2)


def bullet(parts):
    p = doc.add_paragraph(style="List Bullet")
    return spacing(fill(p, parts), after=4, line=1.15)


def note(text, cites=()):
    p = doc.add_paragraph()
    style_run(p.add_run(text), 9, italic=True, color=GREY)
    if cites:
        fill(p, [("cite", list(cites))])
    return spacing(p, before=3, after=11)


def spacer():
    return spacing(doc.add_paragraph(), after=4)


TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize",
               "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook"]


def tblpr_insert(table, child):
    """Insert child into tblPr at its schema position."""
    tblpr = table._tbl.tblPr
    later = TBLPR_ORDER[TBLPR_ORDER.index(child.tag.split("}")[1]) + 1:]
    for i, existing in enumerate(tblpr):
        if existing.tag.split("}")[1] in later:
            tblpr.insert(i, child)
            return
    tblpr.append(child)


def shade(cell, color):
    cell._tc.get_or_add_tcPr().append(_el("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": color}))


def cell_borders(cell, left=None):
    b = _el("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        if side == "left" and left:
            b.append(_el("w:left", **{"w:val": "single", "w:sz": left[0], "w:color": left[1]}))
        else:
            b.append(_el(f"w:{side}", **{"w:val": "single", "w:sz": 4, "w:color": RULE}))
    cell._tc.get_or_add_tcPr().append(b)


def cell_margins(table, top=70, bottom=70, left=110, right=110):
    m = _el("w:tblCellMar")
    for side, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        m.append(_el(f"w:{side}", **{"w:w": v, "w:type": "dxa"}))
    tblpr_insert(table, m)


def fixed_layout(table, widths):
    table.autofit = False  # writes <w:tblLayout w:type="fixed"/>
    tw = table._tbl.tblPr.find(qn("w:tblW"))
    if tw is None:
        tw = _el("w:tblW")
        tblpr_insert(table, tw)
    tw.set(qn("w:w"), str(sum(widths)))
    tw.set(qn("w:type"), "dxa")
    for row in table.rows:
        for c, w in zip(row.cells, widths):
            c.width = Twips(w)


def table(headers, rows, widths, numeric=()):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    fixed_layout(t, widths)
    cell_margins(t)
    hdr = t.rows[0]
    hdr._tr.get_or_add_trPr().append(_el("w:tblHeader"))
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        cell_borders(c)  # tcBorders must precede shd
        shade(c, NAVY)
        p = c.paragraphs[0]
        style_run(p.add_run(h), 9.5, bold=True, color="FFFFFF")
        if i in numeric:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for ri, row in enumerate(rows, 1):
        tr = t.rows[ri]
        tr._tr.get_or_add_trPr().append(_el("w:cantSplit"))
        for i, val in enumerate(row):
            c = tr.cells[i]
            cell_borders(c)
            if ri % 2 == 0:
                shade(c, LIGHT)
            p = c.paragraphs[0]
            fill(p, val if isinstance(val, list) else [str(val)], size=9.5)
            if i in numeric:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return t


def callout(title, paragraphs):
    t = doc.add_table(rows=1, cols=1)
    fixed_layout(t, [W])
    cell_margins(t, 140, 100, 220, 220)
    c = t.rows[0].cells[0]
    cell_borders(c, left=(24, NAVY))
    shade(c, LIGHT)
    p = c.paragraphs[0]
    style_run(p.add_run(title), 11, bold=True, color=NAVY)
    spacing(p, after=5)
    for parts in paragraphs:
        spacing(fill(c.add_paragraph(), parts), after=6)


# --------------------------------------------------------------------------- document setup

sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Inches(1))

normal = doc.styles["Normal"]
normal.font.name, normal.font.size = "Arial", Pt(11)
for name, size, before, after in (("Heading 1", 15, 18, 7), ("Heading 2", 12, 12, 5)):
    s = doc.styles[name]
    rfonts = s.element.get_or_add_rPr().find(qn("w:rFonts"))
    if rfonts is not None:  # drop theme fonts so Arial applies
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            rfonts.attrib.pop(qn(a), None)
    s.font.name, s.font.size, s.font.bold = "Arial", Pt(size), True
    s.font.color.rgb = RGBColor.from_string(NAVY)
    s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(before), Pt(after)
    s.paragraph_format.keep_with_next = True
lb = doc.styles["List Bullet"]
lb.font.name, lb.font.size = "Arial", Pt(11)

fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(fp.add_run("Missing Children and Young Adults – Circumstances Report  |  Page "), 8, color=GREY)
fld = _el("w:fldSimple", **{"w:instr": "PAGE"})
fr = OxmlElement("w:r")
fr.append(_el("w:t"))
fr[-1].text = "1"
fld.append(fr)
fp._p.append(fld)

zoom = doc.settings.element.find(qn("w:zoom"))
if zoom is not None:
    zoom.set(qn("w:percent"), "100")
doc.core_properties.title = "Missing Children and Young Adults in the United States"
doc.core_properties.author = "Missing persons research project"

# --------------------------------------------------------------------------- content

n = F["n"]
B = F["bands"]
type_count = dict(F["type"])
nf, notstated = type_count["Non-family abduction"], type_count["Not stated"]


def tl(t):
    return TYPE_LABEL.get(t, t)


def band_rows(b, key, label=lambda k: k):
    return [[label(k), fmt(v), pct(v, B[b]["n"])] for k, v in B[b][key]]


# Title block
p = doc.add_paragraph()
style_run(p.add_run("Missing Children and Young Adults in the United States"), 20, bold=True, color=NAVY)
spacing(p, after=4, line=1.0)
p = doc.add_paragraph()
style_run(p.add_run("What public case records say about how they went missing, where they were, "
                    "and what they were doing"), 13, color=GREY)
spacing(p, after=8, line=1.1)
p = doc.add_paragraph()
style_run(p.add_run(f"Based on {fmt(n)} open cases from NamUs and NCMEC, collected {F['collected']}"), 10, color=GREY)
pbdr = _el("w:pBdr")
pbdr.append(_el("w:bottom", **{"w:val": "single", "w:sz": 8, "w:space": 6, "w:color": NAVY}))
p._p.get_or_add_pPr().append(pbdr)
spacing(p, after=14)

# Key findings
h1("Key findings")
fam_young = dict(B["0-11"]["type"])["Family abduction"]
INS_RACE0 = {r[0]: r for r in INS["race"]}
bullet([("b", "Kidnapping by a stranger or other non-family member is rare. "),
        f"It appears in {fmt(nf)} of {fmt(n)} open cases ({pct(nf, n)}). National figures agree: NCMEC "
        "reports that non-family abductions make up about 1% of its cases, and FBI records coded "
        "“abducted by stranger” were 0.1% in 2023.", ("cite", [7, 6, 3])])
bullet([("b", "Most missing teenagers left on their own. "),
        "Over 90% of children reported to NCMEC in 2024 were endangered runaways, and 95.2% of 2023 FBI "
        "entries that recorded a reason were coded as runaways. Most come home quickly, so they are "
        "under-represented in the long-term open cases studied here.", ("cite", [5, 3])])
bullet([("b", "When the record says how a young child went missing, it is usually a parent who took them. "),
        f"Among children 11 and under, {pct(fam_young, B['0-11']['n'])} of cases describe a parent or "
        "relative taking the child, usually in a custody dispute and often with the child believed to be "
        "abroad.", ("cite", [7])])
bullet([("b", "Home is the most common last known place at every age. "),
        "After home come parks, water and streets for young children; streets, walking and school for "
        "teens; and cars, roads, outdoor or water settings, workplaces and nights out for adults aged 18 "
        "to 25.", ("cite", [7])])
bullet([("b", "Most records say very little. "),
        f"{pct(notstated, n)} of cases don’t state how the person went missing, and only "
        f"{fmt(F['any_detail'])} ({pct(F['any_detail'], n)}) mention any place or activity before they "
        "disappeared.", ("cite", [7])])
bullet([("b", "Black, Hispanic and Native American young people are over-represented. "),
        "Compared with their share of Americans aged 0 to 25, they appear in open cases since 2016 at "
        f"{INS_RACE0['Black'][4]:.1f}, {INS_RACE0['Hispanic'][4]:.1f} and "
        f"{INS_RACE0['American Indian / Alaska Native'][4]:.1f} times their population share.", ("cite", [7, 8])])
bullet([("b", "The cases that stay open are the serious ones. "),
        f"Open runaway cases are typically {INS['years_open_by_type']['Runaway / left voluntarily'][0]:.0f} "
        "years old, while open non-family abductions and suspected homicides are typically "
        f"{INS['years_open_by_type']['Non-family abduction'][0]:.0f} and "
        f"{INS['years_open_by_type']['Possible foul play / homicide'][0]:.0f} years old.", ("cite", [7])])

# Data
h1("Where the data comes from")
para([f"Every case comes from one of two official public databases. All open cases were downloaded on "
      f"{F['collected']}. A case is included if the person was 25 or younger when they went missing."])
table(["Source", "What it covers", "Cases used", "Link"], [
    ["NamUs (U.S. Dept. of Justice)", "Missing people of all ages; filtered to age 25 or under at disappearance",
     fmt(F["namus_cases"]), [("link", "namus.gov", SOURCES[0][1])]],
    ["NCMEC (missingkids.org)", "Missing children, mostly under 18",
     fmt(F["ncmec_cases"] - F["ncmec_unidentified_removed"]), [("link", "missingkids.org", SOURCES[1][1])]],
    ["Combined", f"{fmt(F['both'])} children listed in both were merged", fmt(n), ""],
], [2300, 3960, 1300, 1800], numeric=(2,))
note(f"NCMEC’s search also returned {F['ncmec_unidentified_removed']} posters for unidentified deceased "
     "children. They were excluded because they are not missing-person cases.", (2, 7))
table(["Year last seen", "Cases", "Share"], [[k, fmt(v), pct(v, n)] for k, v in F["era"]],
      [4680, 2340, 2340], numeric=(1, 2))
note("These are open cases still listed in the databases. Cases that end quickly are removed, so older and "
     "harder cases make up a larger share here than in all reports.", (7,))

# How they went missing
h1("How these young people went missing")
para(["Each case’s written account was checked for words and phrases that point to how the person "
      "went missing, such as “ran away”, “abducted by her father” or “drowned”. "
      "Where NCMEC had assigned an official case type, that label was used instead.", ("cite", [7])])
table(["How they went missing", "Cases", "Share of all cases"],
      [[tl(k), fmt(v), pct(v, n)] for k, v in F["type"]], [5160, 2000, 2200], numeric=(1, 2))
note(f"Share is out of all {fmt(n)} open cases.", (7,))

h2("NCMEC’s own case labels")
para(["NCMEC gives some of its posters an official case type. The labeled cases show the same pattern:",
      ("cite", [2])])
table(["NCMEC case type", "Cases"], [[NCMEC_LABEL.get(k, k), fmt(v)] for k, v in F["ncmec_label"]],
      [6360, 3000], numeric=(1,))
spacer()
callout("National context: all reports, not just open cases", [
    [("b", "FBI, 2023: "),
     "563,389 missing-person records were entered into the national NCIC system, and 563,644 were removed, "
     "mostly because the person was located or came home. Where a reason was recorded, 95.2% were runaways, "
     "0.9% abduction by a non-custodial parent and 0.1% abduction by a stranger. At the end of 2023, 38,276 "
     "active records (39%) were people under 21.", ("cite", [3])],
    [("b", "NCMEC, 2024: "),
     "NCMEC assisted with 29,568 missing-child cases and helped bring 91% of the children home. More than "
     "27,000 of these cases were endangered runaways.", ("cite", [4, 5])],
])
spacer()

# By age
h1("Where they were and what they were doing, by age")
para(["The tables below count how often each kind of place or activity is mentioned in the written account "
      "of the disappearance. A case can mention several, or none. Percentages are out of all cases in that "
      "age group, including the many that give no details.", ("cite", [7])])
AGES = [
    ("0-11", "Children 11 and under",
     "The biggest identifiable group is children taken by a parent or relative. These records typically name "
     "the parent, mention a custody or kidnapping warrant, and say they “may have traveled to” "
     "another state or country. Where a setting is given, it is most often the home, then parks, water and "
     "streets. The most common activity is playing outside."),
    ("12-17", "Teens 12 to 17",
     "The typical record describes a teenager who left home, often at night or after an argument, or who "
     "left a group home or foster placement. Common settings are home, streets and walking, and school. "
     "Common activities are leaving home, walking somewhere, and visiting a friend, boyfriend or girlfriend. "
     "Abduction of any kind is rare in this group."),
    ("18-25", "Young adults 18 to 25",
     "Records describe ordinary adult activities: visiting friends or a partner, walking, driving, going out "
     "at night, working, hiking or swimming. Cars and roads appear far more often than for younger ages. "
     "This group has the most drownings and outdoor accidents, and the most cases of suspected foul play."),
]
for b, title, text in AGES:
    h2(f"{title} ({fmt(B[b]['n'])} cases)")
    para([text, ("cite", [7])])
    table(["How they went missing", "Cases", "Share"], band_rows(b, "type", tl), [5160, 2000, 2200], numeric=(1, 2))
    spacer()
    table(["Places mentioned", "Cases", "Share"], band_rows(b, "place"), [5160, 2000, 2200], numeric=(1, 2))
    spacer()
    table(["Activities mentioned", "Cases", "Share"], band_rows(b, "act"), [5160, 2000, 2200], numeric=(1, 2))
    note(f"{fmt(B[b]['any'])} of {fmt(B[b]['n'])} cases in this group ({pct(B[b]['any'], B[b]['n'])}) "
         "mention any place or activity.", (7,))

# Non-family abductions
h1("A closer look at non-family abductions")
NF = F["nf"]
ages_txt = ", ".join(f"{fmt(v)} aged {k}" for k, v in NF["band"])
para([f"{fmt(NF['n'])} open cases describe an abduction by someone outside the family. {NF['pre1990']} of "
      f"them date from before 1990. Most involve young children: {ages_txt}.", ("cite", [7])])
table(["Places mentioned in these cases", "Cases"], [[k, fmt(v)] for k, v in NF["place"]], [6360, 3000], numeric=(1,))
spacer()
para(["NCMEC’s research on abductions and attempts matches this pattern. Attempts happen most often on "
      "the street while children are playing, walking or riding bikes, and are more common when children "
      "are going to or from school.", ("cite", [6])])

# Insights
INS_RACE = {r[0]: r for r in INS["race"]}
FIG = [0]


def figure(name, caption, cites):
    FIG[0] += 1
    p = doc.add_paragraph()
    p.add_run().add_picture(str(HERE / "charts" / f"{name}.png"), width=Inches(6.5))
    spacing(p, before=4, after=2, line=1.0)
    p.paragraph_format.keep_with_next = True
    c = doc.add_paragraph()
    style_run(c.add_run(f"Figure {FIG[0]}. "), 9, bold=True, color=GREY)
    style_run(c.add_run(caption), 9, color=GREY)
    fill(c, [("cite", list(cites))])
    spacing(c, after=12)


def x(v):
    return f"{v:.1f}x"


def p1(v):
    return f"{100 * v:.1f}%"


def pf(v):
    return f"{round(100 * v)}%"


yo = INS["years_open_by_type"]
fs = INS["female_share_by_type"]
fsh = INS["female_share"]
sea = INS["season"]
dig = {d[0]: d for d in INS["digital"]}
src = INS["source_recent_share"]
rbs = INS["race_by_source"]
rates = INS["state_rates"]
split = INS["state_source_split"]
age_tot = {a: f + m for a, f, m in INS["age_sex"]}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
s_all = sea["All cases"]["shares"]
s_out = sea["Lost, drowned or accident outdoors"]["shares"]
pk_all, lo_all = max(range(12), key=s_all.__getitem__), min(range(12), key=s_all.__getitem__)
pk_out = sorted(range(12), key=lambda i: -s_out[i])[:2]
mig, hisp_n = INS["hispanic_migration_related"]
outdoor_f, outdoor_n = fs["Outdoors / water (lost, drowning, accident)"]
peak_more = round(100 * (s_all[pk_all] / s_all[lo_all] - 1))
dig_recent = pct(dig["2010-2019"][1] + dig["2020-2026"][1], dig["2010-2019"][2] + dig["2020-2026"][2])

h1("Insights")
para([f"These findings go beyond the category counts above. They combine the {fmt(INS['n_all'])} case records "
      "with U.S. Census population estimates. Each one says how it was measured and what it cannot show.",
      ("cite", [7, 8])])
for t in [
    [("b", "Age 16 is the peak. "), f"Mid-teens (15 to 17) make up {pf(INS['share_15_17'])} of all open cases."],
    [("b", "Sex depends on the situation. "), f"Teen cases are {pf(fsh['12-17'])} female, but outdoor and water "
     f"cases are {pct(outdoor_n - outdoor_f, outdoor_n)} male."],
    [("b", "Black, Hispanic and Native American young people are over-represented "),
     f"compared with their share of the population ({x(INS_RACE['Black'][4])}, {x(INS_RACE['Hispanic'][4])} "
     f"and {x(INS_RACE['American Indian / Alaska Native'][4])})."],
    [("b", "Runaway cases close fast; abductions and suspected homicides stay open for decades "),
     f"(median {yo['Runaway / left voluntarily'][0]:.0f} years vs. {yo['Non-family abduction'][0]:.0f} and "
     f"{yo['Possible foul play / homicide'][0]:.0f} years)."],
    [("b", "Disappearances rise in late spring and summer. "),
     f"{MONTHS[pk_all]} has about {peak_more}% more cases than {MONTHS[lo_all]}."],
    [("b", "Family abductions often cross borders. "),
     f"{pct(INS['fam_abroad'], INS['fam_n'])} name a foreign country, most often Mexico."],
    [("b", "Phones and social media now show up in the records "),
     f"of about {dig_recent} of cases since 2010, up from almost none before 2000."],
    [("b", "State-by-state rates mostly reflect reporting practices, "),
     "not where young people are at greater risk."],
]:
    bullet(t)

h2("1. The mid-teens are the peak, and girls outnumber boys in the teen years")
para([f"Age 16 is the most common age at disappearance ({fmt(age_tot[16])} open cases), and ages 15 to 17 "
      f"together account for {pf(INS['share_15_17'])} of all cases. Among children under 12, boys and girls "
      f"are about equal ({pf(fsh['0-11'])} female). Among teens, girls are the majority ({pf(fsh['12-17'])} "
      f"female). From about age 20, young men clearly outnumber young women ({pf(fsh['18-25'])} of 18- to "
      "25-year-olds are female).", ("cite", [7])])
figure("age_sex", "Open cases by age at disappearance and sex, all years.", [1, 2, 7])

h2("2. Boys and young men dominate outdoor and water cases")
para([f"In cases involving drowning, getting lost or an accident outdoors, {pct(outdoor_n - outdoor_f, outdoor_n)} "
      f"of those missing are male ({fmt(outdoor_n - outdoor_f)} of {fmt(outdoor_n)}). Cases of possible foul "
      f"play lean female ({pct(*fs['Possible foul play / homicide'])}), as do non-family abductions "
      f"({pct(*fs['Non-family abduction'])}). Runaways and family abductions are close to evenly split.",
      ("cite", [7])])
figure("female_share", "Share of cases who are female, by how they went missing (all years).", [7])

h2("3. Black, Hispanic and Native American young people are over-represented")
para([f"Among open cases since {INS['recent_from']} where race or ethnicity is recorded "
      f"({fmt(INS['race_known'])} people), {p1(INS_RACE['Black'][2])} are Black. Black young people are "
      f"{p1(INS_RACE['Black'][3])} of Americans aged 0 to 25, so their share of cases is "
      f"{x(INS_RACE['Black'][4])} their share of the population. The ratio is {x(INS_RACE['Hispanic'][4])} for "
      f"Hispanic young people and {x(INS_RACE['American Indian / Alaska Native'][4])} for American Indian and "
      f"Alaska Native young people. White ({x(INS_RACE['White'][4])}) and Asian ({x(INS_RACE['Asian'][4])}) "
      "young people are under-represented.", ("cite", [7, 8])])
para([f"The pattern appears in both databases separately: Black young people are {pf(rbs['namus']['Black'])} "
      f"of NamUs cases and {pf(rbs['ncmec']['Black'])} of NCMEC cases. It is not explained by migration: only "
      f"{fmt(mig)} of {fmt(hisp_n)} Hispanic cases ({pct(mig, hisp_n)}) mention a border crossing, migrants or "
      "unaccompanied minors. This shows who is in the open-case listings, not who is most likely to go "
      "missing. Differences in how quickly cases are resolved, reported and publicized could all play a part, "
      "and this data can't separate them.", ("cite", [7])])
figure("race", f"Share of open cases since {INS['recent_from']} (known race/ethnicity) compared with share of "
       "U.S. population aged 0 to 25 (2024 estimate). Hispanic is any race; other groups are non-Hispanic.",
       [1, 2, 7, 8])

h2("4. Runaway cases close quickly; abductions and suspected homicides stay open for decades")
para([f"Among cases that are still open, the typical runaway went missing "
      f"{yo['Runaway / left voluntarily'][0]:.1f} years ago. The typical family abduction has been open "
      f"{yo['Family abduction'][0]:.0f} years, an outdoor or water case "
      f"{yo['Outdoors / water (lost, drowning, accident)'][0]:.0f} years, a non-family abduction "
      f"{yo['Non-family abduction'][0]:.0f} years, and a case of possible foul play "
      f"{yo['Possible foul play / homicide'][0]:.0f} years. Most runaways are found, so the open runaway cases "
      "are mostly recent; the cases that stay unsolved are the more serious ones.", ("cite", [7, 4])])
para([f"The two databases capture different stages. {pf(src['ncmec'][1])} of NCMEC's open posters are less "
      f"than a year old (median {src['ncmec'][0]:.1f} years), while the median NamUs case is "
      f"{src['namus'][0]:.0f} years old.", ("cite", [7])])
figure("years_open", "Median years since last seen for open cases, by how they went missing.", [7])

h2("5. Disappearances rise in late spring and summer")
para([f"Across all cases, {MONTHS[pk_all]} has the most disappearances ({p1(s_all[pk_all])} of the year) and "
      f"{MONTHS[lo_all]} the fewest ({p1(s_all[lo_all])}), so the peak month has about {peak_more}% more. "
      f"Outdoor and water cases peak earlier, in {MONTHS[pk_out[0]]} and {MONTHS[pk_out[1]]}, which fits "
      "swimming, boating and hiking season.", ("cite", [7])])
note("Cases from the last 12 months are left out because recent open cases pile up in the current month. "
     "Dates recorded as January 1 are also left out, since that date is often a placeholder.")
figure("season", "Share of cases by month of disappearance. The dashed line marks an even spread (8.3%).", [7])

h2("6. When a parent takes a child, it is often across a border")
para([f"{fmt(INS['fam_abroad'])} of the {fmt(INS['fam_n'])} family abductions "
      f"({pct(INS['fam_abroad'], INS['fam_n'])}) name a foreign country where the child may have been taken. "
      f"Mexico is named most often ({fmt(INS['fam_countries'][0][1])} cases), followed by "
      + ", ".join(f"{c} ({v})" for c, v in INS["fam_countries"][1:4])
      + ".", ("cite", [7])])
figure("countries", "Countries named in family-abduction case records (a case can name more than one).",
       [1, 2, 7])

h2("7. Phones and social media now show up in the records")
para([f"Before 2000, only {p1(dig['Before 2000'][1] / dig['Before 2000'][2])} of written accounts mention a "
      f"phone, texts, social media or online activity. Since 2010 it is about {dig_recent}. When these details "
      "appear, they often place the person somewhere after the last sighting, for example a phone last used "
      "near a park, or social media posts from another city. Most records still don't mention them, which may "
      "reflect how "
      "briefly public summaries are written rather than what investigators know.", ("cite", [7])])
figure("digital", "Share of case accounts (more than one line long) that mention a phone, texts, social media or "
       "online activity, by year last seen.", [7])

h2("8. State-by-state rates mostly reflect reporting practices")
para([f"Since {INS['recent_from']}, the national rate is {INS['national_rate']:.1f} open cases per 100,000 "
      "people aged 0 to 25, but states range from under 1 to about 20. The highest rates come from states "
      "that post many cases to one database. Virginia's are almost all NCMEC posters "
      f"({split['Virginia'].get('ncmec', 0)} of {sum(split['Virginia'].values())}), and Tennessee's are almost "
      f"all NamUs records ({split['Tennessee'].get('namus', 0)} of {sum(split['Tennessee'].values())}). "
      "A low rate may simply mean a state enters fewer cases into these public systems, so these figures "
      "should not be read as risk.", ("cite", [7, 8])])
show = rates[:8] + rates[-5:]
table(["State", f"Open cases since {INS['recent_from']}", "Rate per 100,000 aged 0-25", "From NamUs / NCMEC"],
      [[s, fmt(c), f"{r:.1f}", f"{split.get(s, {}).get('namus', 0)} / {split.get(s, {}).get('ncmec', 0)}"]
       for s, c, _, r in show],
      [2700, 2200, 2400, 2060], numeric=(1, 2))
note("Top 8 and bottom 5 states shown. Rates use the Census Bureau's 2024 civilian population estimate for "
     "ages 0 to 25.", (7, 8))

h2("9. Smaller patterns")
ncomp, nnc = INS["ncmec_with_companions"]
ft = INS["foster_teen"][0]
fr, frn = INS["foster_teen_runaway"]
bullet([("b", "Missing together: "), f"{fmt(ncomp)} of {fmt(nnc)} NCMEC children ({pct(ncomp, nnc)}) went "
        "missing with a sibling or another child.", ("cite", [2, 7])])
bullet([("b", "Foster care and group homes: "), f"{fmt(ft)} teen records mention foster care, a group home, a "
        f"shelter or a state placement, including {fmt(fr)} of {fmt(frn)} teen runaway cases ({pct(fr, frn)}). "
        "This is a minimum, since most records don't say where the teen lived.", ("cite", [7])])
bullet([("b", "Unaccompanied minors: "), "Some recent records describe teens who crossed the border alone and "
        "later left the home of a sponsor or relative.", ("cite", [7])])

# Examples
h1("Example cases")
para(["Below are short summaries of real case records, one or more per category. Cases are identified by "
      "their public case number rather than by name. Each number links to the official record.",
      ("cite", [1, 2])])


def nm(i):
    return [("link", f"NamUs MP{i}", f"https://www.namus.gov/MissingPersons/Case#/{i}")]


def nc(pre, i):
    return [("link", f"NCMEC {pre}-{i}", f"https://www.missingkids.org/poster/{pre}/{i}/1")]


EX = [
    (nm(4571), "16, 1979, CA", "Walking back to her grandmother’s house after a church youth meeting. Two men "
     "later confessed to abducting her.", "Non-family abduction"),
    (nm(6704), "Infant, 1993, GA", "Taken from his hospital room.", "Non-family abduction"),
    (nm(8554), "21, 1984, TX", "Disappeared from her workplace in the late afternoon. Last seen talking with "
     "two men outside.", "Non-family abduction"),
    (nm(19556), "4, 2005, CA", "Allegedly taken by her mother. A federal flight warrant was issued and she "
     "is believed to be abroad.", "Family abduction"),
    (nm(98717), "9, 2020, OR", "Taken from his home between 6 and 8 a.m. May be with non-custodial family.",
     "Family abduction"),
    (nm(103596), "16, 2018, UT", "Packed her belongings and left home. Later leads pointed to two other "
     "states.", "Ran away"),
    (nm(100826), "14, 2023, IL", "Described as a habitual runaway. Her social media posts later placed her "
     "on a Chicago train line.", "Ran away"),
    (nm(95886), "17, 2022, VA", "Ran away while at work.", "Ran away"),
    (nm(66559), "13, 2004, AK", "Playing in a kayak with another boy. His shoes were later found in the "
     "overturned kayak; presumed drowned.", "Outdoors / water"),
    (nm(124303), "25, 1998, CA", "Jumped into a river during a rafting trip and was swept away.",
     "Outdoors / water"),
    (nm(9439), "22, 1998, AZ", "Left home around 7 p.m. His car was later found empty in another city.",
     "Possible foul play"),
    (nm(8746), "16, 2010, MI", "Went outside to make a phone call and never came back. Two men were later "
     "charged in her death.", "Possible foul play"),
    (nc("NCMC", "1107030"), "2, 2008, MI", "Last seen at a gas station around 9 p.m.", "Not stated"),
    (nm(80827), "17, 2021, TX", "Last seen at her sister’s apartment. Social media activity appeared "
     "near another city weeks later.", "Not stated"),
]
table(["Case", "Age, year, state", "What the record says", "Category"],
      [[c, a, w, t] for c, a, w, t in EX], [1750, 1500, 4410, 1700])
note("Summaries paraphrase the official record as of the collection date. Records can change as "
     "investigations go on.", (1, 2))

# Timeline
h1("Before and after the last sighting")
para(["Each case was also turned into a timeline. Structured fields give the last date and place seen; the "
      "written accounts give earlier and later details.", ("cite", [7])])
T = F["timeline"]
bt = dict(T["between_types"])
bullet([("b", "Last date and place seen: "),
        f"recorded for nearly every case; {fmt(F['coords'])} NamUs cases also have map coordinates.",
        ("cite", [1, 2])])
bullet([("b", "Before they went missing: "),
        f"{fmt(T['before_people'])} people have an earlier event in their record, such as a previous runaway, "
        f"a move, a trip, or a previous missing report ({fmt(T['prior_history'])} mention a history of "
        "running away).", ("cite", [7])])
bullet([("b", "After the last sighting: "),
        f"{fmt(T['between_people'])} people have later details, such as sightings, phone or social-media "
        f"activity, “may be traveling to” leads ({fmt(bt['sighting_or_lead'])}), or a car or "
        f"belongings found ({fmt(bt['evidence'])}).", ("cite", [7])])
bullet([("b", "When and where found: "),
        "Neither database publishes this. Both remove a case once the person is located, so outcomes can "
        "only be detected by collecting the data repeatedly and noting which cases disappear.",
        ("cite", [1, 2, 3])])

# Limitations
h1("Limitations")
for text in [
    "Categories come from matching keywords in each case’s written account. Samples were checked by hand, "
    "but some cases will be misclassified, especially in the smaller categories.",
    f"Most records are short. {pct(notstated, n)} don’t say how the person went missing, so the "
    "percentages for known categories are minimums, not complete counts.",
    "Only cases that were still open on the collection date are included. Runaways who return within days "
    "are under-represented, and long-unsolved cases (abductions, drownings, unexplained disappearances) are "
    "over-represented compared with all missing-person reports.",
    "NamUs and NCMEC overlap only partly. Children listed in both were merged only when NCMEC recorded the "
    "NamUs case number, so some duplicates may remain.",
    "The national figures are for different years (FBI 2023, NCMEC 2024) and count all reports, not open "
    "cases. They are included for context, not as a direct comparison.",
    "Population comparisons set open cases since 2016 against 2024 population estimates. Race categories "
    "don’t line up exactly: case records rarely record more than one race, so “two or more races” "
    "is under-counted in the cases (about 1%) compared with the population (about 4%).",
    "NamUs has a field for whether the person went missing from tribal land, but its answers are unreliable "
    "(for example, cases in Nashville marked “yes”), so it isn’t used here.",
]:
    bullet([text])

# Method
h1("Method")
para(["All open cases were downloaded through the public data feeds behind each site’s search pages: "
      "NamUs cases where the person was 25 or younger when they went missing, and all NCMEC child posters. "
      "Each case’s written account was split into sentences and checked against keyword lists for how "
      "the person went missing (e.g. “ran away”, “non-custodial”, “abducted”, "
      "“drowned”), the place (home, school, street, vehicle, workplace and so on) and the activity "
      "(walking, leaving home, visiting a friend and so on). NCMEC’s official case type was used where "
      "available. For the insights, ages and dates come from the structured fields, race and ethnicity "
      "from each database’s coded fields, and population figures from Census Bureau estimates. The "
      "scripts and the per-person results are in the project folder.", ("cite", [7, 8])])

# Sources
h1("Sources")
for i, (text, url, extra) in enumerate(SOURCES, 1):
    p = doc.add_paragraph()
    parts = [("b", f"[{i}] "), text + " "]
    if url:
        parts += [("link", url, url), " "]
    if extra:
        parts.append(extra)
    fill(p, parts, size=10)
    spacing(p, after=6, line=1.15)
    p.paragraph_format.left_indent = Twips(440)
    p.paragraph_format.first_line_indent = Twips(-440)
spacer()
p = doc.add_paragraph()
style_run(p.add_run("If you have information about a missing child, contact the agency listed on the case "
                    "record or NCMEC at 1-800-THE-LOST (1-800-843-5678)."), 10, italic=True, color=GREY)

doc.save(OUT)
print("wrote", OUT)
