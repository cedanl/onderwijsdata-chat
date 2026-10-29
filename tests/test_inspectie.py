"""Inspectie-oordelen per mbo-bestuur, de datalaag (#749).

De Inspectie publiceert elke maand een peilbestand per bevoegd gezag, met een andere bestandsnaam en een ander
document-ID. De code volgt de pagina's naar het nieuwste bg-bestand en leest het ODS-bestand met de
standaardbibliotheek. Het bestuursnummer staat als formuletekst (`="00008"`); DUO heeft het als getal.
"""

import io
import zipfile

import httpx
import pytest

from data import instellingen
from tools import inspectie

_KOP = ["Peildatum", "Bestuursnummer", "Bestuursnaam", "SectorenBijBestuur", "Eindoordeel",
        "VaststellingsdatumEindoordeel", "FinancieelBeheer", "KwaliteitszorgEnAmbitie", "Onderwijsresultaten"]  # fmt: skip
_RIJEN = [
    ["01-10-2026", '="00008"', "Rijksuniversiteit Groningen", "HO", "", "", "", "", ""],
    ["01-10-2026", '="34386"', "Stichting SOMA College", "MBO", "Voldoende", "20230906", "", "", ""],
    ["01-10-2026", '="40740"', "Stichting Gemengd", "VO-MBO", "Goed", "20250115", "Goed", "Voldoende", "Goed"],
    ["01-10-2026", '="12345"', "Basisschoolbestuur", "PO", "Voldoende", "20240101", "", "", ""],
]


def _cel(waarde: str) -> str:
    return f'<table:table-cell office:value-type="string"><text:p>{waarde}</text:p></table:table-cell>'


def _ods(rijen: list[list[str]]) -> bytes:
    """Een ODS-bestand zoals LibreOffice het schrijft, met herhaalde lege cellen en rijen aan het eind."""
    regels = "".join(
        "<table:table-row>"
        + "".join(_cel(w) if w else "<table:table-cell/>" for w in rij)
        + '<table:table-cell table:number-columns-repeated="16375"/></table:table-row>'
        for rij in rijen
    )
    leeg = '<table:table-row table:number-rows-repeated="1048000"><table:table-cell table:number-columns-repeated="16384"/></table:table-row>'
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        f'<office:body><office:spreadsheet><table:table table:name="Sheet_1">{regels}{leeg}</table:table>'
        "</office:spreadsheet></office:body></office:document-content>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", xml)
    return buffer.getvalue()


_ODS = _ods([_KOP, *_RIJEN])
_JAAR = "/trends-en-ontwikkelingen/onderwijsdata/oordelen/oordelen-{}-{}"
_BG = "https://www.onderwijsinspectie.nl/site/binaries/documents/2026/10/02/x/20261001-oordeel-en-standaard-bg.ods"


def _site(paginas: dict[str, tuple[int, bytes | str]]) -> httpx.Client:
    def antwoord(verzoek: httpx.Request) -> httpx.Response:
        status, inhoud = paginas.get(str(verzoek.url), (404, ""))
        return httpx.Response(status, content=inhoud if isinstance(inhoud, bytes) else inhoud.encode())

    return httpx.Client(transport=httpx.MockTransport(antwoord))


def _standaard_site(**anders) -> httpx.Client:
    b = inspectie.BASIS
    paginas = {
        inspectie.OVERZICHT: (
            200,
            f'<a href="{_JAAR.format(2025, 2026)}">25</a><a href="{_JAAR.format(2026, 2027)}">26</a>',
        ),
        # Het nieuwe schooljaar heeft nog geen document: dan het vorige.
        b + _JAAR.format(2026, 2027): (200, "<p>Nog geen oordelen.</p>"),
        b + _JAAR.format(2025, 2026): (
            200,
            '<a href="/documenten/2026/09/01/oordelen-1-september-2026">sep</a>'
            '<a href="/documenten/2026/10/02/oordelen-1-oktober-2026">okt</a>',
        ),
        b + "/documenten/2026/10/02/oordelen-1-oktober-2026": (
            200,
            f'<a href="{_BG}">bg</a><a href="https://x/20261001-oordeel-en-standaard-po-so-vo.ods">po</a>',
        ),
        _BG: (200, _ODS),
    }
    return _site({**paginas, **anders})


# --- lezen en normaliseren ----------------------------------------------------------------------------------


def test_het_ods_bestand_wordt_gelezen_zonder_odf_engine():
    rijen = inspectie.lees_ods(_ODS)
    assert len(rijen) == 4
    assert rijen[1]["Bestuursnummer"] == '="34386"' and rijen[1]["Eindoordeel"] == "Voldoende"
    assert rijen[0]["Eindoordeel"] == ""


@pytest.mark.parametrize(("waarde", "nummer"), [('="00008"', 8), ("00008", 8), (8, 8), (8.0, 8), ("34386.0", 34386)])
def test_het_bestuursnummer_wordt_een_getal(waarde, nummer):
    assert inspectie.bestuursnummer(waarde) == nummer


@pytest.mark.parametrize("waarde", ["", None, "abc", 8.5, True])
def test_geen_bestuursnummer_geeft_none(waarde):
    assert inspectie.bestuursnummer(waarde) is None


def test_alleen_besturen_met_mbo_met_hun_oordeel_en_of_ze_gemengd_zijn():
    bestand = inspectie.Peilbestand(_BG, "01-10-2026", inspectie.lees_ods(_ODS))
    oordelen = inspectie.oordelen_mbo(bestand)

    assert set(oordelen) == {34386, 40740}
    soma, gemengd = oordelen[34386], oordelen[40740]
    assert (soma.eindoordeel, soma.vastgesteld, soma.gemengd, soma.standaarden) == (
        "Voldoende",
        "06-09-2023",
        False,
        {},
    )
    assert gemengd.gemengd and gemengd.sectoren == ("VO", "MBO")
    assert gemengd.standaarden == {
        "Financieel beheer": "Goed",
        "Kwaliteitszorg en ambitie": "Voldoende",
        "Onderwijsresultaten": "Goed",
    }
    assert soma.peildatum == "01-10-2026" and soma.url == _BG


def test_een_ongeldig_bestand_is_een_melding_geen_crash():
    with pytest.raises(inspectie.InspectieOnbereikbaar, match="geen leesbaar ODS"):
        inspectie.lees_ods(b"geen zip")


# --- de pagina's volgen --------------------------------------------------------------------------------------


def test_de_code_volgt_de_paginas_naar_het_nieuwste_bg_bestand():
    bestand = inspectie.haal_peilbestand(_standaard_site())
    assert bestand.url == _BG
    assert bestand.peildatum == "01-10-2026"
    assert len(bestand.rijen) == 4


def test_zonder_bg_bestand_of_bij_een_fout_van_de_site_een_melding():
    zonder = {inspectie.BASIS + "/documenten/2026/10/02/oordelen-1-oktober-2026": (200, "<p>leeg</p>"),
              inspectie.BASIS + "/documenten/2026/09/01/oordelen-1-september-2026": (200, "<p>leeg</p>")}  # fmt: skip
    with pytest.raises(inspectie.InspectieOnbereikbaar, match="geen bg-bestand"):
        inspectie.haal_peilbestand(_standaard_site(**zonder))
    with pytest.raises(inspectie.InspectieOnbereikbaar, match="antwoordde niet"):
        inspectie.haal_peilbestand(_standaard_site(**{inspectie.OVERZICHT: (503, "")}))


# --- de koppeling met een instelling -------------------------------------------------------------------------


def test_een_instelling_vindt_het_oordeel_van_haar_bestuur(monkeypatch):
    monkeypatch.setattr(inspectie, "get_adres_lookup", lambda: {"04NZ": {"bevoegd_gezag": 34386}, "99ZZ": {}})
    bestand = inspectie.Peilbestand(_BG, "01-10-2026", inspectie.lees_ods(_ODS))

    oordeel = inspectie.oordeel_voor_instelling("04NZ", bestand)
    assert oordeel is not None and oordeel.bestuursnaam == "Stichting SOMA College"
    assert inspectie.oordeel_voor_instelling("99ZZ", bestand) is None
    assert inspectie.oordeel_voor_instelling("ONBEKEND", bestand) is None


def test_het_adres_van_een_instelling_kent_haar_bestuur():
    adres = instellingen._adres({"PROVINCIE": "Utrecht", "BEVOEGD GEZAG NUMMER": 34386.0, "PLAATSNAAM": "Zeist"})
    assert adres["bevoegd_gezag"] == 34386
    assert instellingen._adres({"BEVOEGD GEZAG NUMMER": float("nan")})["bevoegd_gezag"] is None
