"""Bouwt templates/rapport.docx, het Word-sjabloon van "Download als Word" (#1038), in Npuls-huisstijl.

Draai vanuit de repo-root: `env UV_PYTHON=3.14 uv run python scripts/maak_rapportsjabloon.py`. Het resultaat wordt
gecommit; tools/rapport_docx/render.py vult het met docxtpl. Het sjabloon mag ook in Word worden bijgewerkt (besluit
18-11): laat dan de Jinja-codes ({{ … }}, {%p … %}, {%tr … %}, {%tc … %}) staan, elk in één stuk tekst.

Huisstijl (npuls-huisstijl, gelijk aan de PDF van #1037): oranje #DD784B alleen voor grote tekst (titel 24 pt, sectiekop
18 pt: op wit 3:1), zwarte tekst, roze #F4D9DC als zacht vlak met zwarte tekst, blauw #3D68EC voor links op wit.
Letter General Sans (600 voor koppen); het fontbestand zit niet in het document. De lettertabel noemt Inter als
alternatief (altName) en de familie "swiss", zodat Word of LibreOffice zonder General Sans een schreefloze letter
(Inter, anders Arial) kiest. Logo: het Npuls-beeldmerk (templates/npuls-logo.png, uit npuls-logo.svg) met de naam
openEDUdata+ in de kop; paginanummers in de voet.

Het bestand is reproduceerbaar: vaste datums in de eigenschappen en vaste tijden in het zip-archief.
"""

import sys
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.oxml import serialize_part_xml
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
DOEL = ROOT / "templates" / "rapport.docx"
LOGO = ROOT / "templates" / "npuls-logo.png"

ORANJE = "DD784B"
ZWART = "000000"
ROZE = "F4D9DC"
BLAUW = "3D68EC"
LETTER = "General Sans"
TERUGVAL = "Inter"
PRODUCT = "openEDUdata+"
VASTE_DATUM = datetime(2026, 11, 18, tzinfo=UTC)
GEEN_GRAFIEK = "Grafiek niet beschikbaar"


# ── Stijlen ────────────────────────────────────────────────────────────────────────────────────────────────────────


def _letter(rpr) -> None:
    """Zet de letter vast op General Sans, zonder themaletter (die wint anders van de naam)."""
    fonts = rpr.get_or_add_rFonts()
    for attr in list(fonts.attrib):
        del fonts.attrib[attr]
    for soort in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(soort), LETTER)


# Word leest een document met elementen buiten de volgorde van het schema als beschadigd: wat dit script zelf in een
# w:pPr zet, komt vóór het eerste element dat er volgens het schema na hoort (ECMA-376, CT_PPrBase).
_NA_SHD = (
    "tabs",
    "suppressAutoHyphens",
    "kinsoku",
    "wordWrap",
    "overflowPunct",
    "topLinePunct",
    "autoSpaceDE",
    "autoSpaceDN",
    "bidi",
    "adjustRightInd",
    "snapToGrid",
    "spacing",
    "ind",
    "contextualSpacing",
    "mirrorIndents",
    "suppressOverlap",
    "jc",
    "textDirection",
    "textAlignment",
    "textboxTightWrap",
    "outlineLvl",
    "divId",
    "cnfStyle",
    "rPr",
    "sectPr",
    "pPrChange",
)
_NA_PBDR = ("shd", *_NA_SHD)


def _in_volgorde(ouder, element, na: tuple[str, ...]) -> None:
    ouder.insert_element_before(element, *(f"w:{tag}" for tag in na))


def _vlak(ppr, hex_kleur: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_kleur)
    _in_volgorde(ppr, shd, _NA_SHD)


def _lijn_onder(ppr, hex_kleur: str, dikte: int = 12) -> None:
    for oud in ppr.findall(qn("w:pBdr")):
        ppr.remove(oud)
    rand = OxmlElement("w:pBdr")
    onder = OxmlElement("w:bottom")
    for attr, waarde in (("w:val", "single"), ("w:sz", str(dikte)), ("w:space", "4"), ("w:color", hex_kleur)):
        onder.set(qn(attr), waarde)
    rand.append(onder)
    _in_volgorde(ppr, rand, _NA_PBDR)


def _standaard(doc) -> None:
    """De standaardletter van het document: General Sans, Nederlands (spellingcontrole)."""
    rpr = doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
    _letter(rpr)
    for oud in rpr.findall(qn("w:lang")):
        rpr.remove(oud)
    taal = OxmlElement("w:lang")
    taal.set(qn("w:val"), "nl-NL")
    _in_volgorde(rpr, taal, ("eastAsianLayout", "specVanish", "oMath"))


def _alineastijl(
    doc,
    naam: str,
    *,
    basis: str = "Normal",
    grootte: float = 10.5,
    vet: bool = False,
    kleur: str = ZWART,
    cursief: bool = False,
    na: float = 6,
    voor: float = 0,
):
    styles = doc.styles
    stijl = styles[naam] if naam in [s.name for s in styles] else styles.add_style(naam, WD_STYLE_TYPE.PARAGRAPH)
    if naam != "Normal":
        stijl.base_style = styles[basis]
    stijl.font.size = Pt(grootte)
    stijl.font.bold = vet
    stijl.font.italic = cursief
    stijl.font.color.rgb = RGBColor.from_string(kleur)
    _letter(stijl.element.get_or_add_rPr())
    stijl.paragraph_format.space_after = Pt(na)
    stijl.paragraph_format.space_before = Pt(voor)
    return stijl


def _stijlen(doc) -> None:
    _standaard(doc)
    normaal = _alineastijl(doc, "Normal")
    normaal.paragraph_format.line_spacing = 1.15
    titel = _alineastijl(doc, "Title", grootte=24, vet=True, kleur=ORANJE, na=4)
    _lijn_onder(titel.element.get_or_add_pPr(), ORANJE)
    for kop, grootte, kleur, voor in (
        ("Heading 1", 20, ORANJE, 18),
        ("Heading 2", 18, ORANJE, 16),
        ("Heading 3", 13, ZWART, 10),
    ):
        stijl = _alineastijl(doc, kop, grootte=grootte, vet=True, kleur=kleur, voor=voor, na=4)
        stijl.paragraph_format.keep_with_next = True
    _alineastijl(doc, "Rapport meta", grootte=9, na=12)
    vraag = _alineastijl(doc, "Onderzoeksvraag", grootte=12, vet=True, na=10)
    _vlak(vraag.element.get_or_add_pPr(), ROZE)
    _alineastijl(doc, "Grafiekregel", grootte=9, na=4)
    toelichting = _alineastijl(doc, "Toelichting", na=12)
    _vlak(toelichting.element.get_or_add_pPr(), ROZE)
    grafiek = _alineastijl(doc, "Grafiek", na=4)
    grafiek.paragraph_format.keep_with_next = True
    _alineastijl(doc, "Geen grafiek", cursief=True, na=4)
    _alineastijl(doc, "Herkomst", grootte=8, na=2)
    for lijst in ("List Bullet", "List Number"):
        _letter(doc.styles[lijst].element.get_or_add_rPr())
    if "Hyperlink" not in [s.name for s in doc.styles]:
        link = doc.styles.add_style("Hyperlink", WD_STYLE_TYPE.CHARACTER)
        link.font.underline = True
        link.font.color.rgb = RGBColor.from_string(BLAUW)


def _lettertabel(doc) -> None:
    """General Sans met Inter als alternatief, en Inter met Arial; beide schreefloos (familie swiss)."""
    deel = next(p for p in doc.part.package.parts if p.partname == "/word/fontTable.xml")
    tabel = parse_xml(deel.blob)
    for naam, alternatief in ((LETTER, TERUGVAL), (TERUGVAL, "Arial")):
        font = OxmlElement("w:font", attrs={qn("w:name"): naam})
        for tag, waarde in (("w:altName", alternatief), ("w:family", "swiss"), ("w:pitch", "variable")):
            font.append(OxmlElement(tag, attrs={qn("w:val"): waarde}))
        tabel.append(font)
    deel._blob = serialize_part_xml(tabel)


# ── Pagina, kop en voet ────────────────────────────────────────────────────────────────────────────────────────────


def _veld(alinea, code: str) -> None:
    veld = OxmlElement("w:fldSimple")
    veld.set(qn("w:instr"), code)
    run = OxmlElement("w:r")
    tekst = OxmlElement("w:t")
    tekst.text = "1"
    run.append(tekst)
    veld.append(run)
    alinea._p.append(veld)


def _pagina(doc) -> None:
    sectie = doc.sections[0]
    sectie.orientation = WD_ORIENT.PORTRAIT
    sectie.page_width, sectie.page_height = Cm(21), Cm(29.7)
    sectie.left_margin = sectie.right_margin = Cm(2.2)
    sectie.top_margin, sectie.bottom_margin = Cm(2.5), Cm(2)
    sectie.header_distance, sectie.footer_distance = Cm(1.1), Cm(1)

    kop = sectie.header.paragraphs[0]
    kop.add_run().add_picture(str(LOGO), height=Cm(0.8))
    naam = kop.add_run(f"  {PRODUCT}")
    naam.bold = True
    naam.font.size = Pt(11)
    _lijn_onder(kop._p.get_or_add_pPr(), ORANJE, dikte=8)

    voet = sectie.footer.paragraphs[0]
    voet.alignment = WD_ALIGN_PARAGRAPH.CENTER
    voet.add_run(f"{PRODUCT} · Gebaseerd op open onderwijsdata · Pagina ").font.size = Pt(8)
    _veld(voet, "PAGE")
    voet.add_run(" van ").font.size = Pt(8)
    _veld(voet, "NUMPAGES")


# ── De inhoud met de Jinja-codes ───────────────────────────────────────────────────────────────────────────────────


def _codes(doc, *regels: str | tuple[str, str]) -> None:
    """Eén alinea per regel; een tuple is (tekst, stijl). Een {%p …%}-regel verdwijnt bij het renderen."""
    for regel in regels:
        tekst, stijl = regel if isinstance(regel, tuple) else (regel, "Normal")
        doc.add_paragraph(tekst, style=stijl)


def _lijst(doc, kop: str, veld: str, stijl: str = "List Bullet", kopstijl: str = "Heading 2") -> None:
    _codes(
        doc,
        f"{{%p if {veld} %}}",
        (kop, kopstijl),
        f"{{%p for regel in {veld} %}}",
        ("{{ regel }}", stijl),
        "{%p endfor %}",
        "{%p endif %}",
    )


def _definities(doc) -> None:
    _codes(doc, "{%p if definities %}", ("Gekozen definities", "Heading 2"), "{%p for d in definities %}")
    alinea = doc.add_paragraph(style="Normal")
    alinea.add_run("{{ d.begrip }}").bold = True
    alinea.add_run("{{ d.na_begrip }}")
    _codes(
        doc,
        "{%p for deel in d.delen %}",
        ("{{ deel }}", "List Bullet"),
        "{%p endfor %}",
        "{%p endfor %}",
        "{%p endif %}",
    )


def _visualisaties(doc) -> None:
    _codes(
        doc,
        "{%p if visualisaties %}",
        ("Visualisaties", "Heading 2"),
        "{%p for v in visualisaties %}",
        ("{{ v.titel }}", "Heading 3"),
        "{%p if v.afbeelding %}",
        ("{{ v.afbeelding }}", "Grafiek"),
        "{%p else %}",
        (GEEN_GRAFIEK, "Geen grafiek"),
        "{%p endif %}",
        "{%p if v.noot %}",
        ("{{ v.noot }}", "Grafiekregel"),
        "{%p endif %}",
        "{%p if v.bron %}",
        ("{{r v.bron }}", "Grafiekregel"),
        "{%p endif %}",
        "{%p if v.toelichting %}",
        ("{{ v.toelichting }}", "Toelichting"),
        "{%p endif %}",
        "{%p endfor %}",
        "{%p endif %}",
    )


def _cel_vlak(cel, hex_kleur: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_kleur)
    _in_volgorde(
        cel._tc.get_or_add_tcPr(), shd, ("noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark")
    )


def _tabel(doc) -> None:
    """Een pipetabel uit de conclusie: een kopregel (roze, herhaald op elke pagina) en de rijen, met elk aantal
    kolommen ({%tc for %}; docxtpl past het raster daarna aan)."""
    tabel = doc.add_table(rows=4, cols=3)
    tabel.style = doc.styles["Table Grid"]
    rijen = tabel.rows
    for rij, bron in ((rijen[0], "blok.kop"), (rijen[2], "rij")):
        rij.cells[0].text = f"{{%tc for cel in {bron} %}}"
        rij.cells[1].paragraphs[0].add_run("{{r cel }}")
        rij.cells[2].text = "{%tc endfor %}"
    _cel_vlak(rijen[0].cells[1], ROZE)
    kopregel = rijen[0]._tr.get_or_add_trPr()
    kopregel.append(OxmlElement("w:tblHeader"))
    rijen[1].cells[0].text = "{%tr for rij in blok.rijen %}"
    rijen[3].cells[0].text = "{%tr endfor %}"
    # De volle breedte van de tekstkolom, verdeeld over de kolommen die er na het renderen zijn: geen vaste celbreedte.
    for tcw in tabel._tbl.iter(qn("w:tcW")):
        tcw.getparent().remove(tcw)
    tblw = tabel._tbl.tblPr.find(qn("w:tblW"))
    tblw.set(qn("w:type"), "pct")
    tblw.set(qn("w:w"), "5000")


def _conclusie(doc) -> None:
    _codes(
        doc,
        "{%p if conclusie %}",
        ("Conclusie", "Heading 2"),
        "{%p for blok in conclusie %}",
        "{%p if blok.soort == 'kop' %}",
        ("{{r blok.runs }}", "Heading 3"),
        "{%p elif blok.soort == 'punt' %}",
        ("{{r blok.runs }}", "List Bullet"),
        "{%p elif blok.soort == 'tabel' %}",
    )
    _tabel(doc)
    _codes(doc, "", "{%p else %}", "{{r blok.runs }}", "{%p endif %}", "{%p endfor %}", "{%p endif %}")


def _inhoud(doc) -> None:
    _codes(doc, ("{{ titel }}", "Title"), "{%p if metaregel %}", ("{{ metaregel }}", "Rapport meta"), "{%p endif %}")
    _lijst(doc, "Afwijking van je vraag", "afwijkingen")
    _codes(
        doc,
        "{%p if onderzoeksvraag %}",
        ("Onderzoeksvraag", "Heading 2"),
        ("{{ onderzoeksvraag }}", "Onderzoeksvraag"),
        "{%p endif %}",
    )
    _codes(doc, "{%p if beantwoordt or beantwoordt_niet %}", ("Reikwijdte", "Heading 2"))
    _lijst(doc, "Wat dit rapport wel beantwoordt", "beantwoordt", kopstijl="Heading 3")
    _lijst(doc, "Wat dit rapport niet beantwoordt", "beantwoordt_niet", kopstijl="Heading 3")
    _codes(doc, "{%p endif %}")
    _definities(doc)
    _visualisaties(doc)
    _conclusie(doc)
    _lijst(doc, "Bronnen", "bronnen", stijl="List Number")
    _lijst(doc, "Herkomst", "herkomst", stijl="Herkomst")


def _eigenschappen(doc) -> None:
    eig = doc.core_properties
    eig.title = "Rapport"
    eig.author = eig.last_modified_by = PRODUCT
    eig.subject = "Rapport over open onderwijsdata"
    eig.language = "nl-NL"
    eig.comments = ""
    eig.keywords = ""
    eig.revision = 1
    eig.created = eig.modified = VASTE_DATUM
    eig.last_printed = VASTE_DATUM


def _vaste_tijden(docx: bytes) -> bytes:
    """Hetzelfde zip-archief met vaste tijden: zo geeft het script elke keer hetzelfde bestand."""
    uit = BytesIO()
    with zipfile.ZipFile(BytesIO(docx)) as bron, zipfile.ZipFile(uit, "w", zipfile.ZIP_DEFLATED) as doel:
        for info in bron.infolist():
            vast = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            vast.compress_type = zipfile.ZIP_DEFLATED
            doel.writestr(vast, bron.read(info.filename))
    return uit.getvalue()


def bouw() -> bytes:
    doc = Document()
    _stijlen(doc)
    _lettertabel(doc)
    _pagina(doc)
    _inhoud(doc)
    _eigenschappen(doc)
    uit = BytesIO()
    doc.save(uit)
    return _vaste_tijden(uit.getvalue())


def main() -> int:
    DOEL.write_bytes(bouw())
    print(f"{DOEL.relative_to(ROOT)} geschreven")
    return 0


if __name__ == "__main__":
    sys.exit(main())
