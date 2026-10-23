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
    ("This project’s analysis of sources [1] and [2] (and [8], [9]): collect.py (weekly collection), "
     "circumstances.py (classification), insights.py (insights, children and young adults separately), "
     "models/stock_flow_ncic.py (national model), output/*.csv, report/insights.json.",
     None, f"Latest collection {F['collected']}."),
    ("U.S. Census Bureau, Population Estimates Program, Vintage 2024. State population estimates by single "
     "year of age and sex (file SC-EST2024-AGESEX-CIV, civilian population) and by age, sex, race and Hispanic "
     "origin (file SC-EST2024-ALLDATA6), 2024 estimates.",
     "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/state/asrh/", "Accessed October 22, 2026."),
    ("FBI Criminal Justice Information Services. NCIC Missing Person and Unidentified Person Statistics, yearly "
     "editions 2015–2020 and 2022–2025 (2021 not found online). Juvenile entries and active records "
     "compiled in models/ncic_juvenile_by_year.csv.",
     "https://www.fbi.gov/file-repository/2025-ncic-missing-person-and-unidentified-person-statistics.pdf/view",
     "Accessed October 22, 2026."),
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
style_run(fp.add_run("Missing Children in the United States  |  Page "), 8, color=GREY)
fld = _el("w:fldSimple", **{"w:instr": "PAGE"})
fr = OxmlElement("w:r")
fr.append(_el("w:t"))
fr[-1].text = "1"
fld.append(fr)
fp._p.append(fld)

zoom = doc.settings.element.find(qn("w:zoom"))
if zoom is not None:
    zoom.set(qn("w:percent"), "100")
doc.core_properties.title = "Missing Children in the United States"
doc.core_properties.author = "Missing persons research project"

# --------------------------------------------------------------------------- content
# Children (under 18) first; young adults (18-25) in their own part. Never pooled.

SF = json.loads((HERE.parent / "models/stock_flow_results.json").read_text("utf-8"))
FC, FA = F["child"], F["adult"]
IC, IA = INS["child"], INS["adult"]
FIG = [0]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def tl(t):
    return TYPE_LABEL.get(t, t)


def x(v):
    return f"{v:.1f}x"


def p1(v):
    return f"{100 * v:.1f}%"


def pf(v):
    return f"{round(100 * v)}%"


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


def type_table(G, label="Share"):
    table(["How they went missing", "Cases", label], [[tl(k), fmt(v), pct(v, G["n"])] for k, v in G["type"]],
          [5160, 2000, 2200], numeric=(1, 2))


def band_tables(G, b):
    B = G["bands"][b]
    for key, head in (("type", "How they went missing"), ("place", "Places mentioned"), ("act", "Activities mentioned")):
        rows = [[tl(k) if key == "type" else k, fmt(v), pct(v, B["n"])] for k, v in B[key]]
        table([head, "Cases", "Share"], rows, [5160, 2000, 2200], numeric=(1, 2))
        spacer()
    note(f"{fmt(B['any'])} of {fmt(B['n'])} cases in this group ({pct(B['any'], B['n'])}) mention any place or "
         "activity. Shares are out of all cases in the group.", (7,))


def state_table(I, ages):
    rates, split = I["state_rates"], I["state_source_split"]
    show = rates[:8] + rates[-5:]
    table(["State", f"Open cases since {INS['recent_from']}", f"Per 100,000 aged {ages}", "From NamUs / NCMEC"],
          [[s, fmt(c), f"{r:.1f}", f"{split.get(s, {}).get('namus', 0)} / {split.get(s, {}).get('ncmec', 0)}"]
           for s, c, _, r in show], [2700, 2200, 2400, 2060], numeric=(1, 2))


def nm(i):
    return [("link", f"NamUs MP{i}", f"https://www.namus.gov/MissingPersons/Case#/{i}")]


def nc(pre, i):
    return [("link", f"NCMEC {pre}-{i}", f"https://www.missingkids.org/poster/{pre}/{i}/1")]


def examples(rows):
    table(["Case", "Age, year, state", "What the record says", "Category"], [[c, a, w, t] for c, a, w, t in rows],
          [1750, 1500, 4410, 1700])
    note("Summaries paraphrase the official record as of the collection date. Records can change as "
         "investigations go on.", (1, 2))


tc, ta = dict(FC["type"]), dict(FA["type"])
rc, ra = {r[0]: r for r in IC["race"]}, {r[0]: r for r in IA["race"]}
fam_young = dict(FC["bands"]["0-11"]["type"]).get("Family abduction", 0)
yo, yoa = IC["years_open_by_type"], IA["years_open_by_type"]
slow = SF["fits"]["1"]
slow_c = slow["params"]["compartments"][0]
slow_shares = list(slow["slow_share_of_active"].values())
bt = SF["backtest"]

# Title block
p = doc.add_paragraph()
style_run(p.add_run("Missing Children in the United States"), 20, bold=True, color=NAVY)
spacing(p, after=4, line=1.0)
p = doc.add_paragraph()
style_run(p.add_run("How they went missing, where they were and what they were doing, from public case records. "
                    "Young adults (18–25) are reported separately in Part 2."), 13, color=GREY)
spacing(p, after=8, line=1.1)
p = doc.add_paragraph()
style_run(p.add_run(f"Open NamUs and NCMEC cases on {F['collected']}: {fmt(FC['n'])} children and "
                    f"{fmt(FA['n'])} young adults"), 10, color=GREY)
pbdr = _el("w:pBdr")
pbdr.append(_el("w:bottom", **{"w:val": "single", "w:sz": 8, "w:space": 6, "w:color": NAVY}))
p._p.get_or_add_pPr().append(pbdr)
spacing(p, after=14)

callout("How to read this report", [
    [("b", "Children and young adults are never pooled. "),
     "Every figure in Part 1 uses only children: people under 18 for their whole recorded age range. Young "
     "adults (18–25) are in Part 2 with their own figures, compared with the population of the same age. "
     f"{F['unknown_age']} records with no age, or an age range that straddles 18, are in neither part.",
     ("cite", [7])],
    [("b", "Open cases only. "),
     f"Counts are cases still listed on {F['collected']}. Since weekly collection began on {F['first_run']}, "
     f"{fmt(F['delisted_so_far'])} cases have dropped off the listings (found) and are not counted here.",
     ("cite", [1, 2, 7])],
])
spacer()

# Key findings (children)
h1("Key findings about children")
nfc = tc.get("Non-family abduction", 0)
bullet([("b", "Kidnapping by a stranger or other non-family member is rare. "),
        f"It appears in {fmt(nfc)} of {fmt(FC['n'])} open child cases ({pct(nfc, FC['n'])}). National figures "
        "agree: NCMEC reports non-family abductions are about 1% of its cases, and FBI records coded "
        "“abducted by stranger” were 0.1% in 2023.", ("cite", [7, 6, 3])])
bullet([("b", "Most missing teenagers left on their own. "),
        "Over 90% of children reported to NCMEC in 2024 were endangered runaways, and 95.2% of 2023 FBI entries "
        "that recorded a reason were coded as runaways. Most come home quickly, so few remain among open cases.",
        ("cite", [5, 3])])
bullet([("b", "When the record says how a young child went missing, it is usually a parent who took them. "),
        f"Among children 11 and under, {pct(fam_young, FC['bands']['0-11']['n'])} of cases describe a parent or "
        "relative taking the child.", ("cite", [7])])
bullet([("b", "Black, Hispanic and American Indian / Alaska Native children are over-represented. "),
        f"Compared with their share of Americans aged 0 to 17, they appear in open child cases since "
        f"{INS['recent_from']} at {x(rc['Black'][4])}, {x(rc['Hispanic'][4])} and "
        f"{x(rc['American Indian / Alaska Native'][4])} their population share.", ("cite", [7, 8])])
bullet([("b", "The cases that stay open are the serious ones. "),
        f"Open child runaway cases are typically {yo['Runaway / left voluntarily'][0]:.0f} years old; open "
        f"non-family abductions and suspected homicides of children, {yo['Non-family abduction'][0]:.0f} and "
        f"{yo['Possible foul play / homicide'][0]:.0f} years.", ("cite", [7])])
bullet([("b", "Nationally, about 1% of juvenile records make up about half of all active ones. "),
        f"A stock-and-flow model of FBI figures for 2015–2025 finds about {pf(slow_c['share_of_entries'])} of "
        f"juvenile records clear with a half-life of about {slow_c['half_life_years']:.0f} years, while the rest "
        "close within weeks.", ("cite", [9, 7])])
bullet([("b", "Most records say very little. "),
        f"{pct(tc.get('Not stated', 0), FC['n'])} of child cases don’t say how the child went missing, and "
        f"{pct(FC['any_detail'], FC['n'])} mention any place or activity.", ("cite", [7])])

# Data
h1("Where the data comes from")
para(["Every case comes from one of two official public databases, collected weekly. National context comes "
      "from the FBI’s yearly NCIC statistics and NCMEC reports; population figures from the Census Bureau.",
      ("cite", [1, 2, 9, 8])])
table(["Source", "What it covers", "Link"], [
    ["NamUs (U.S. Dept. of Justice)", f"Missing people of all ages; filtered to age 25 or under ({fmt(F['namus_cases'])} cases)",
     [("link", "namus.gov", SOURCES[0][1])]],
    ["NCMEC (missingkids.org)", "Missing children, mostly under 18", [("link", "missingkids.org", SOURCES[1][1])]],
], [2600, 4960, 1800])
spacer()
table(["Group", "Open cases", "Rule"], [
    ["Children", fmt(FC["n"]), "Under 18 for the whole recorded age range"],
    ["Young adults", fmt(FA["n"]), "18–25"],
    ["Age unknown", fmt(F["unknown_age"]), "No age, or age range straddles 18 (in neither part)"],
], [2600, 1800, 4960], numeric=(1,))
note(f"NCMEC’s search also returns {F['ncmec_unidentified_removed']} posters for unidentified deceased children; "
     "they are excluded because they are not missing-person cases.", (2, 7))

# ===================================================================== PART 1: CHILDREN
h1("Part 1: Children (under 18)")
h2("How children went missing")
para(["Each case’s written account was checked for words that point to how the child went missing, such as "
      "“ran away”, “abducted by her father” or “drowned”. Where NCMEC assigned an official case type, that "
      "label was used instead.", ("cite", [7])])
type_table(FC)
note(f"Share of all {fmt(FC['n'])} open child cases.", (7,))
if FC["ncmec_label"]:
    para(["NCMEC’s own case types for the children it lists show the same pattern:", ("cite", [2])])
    table(["NCMEC case type", "Cases"], [[NCMEC_LABEL.get(k, k), fmt(v)] for k, v in FC["ncmec_label"]],
          [6360, 3000], numeric=(1,))
    spacer()
callout("National context: all reports, not just open cases", [
    [("b", "FBI, 2023: "),
     "563,389 missing-person records were entered into NCIC and 563,644 removed, mostly because the person was "
     "located or came home. Where a reason was recorded, 95.2% were runaways, 0.9% abduction by a non-custodial "
     "parent and 0.1% abduction by a stranger.", ("cite", [3])],
    [("b", "NCMEC, 2024: "),
     "NCMEC assisted with 29,568 missing-child cases and helped bring 91% of the children home; more than 27,000 "
     "were endangered runaways.", ("cite", [4, 5])],
])
spacer()

for b, title, text in (
    ("0-11", "Children 11 and under",
     "The biggest identifiable group is children taken by a parent or relative, often with a custody or "
     "kidnapping warrant and a note that they “may have traveled to” another state or country. Where a setting "
     "is given, it is most often the home, then parks, water and streets; the most common activity is playing outside."),
    ("12-17", "Teens 12 to 17",
     "The typical record describes a teenager who left home, often at night or after an argument, or who left a "
     "group home or foster placement. Common settings are home, streets and school. Abduction of any kind is rare."),
):
    h2(f"{title} ({fmt(FC['bands'][b]['n'])} cases)")
    para([text, ("cite", [7])])
    band_tables(FC, b)

NFc = FC["nf"]
h2("A closer look at non-family abductions of children")
para([f"{fmt(NFc['n'])} open child cases describe an abduction by someone outside the family; {NFc['pre1990']} "
      "date from before 1990.", ("cite", [7])])
if NFc["place"]:
    table(["Places mentioned in these cases", "Cases"], [[k, fmt(v)] for k, v in NFc["place"]], [6360, 3000],
          numeric=(1,))
    spacer()
para(["NCMEC’s research on abductions and attempts matches this: attempts happen most often on the street while "
      "children are playing, walking or riding bikes, and are more common going to or from school.", ("cite", [6])])

# Insights about children
h1("Insights about children")
para([f"Each insight uses only the {fmt(IC['n_all'])} open child cases and, for comparisons, the Census "
      "population aged 0 to 17.", ("cite", [7, 8])])
s_all, s_out = IC["season"]["All cases"]["shares"], IC["season"]["Lost, drowned or accident outdoors"]["shares"]
pk, lo = max(range(12), key=s_all.__getitem__), min(range(12), key=s_all.__getitem__)
fsh, fs = IC["female_share"], IC["female_share_by_type"]
dig = {d[0]: d for d in IC["digital"]}
src = IC["source_recent_share"]
rbs = IC["race_by_source"]
mig, hisp_n = IC["hispanic_migration_related"]
split = IC["state_source_split"]

h2("1. The mid-teens are the peak, and girls outnumber boys in the teen years")
ages_tot = {a: f + m for a, f, m in IC["age_sex"]}
para([f"Age {IC['peak_age']} is the most common age at disappearance ({fmt(ages_tot[IC['peak_age']])} open cases); "
      f"ages {IC['top3_ages'][0]} to {IC['top3_ages'][-1]} account for {pf(IC['top3_ages_share'])} of open child cases. "
      f"Under 12, boys and girls are about equal ({pf(fsh['0-11'])} female); among teens, girls are the majority "
      f"({pf(fsh['12-17'])} female).", ("cite", [7])])
figure("age_sex_child", "Open child cases by age at disappearance and sex.", [1, 2, 7])

h2("2. Who goes missing depends on the situation")
out_f, out_n = fs["Outdoors / water (lost, drowning, accident)"]
para([f"In outdoor and water cases, {pct(out_n - out_f, out_n)} of the children are boys. Possible foul play "
      f"leans female ({pct(*fs['Possible foul play / homicide'])}).", ("cite", [7])])
figure("female_share_child", "Share of child cases who are girls, by how they went missing (categories with 10 or more cases).", [7])

h2("3. Black, Hispanic and American Indian / Alaska Native children are over-represented")
para([f"Among open child cases since {INS['recent_from']} with race or ethnicity recorded ({fmt(IC['race_known'])}), "
      f"{p1(rc['Black'][2])} are Black children, who are {p1(rc['Black'][3])} of Americans aged 0 to 17: "
      f"{x(rc['Black'][4])} their population share. The ratio is {x(rc['Hispanic'][4])} for Hispanic and "
      f"{x(rc['American Indian / Alaska Native'][4])} for American Indian and Alaska Native children; White "
      f"({x(rc['White'][4])}) and Asian ({x(rc['Asian'][4])}) children are under-represented.", ("cite", [7, 8])])
para([f"The pattern holds in each database (Black children: {pf(rbs['namus']['Black'])} of NamUs and "
      f"{pf(rbs['ncmec']['Black'])} of NCMEC cases) and is not explained by migration: {fmt(mig)} of "
      f"{fmt(hisp_n)} Hispanic child cases ({pct(mig, hisp_n)}) mention a border crossing, migrants or "
      "unaccompanied minors. This shows who is in the open-case listings, not who is most likely to go missing; "
      "differences in how quickly cases are resolved, reported and publicized could all play a part.", ("cite", [7])])
figure("race_child", f"Share of open child cases since {INS['recent_from']} (known race/ethnicity) and of U.S. "
       "population aged 0 to 17 (2024). Hispanic is any race; other groups are non-Hispanic.", [1, 2, 7, 8])

h2("4. Runaway cases close quickly; abductions and suspected homicides stay open for decades")
para([f"Among open child cases, the typical runaway went missing {yo['Runaway / left voluntarily'][0]:.1f} years "
      f"ago; a family abduction {yo['Family abduction'][0]:.0f} years, an outdoor or water case "
      f"{yo['Outdoors / water (lost, drowning, accident)'][0]:.0f}, a non-family abduction "
      f"{yo['Non-family abduction'][0]:.0f} and possible foul play {yo['Possible foul play / homicide'][0]:.0f}. "
      f"{pf(src['ncmec'][1])} of NCMEC’s open child posters are under a year old; the median NamUs child case is "
      f"{src['namus'][0]:.0f} years old.", ("cite", [7, 4])])
figure("years_open_child", "Median years since last seen, open child cases, by how they went missing.", [7])

h2("5. Disappearances rise in late spring and summer")
para([f"{MONTHS[pk]} has the most child disappearances ({p1(s_all[pk])}) and {MONTHS[lo]} the fewest "
      f"({p1(s_all[lo])}). Cases from the last 12 months and dates recorded as January 1 are left out.", ("cite", [7])])
figure("season_child", "Share of child cases by month of disappearance; the dashed line is an even spread (8.3%).", [7])

h2("6. When a parent takes a child, it is often across a border")
para([f"{fmt(IC['fam_abroad'])} of {fmt(IC['fam_n'])} family abductions ({pct(IC['fam_abroad'], IC['fam_n'])}) "
      f"name a foreign country. Mexico is named most often ({fmt(IC['fam_countries'][0][1])} cases), followed by "
      + ", ".join(f"{c} ({v})" for c, v in IC["fam_countries"][1:4]) + ".", ("cite", [7])])
figure("countries_child", "Countries named in family-abduction records (a case can name more than one).", [1, 2, 7])

h2("7. Phones and social media now show up in the records")
recent_d = pct(dig["2010-2019"][1] + dig["2020-2026"][1], dig["2010-2019"][2] + dig["2020-2026"][2])
para([f"Before 2000, {p1(dig['Before 2000'][1] / max(1, dig['Before 2000'][2]))} of child case accounts mention a "
      f"phone, texts, social media or online activity; since 2010, {recent_d}. When they appear, they often place "
      "the child somewhere after the last sighting.", ("cite", [7])])
figure("digital_child", "Share of child case accounts (more than one line) mentioning a phone, texts, social media or "
       "online activity, by year last seen.", [7])

h2("8. State rates mostly reflect reporting practices")
para([f"Since {INS['recent_from']}, the national rate is {IC['national_rate']:.1f} open child cases per 100,000 "
      "children, but states differ widely. The highest rates come from states that post many cases to one "
      f"database: Virginia’s are mostly NCMEC posters ({split['Virginia'].get('ncmec', 0)} of "
      f"{sum(split['Virginia'].values())}) and Tennessee’s mostly NamUs records "
      f"({split['Tennessee'].get('namus', 0)} of {sum(split['Tennessee'].values())}). These are not risk rates.",
      ("cite", [7, 8])])
state_table(IC, "0-17")
note("Top 8 and bottom 5 states.", (7, 8))

h2("9. Nationally, a small slow group makes up half of active juvenile records")
mdo = SF["mean_days_open"]
para([f"FBI figures for 2015–2025 (2021 not published online) give the number of juvenile records entered each "
      f"year and the number still active on December 31. Juvenile records stay open {min(mdo.values()):.0f}–"
      f"{max(mdo.values()):.0f} days on average. A stock-and-flow model (the linear form of the predator-prey idea) "
      f"fits a fast group that closes in about {slow['params']['a_days']:.0f} days and a slow group of about "
      f"{p1(slow_c['share_of_entries'])} of records with a half-life of about {slow_c['half_life_years']:.1f} years. "
      f"That slow group is {pf(min(slow_shares))}–{pf(max(slow_shares))} of active juvenile records in every year.",
      ("cite", [9, 7])])
para([f"The model explains the structure but does not forecast better than simple rules: one year ahead, “same as "
      f"last year” missed by {bt['persistence']['mape_percent']:.1f}% on average and the model by "
      f"{bt['k1']['mape_percent']:.1f}%. Active juvenile records fell 13% in 2024 and 16% in 2025, faster than "
      "entries; something in how records close changed, and the yearly totals cannot say what.", ("cite", [9, 7])])
figure("ncic_stock_flow", "Active juvenile (under 18) NCIC records on December 31 (dots) and the model’s fast and "
       "slow groups (bars). *2021 entries interpolated.", [9, 7])

h2("10. Smaller patterns")
ncomp, nnc = IC["ncmec_with_companions"]
ft = IC["foster_teen"][0]
fr, frn = IC["foster_teen_runaway"]
bullet([("b", "Missing together: "), f"{fmt(ncomp)} of {fmt(nnc)} NCMEC children ({pct(ncomp, nnc)}) went missing "
        "with a sibling or another child.", ("cite", [2, 7])])
bullet([("b", "Foster care and group homes: "), f"{fmt(ft)} teen records mention foster care, a group home, a "
        f"shelter or a state placement, including {fmt(fr)} of {fmt(frn)} teen runaway cases ({pct(fr, frn)}); a "
        "minimum, since most records don’t say where the teen lived.", ("cite", [7])])

h2("Example cases: children")
para(["Short summaries of real records, identified by public case number, not name. Each links to the official "
      "record.", ("cite", [1, 2])])
examples([
    (nm(4571), "16, 1979, CA", "Walking back to her grandmother’s house after a church youth meeting. Two men later "
     "confessed to abducting her.", "Non-family abduction"),
    (nm(6704), "Infant, 1993, GA", "Taken from his hospital room.", "Non-family abduction"),
    (nm(19556), "4, 2005, CA", "Allegedly taken by her mother; a federal flight warrant was issued and she is "
     "believed to be abroad.", "Family abduction"),
    (nm(98717), "9, 2020, OR", "Taken from his home between 6 and 8 a.m.; may be with non-custodial family.",
     "Family abduction"),
    (nm(103596), "16, 2018, UT", "Packed her belongings and left home; later leads pointed to two other states.", "Ran away"),
    (nm(100826), "14, 2023, IL", "Described as a habitual runaway; social media posts later placed her on a Chicago "
     "train line.", "Ran away"),
    (nm(95886), "17, 2022, VA", "Ran away while at work.", "Ran away"),
    (nm(66559), "13, 2004, AK", "Playing in a kayak with another boy; his shoes were later found in the overturned "
     "kayak. Presumed drowned.", "Outdoors / water"),
    (nm(8746), "16, 2010, MI", "Went outside to make a phone call and never came back; two men were later charged "
     "in her death.", "Possible foul play"),
    (nc("NCMC", "1107030"), "2, 2008, MI", "Last seen at a gas station around 9 p.m.", "Not stated"),
    (nm(80827), "17, 2021, TX", "Last seen at her sister’s apartment; social media activity appeared near another "
     "city weeks later.", "Not stated"),
])

h2("Before and after the last sighting: children")
T = FC["timeline"]
btc = dict(T["between_types"])
bullet([("b", "Before: "), f"{fmt(T['before_people'])} children have an earlier event in their record "
        f"({fmt(T['prior_history'])} mention a history of running away).", ("cite", [7])])
bullet([("b", "After the last sighting: "), f"{fmt(T['between_people'])} children have later details: sightings and "
        f"“may be traveling to” leads ({fmt(btc.get('sighting_or_lead', 0))}), or a car or belongings found "
        f"({fmt(btc.get('evidence', 0))}).", ("cite", [7])])
bullet([("b", "Found: "), f"Neither database publishes outcomes; a case drops off when the child is located. Weekly "
        f"collection since {F['first_run']} has recorded {fmt(F['delisted_children'])} children found so far.",
        ("cite", [1, 2, 7])])

# ===================================================================== PART 2: YOUNG ADULTS
h1("Part 2: Young adults (18–25)")
para([f"These {fmt(FA['n'])} open cases are kept apart from the children in Part 1 and compared with the "
      "population aged 18 to 25. They are context for the children’s figures, not part of them.", ("cite", [7, 8])])
h2("How young adults went missing")
type_table(FA)
spacer()
h2("Places and activities")
band_tables(FA, "18-25")

fsa, fsta = IA["female_share"], IA["female_share_by_type"]
sa = IA["season"]["All cases"]["shares"]
pka, loa = max(range(12), key=sa.__getitem__), min(range(12), key=sa.__getitem__)
h2("Insights about young adults")
para([("b", "Mostly men. "), f"{pf(1 - IA['female_share_all'])} of open young-adult cases are men; the peak age is "
      f"{IA['peak_age']}.", ("cite", [7])])
figure("age_sex_adult", "Open young-adult cases by age at disappearance and sex.", [1, 2, 7])
oa_f, oa_n = fsta["Outdoors / water (lost, drowning, accident)"]
para([("b", "Outdoor, water and foul-play cases are a larger share than among children. "),
      f"Outdoor and water cases are {pct(ta.get('Outdoors / water (lost, drowning, accident)', 0), FA['n'])} of "
      f"young-adult cases and {pct(oa_n - oa_f, oa_n)} of them are men; possible foul play is "
      f"{pct(ta.get('Possible foul play / homicide', 0), FA['n'])}.", ("cite", [7])])
figure("female_share_adult", "Share of young-adult cases who are women, by how they went missing (10 or more cases).", [7])
para([("b", "American Indian and Alaska Native young adults are the most over-represented group in this report. "),
      f"They appear in open cases since {INS['recent_from']} at {x(ra['American Indian / Alaska Native'][4])} "
      f"their share of Americans aged 18 to 25 (children: {x(rc['American Indian / Alaska Native'][4])}). Black "
      f"({x(ra['Black'][4])}) and Hispanic ({x(ra['Hispanic'][4])}) young adults are also over-represented.",
      ("cite", [7, 8])])
figure("race_adult", f"Share of open young-adult cases since {INS['recent_from']} and of U.S. population aged 18 to 25 "
       "(2024). Hispanic is any race; other groups are non-Hispanic.", [1, 2, 7, 8])
para([("b", "Open cases are older. "), "Open young-adult runaway cases are typically "
      f"{yoa['Runaway / left voluntarily'][0]:.0f} years old (children: {yo['Runaway / left voluntarily'][0]:.1f}); "
      f"cases with no stated cause, {yoa['Not stated'][0]:.0f} years (children: {yo['Not stated'][0]:.0f}).",
      ("cite", [7])])
figure("years_open_adult", "Median years since last seen, open young-adult cases, by how they went missing.", [7])
para([("b", "Seasonality. "), f"{MONTHS[pka]} has the most young-adult disappearances ({p1(sa[pka])}) and "
      f"{MONTHS[loa]} the fewest ({p1(sa[loa])}).", ("cite", [7])])
figure("season_adult", "Share of young-adult cases by month of disappearance.", [7])
para([("b", "State rates. "), f"The national rate is {IA['national_rate']:.1f} open young-adult cases per 100,000 "
      "people aged 18 to 25 since 2016; as for children, state differences mostly reflect reporting.", ("cite", [7, 8])])
state_table(IA, "18-25")
note("Top 8 and bottom 5 states.", (7, 8))

h2("Example cases: young adults")
examples([
    (nm(8554), "21, 1984, TX", "Disappeared from her workplace in the late afternoon; last seen talking with two "
     "men outside.", "Non-family abduction"),
    (nm(124303), "25, 1998, CA", "Jumped into a river during a rafting trip and was swept away.", "Outdoors / water"),
    (nm(9439), "22, 1998, AZ", "Left home around 7 p.m.; his car was later found empty in another city.",
     "Possible foul play"),
])
TA = FA["timeline"]
para([("b", "Before and after the last sighting. "), f"{fmt(TA['before_people'])} young adults have an earlier event "
      f"in their record and {fmt(TA['between_people'])} have later details.", ("cite", [7])])

# Limitations
h1("Limitations")
for text in [
    "Children and young adults are analyzed separately; no figure pools them. Three records with no age, or an age "
    "range that straddles 18, are in neither group.",
    "Categories come from matching keywords in each case’s written account. Samples were checked by hand, but some "
    "cases will be misclassified, especially in the smaller categories.",
    f"Most records are short: {pct(tc.get('Not stated', 0), FC['n'])} of child cases don’t say how the child went "
    "missing, so the shares for known categories are minimums.",
    "Only open cases are included. Runaways who return within days are under-represented, and long-unsolved cases "
    "are over-represented compared with all missing-person reports.",
    "NamUs and NCMEC overlap only partly; children listed in both were merged only when NCMEC recorded the NamUs "
    "case number.",
    "Population comparisons set open cases since 2016 against 2024 estimates of the same ages. Case records rarely "
    "record more than one race, so “two or more races” is under-counted.",
    "The national stock-and-flow model uses ten yearly FBI totals; it identifies one slow group but does not "
    "forecast better than “same as last year”. The FBI counts juveniles as under 18, as reported.",
]:
    bullet([text])

# Method
h1("Method")
para(["Open cases were downloaded through the public data feeds behind NamUs and NCMEC search pages, weekly since "
      f"{F['first_run']}. Each person is labeled child (under 18 for the whole recorded age range), young adult "
      "(18–25) or unknown, and every analysis runs separately for children and young adults. Each case’s written "
      "account was checked against keyword lists for how the person went missing, the place and the activity; NCMEC’s "
      "official case type was used where available. Population comparisons use Census Bureau estimates for the same "
      "ages. The national model fits yearly FBI NCIC juvenile entries and active records with a fast group and a slow "
      "group, and is backtested one year ahead.", ("cite", [7, 8, 9])])

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
