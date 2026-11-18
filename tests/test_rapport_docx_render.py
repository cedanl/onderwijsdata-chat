"""Het rapport als Word-document (#1038): het sjabloon, de inhoud en de grafieken, teruggelezen met python-docx."""

import zipfile
from io import BytesIO

import pytest
from docx import Document
from docx.oxml.ns import qn
from docxtpl import DocxTemplate

from tests.rapport_docx_hulp import RAPPORT_HTML, png
from tools.rapport_docx import render as render_module
from tools.rapport_docx.afbeeldingen import (
    MAX_AANTAL,
    MAX_BYTES,
    AfbeeldingFout,
    Grafiek,
    grafiek,
    lees_grafieken,
)
from tools.rapport_docx.render import SJABLOON, context, omgeving, render_docx
from tools.rapport_docx.uit_html import rapport_uit_html

KOPPEN = [
    "Afwijking van je vraag",
    "Onderzoeksvraag",
    "Reikwijdte",
    "Gekozen definities",
    "Visualisaties",
    "Conclusie",
    "Bronnen",
    "Herkomst",
]


def _document(html: str = RAPPORT_HTML, grafieken: dict | None = None):
    data = render_docx(rapport_uit_html(html), grafieken if grafieken is not None else {0: grafiek(png())})
    return Document(BytesIO(data)), data


def _alineas(doc) -> list[tuple[str, str]]:
    return [(p.style.name, p.text) for p in doc.paragraphs]


def _tekst(doc) -> str:
    return "\n".join(p.text for p in doc.paragraphs)


# ── Inhoud ────────────────────────────────────────────────────────────────────────────────────────────────────────


def test_alle_secties_in_de_volgorde_van_het_rapport():
    doc, _ = _document()
    koppen = [t for s, t in _alineas(doc) if s == "Heading 2"]
    assert koppen == KOPPEN
    assert _alineas(doc)[0] == ("Title", "Instroom hbo in Utrecht {{ 7*7 }}")


def test_meta_instelling_en_datum_onder_de_titel():
    doc, _ = _document()
    assert _alineas(doc)[1] == (
        "Rapport meta",
        "Gegenereerd op 30 oktober 2026 · Opgesteld door jansen met openEDUdata+ (AI-assistent)"
        " · Instelling: Hogeschool Utrecht",
    )


def test_reikwijdte_definities_bronnen_en_herkomst():
    alineas = _alineas(_document()[0])
    assert ("Heading 3", "Wat dit rapport wel beantwoordt") in alineas
    assert ("Heading 3", "Wat dit rapport niet beantwoordt") in alineas
    assert ("Normal", "Instroom: Eerstejaars in het hoger onderwijs.") in alineas
    i = alineas.index(("Normal", "Peildatum"))
    assert alineas[i + 1 : i + 3] == [
        ("List Bullet", "Telling op 1 oktober."),
        ("List Bullet", "Voorlopige cijfers kunnen wijzigen."),
    ]
    assert [t for s, t in alineas if s == "List Number"] == ["CBS StatLine 85353NED", "DUO Ingeschrevenen"]
    assert [t for s, t in alineas if s == "Herkomst"] == [
        "Verantwoording: model gpt-4.1 · prompt abc123 · app 2.8.0",
        "Dataversie: CBS 85353NED (bijgewerkt 2026-10-01)",
    ]


def test_per_visualisatie_titel_grafiek_noot_bron_en_toelichting():
    doc, _ = _document()
    alineas = _alineas(doc)
    i = alineas.index(("Heading 3", "Instroom per jaar"))
    assert alineas[i + 1 : i + 5] == [
        ("Grafiek", ""),
        ("Grafiekregel", "Afgerond op tientallen."),
        ("Grafiekregel", "Bron: CBS, Hoger onderwijs (85353NED), 2023 · Bekijk de bron bij CBS"),
        ("Toelichting", "De instroom steeg licht."),
    ]
    assert len(doc.inline_shapes) == 1
    # Zonder grafiek zegt het document dat; de bron zonder http(s)-adres blijft tekst.
    j = alineas.index(("Heading 3", "Instroom naar sector"))
    assert alineas[j + 1 : j + 3] == [
        ("Geen grafiek", "Grafiek niet beschikbaar"),
        ("Grafiekregel", "Bron: DUO, Ingeschrevenen"),
    ]


def test_alleen_de_bronlink_is_een_link():
    doc, data = _document()
    links = [r for r in doc.part.rels.values() if r.reltype.endswith("/hyperlink")]
    assert [r.target_ref for r in links] == ["https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85353NED"]
    assert b"javascript:" not in zipfile.ZipFile(BytesIO(data)).read("word/document.xml")


def test_grafieken_staan_in_de_volgorde_van_het_rapport():
    breed, hoog = grafiek(png(8, 2)), grafiek(png(2, 8))
    doc, _ = _document(grafieken={0: breed, 2: hoog})
    vormen = doc.inline_shapes
    assert len(vormen) == 2
    assert vormen[0].width > vormen[0].height
    assert vormen[1].height > vormen[1].width
    alineas = _alineas(doc)
    assert alineas[alineas.index(("Heading 3", "Visualisatie 3")) + 1] == ("Grafiek", "")


def test_een_hoge_grafiek_past_op_de_pagina():
    (vorm,) = _document(grafieken={0: grafiek(png(10, 100))})[0].inline_shapes
    assert round(vorm.height.mm) == render_module.BEELD_HOOGTE_MAX_MM
    assert vorm.width.mm < render_module.BEELD_BREEDTE_MM


def test_conclusie_met_koppen_vet_punten_en_een_echte_tabel():
    doc, _ = _document()
    alineas = _alineas(doc)
    i = alineas.index(("Heading 2", "Conclusie"))
    assert alineas[i + 1 : i + 5] == [
        ("Heading 3", "Kern"),
        ("Normal", "De instroom is stabiel {{ geheim }}."),
        ("List Bullet", "2023: 475.460"),
        ("List Bullet", "2024: 476.000"),
    ]
    vet = [r.text for r in doc.paragraphs[i + 2].runs if r.bold]
    assert vet == ["stabiel"]
    (tabel,) = doc.tables
    assert [[c.text for c in rij.cells] for rij in tabel.rows] == [
        ["Jaar", "Instroom"],
        ["2023", "475.460"],
        ["2024", "476.000"],
    ]
    assert all(r.bold for c in tabel.rows[0].cells for r in c.paragraphs[0].runs if r.text)
    assert [r.text for r in tabel.rows[1].cells[1].paragraphs[0].runs if r.bold] == ["475.460"]
    assert "| Jaar |" not in _tekst(doc)


def test_een_lege_sectie_staat_niet_in_het_document():
    html = '<div class="header"><h1>Kort</h1></div><div class="vraag"><div class="vraag-text">Alleen dit?</div></div>'
    doc, _ = _document(html, {})
    assert _alineas(doc) == [("Title", "Kort"), ("Heading 2", "Onderzoeksvraag"), ("Onderzoeksvraag", "Alleen dit?")]
    assert doc.tables == []


# ── Onvertrouwde tekst ────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tekst",
    [
        "{{ 7*7 }}",
        "{% for x in range(3) %}x{% endfor %}",
        "{_{ titel }_}",
        "{_% if %_}",
        "<w:p>&amp;</w:p> & <script>",
        "\"quotes\" 'en' {#commentaar#}",
    ],
)
def test_tekst_uit_het_rapport_staat_er_letterlijk(tekst):
    from html import escape

    html = f'<div class="header"><h1>{escape(tekst)}</h1></div><div class="vraag"><div class="vraag-text">{escape(tekst)}</div></div>'
    doc, _ = _document(html, {})
    assert _alineas(doc)[0] == ("Title", tekst)
    assert _alineas(doc)[2] == ("Onderzoeksvraag", tekst)


def test_tekens_die_xml_niet_toestaat_gaan_eruit():
    """docxtpl maakt van \\a een nieuwe alinea en van \\f een nieuwe pagina; ze mogen niets doen."""
    doc, _ = _document()
    vraag = next(t for s, t in _alineas(doc) if s == "Onderzoeksvraag")
    assert vraag == "Hoeveel studenten stromen in? {% if true %}ja{% endif %} <script>alert(1)</script> & meer"
    assert len([s for s, _ in _alineas(doc) if s == "Onderzoeksvraag"]) == 1
    html = '<div class="vraag"><div class="vraag-text">a&#1;b\x07c\x0cd</div></div>'
    assert rapport_uit_html(html).onderzoeksvraag == "a\x01b\x07c d"
    assert _alineas(_document(html, {})[0])[1:] == [("Heading 2", "Onderzoeksvraag"), ("Onderzoeksvraag", "abc d")]


# ── Het sjabloon (criterium 7) ────────────────────────────────────────────────────────────────────────────────────


def test_het_sjabloon_is_een_geldig_docx():
    with zipfile.ZipFile(SJABLOON) as z:
        assert z.testzip() is None
        assert {"word/document.xml", "word/styles.xml", "word/fontTable.xml", "[Content_Types].xml"} <= set(
            z.namelist()
        )
    Document(str(SJABLOON))


def test_het_sjabloon_plaatst_elk_contextveld():
    """Elk veld van de context staat in het sjabloon (StrictUndefined faalt op een veld dat ontbreekt), en een
    herkenbare waarde per tekstveld komt in het document."""
    tpl = DocxTemplate(SJABLOON)
    gebruikt = tpl.get_undeclared_template_variables(omgeving())
    ctx = context(tpl, rapport_uit_html(RAPPORT_HTML), {})
    assert gebruikt == set(ctx)


def test_npuls_huisstijl():
    doc = Document(str(SJABLOON))
    for naam, kleur in (("Title", "DD784B"), ("Heading 2", "DD784B"), ("Heading 3", "000000"), ("Normal", "000000")):
        stijl = doc.styles[naam]
        assert str(stijl.font.color.rgb) == kleur, naam
        assert stijl.element.rPr.rFonts.get(qn("w:ascii")) == "General Sans", naam
    # Oranje alleen voor grote tekst (3:1 op wit): 18 pt en groter.
    assert doc.styles["Heading 2"].font.size.pt >= 18
    assert str(doc.styles["Hyperlink"].font.color.rgb) == "3D68EC"
    fonts = zipfile.ZipFile(SJABLOON).read("word/fontTable.xml").decode()
    assert '<w:font w:name="General Sans"><w:altName w:val="Inter"/>' in fonts
    kop = doc.sections[0].header
    assert "openEDUdata+" in kop.paragraphs[0].text
    assert kop.part.rels and any(r.reltype.endswith("/image") for r in kop.part.rels.values())
    voet = zipfile.ZipFile(SJABLOON).read("word/footer1.xml").decode()
    assert 'w:instr="PAGE"' in voet and 'w:instr="NUMPAGES"' in voet


def test_het_resultaat_is_een_geldig_docx_met_titel_in_de_eigenschappen():
    doc, data = _document()
    assert zipfile.ZipFile(BytesIO(data)).testzip() is None
    assert doc.core_properties.title == "Instroom hbo in Utrecht {{ 7*7 }}"


def test_een_lange_titel_staat_heel_in_het_document_en_ingekort_in_de_eigenschappen():
    titel = "Hoeveel studenten stromen in " + "x" * 300
    doc, data = _document(RAPPORT_HTML.replace("Instroom hbo in Utrecht {{ 7*7 }}</h1>", f"{titel}</h1>"))
    assert zipfile.ZipFile(BytesIO(data)).testzip() is None
    assert _alineas(doc)[0] == ("Title", titel)
    assert doc.core_properties.title == titel[: render_module.MAX_EIGENSCHAP]


# ── Grafieken uit het verzoek ─────────────────────────────────────────────────────────────────────────────────────


def _multipart(*delen: tuple[str, bytes], grens: str = "grens123") -> tuple[str, bytes]:
    lichaam = b""
    for naam, data in delen:
        lichaam += (
            (
                f'--{grens}\r\nContent-Disposition: form-data; name="{naam}"; filename="{naam}.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
            + data
            + b"\r\n"
        )
    return f"multipart/form-data; boundary={grens}", lichaam + f"--{grens}--\r\n".encode()


def test_grafieken_per_plek():
    soort, lichaam = _multipart(("grafiek-0", png()), ("grafiek-2", png(6, 2)))
    grafieken = lees_grafieken(soort, lichaam, 3)
    assert set(grafieken) == {0, 2}
    assert grafieken[2] == Grafiek(png=png(6, 2), breedte_px=6, hoogte_px=2)
    assert lees_grafieken(None, b"", 3) == {}


@pytest.mark.parametrize(
    ("delen", "status"),
    [
        ((("grafiek-0", b"GIF89a" + b"\x00" * 20),), 400),  # geen PNG
        ((("grafiek-0", b"\x89PNG\r\n\x1a\n" + b"\x00" * 30),), 400),  # handtekening zonder geldige kop
        ((("grafiek-3", png()),), 400),  # er zijn maar drie visualisaties
        ((("grafiek-0", png()), ("grafiek-0", png())), 400),  # dubbel
        ((("titel", png()),), 400),  # alleen grafieken
        ((("grafiek-0", png(extra=MAX_BYTES)),), 413),  # te groot
    ],
)
def test_ongeldige_grafieken_worden_geweigerd(delen, status):
    soort, lichaam = _multipart(*delen)
    with pytest.raises(AfbeeldingFout) as fout:
        lees_grafieken(soort, lichaam, 3)
    assert fout.value.status == status


def test_te_veel_grafieken():
    soort, lichaam = _multipart(*((f"grafiek-{i}", png()) for i in range(MAX_AANTAL + 1)))
    with pytest.raises(AfbeeldingFout) as fout:
        lees_grafieken(soort, lichaam, MAX_AANTAL + 5)
    assert fout.value.status == 400


@pytest.mark.parametrize(
    ("soort", "lichaam"),
    [("application/json", b'{"titel": "x"}'), ("multipart/form-data; boundary=x", b"geen multipart")],
)
def test_geen_geldig_formulier(soort, lichaam):
    with pytest.raises(AfbeeldingFout) as fout:
        lees_grafieken(soort, lichaam, 3)
    assert fout.value.status == 400
