"""Inspectie-oordelen per mbo-bestuur, de datalaag (#749).

De Inspectie publiceert elke maand een peilbestand per bevoegd gezag, met een andere bestandsnaam en een ander
document-ID. De code volgt de pagina's naar het nieuwste bg-bestand en leest het ODS-bestand met de
standaardbibliotheek. Het bestuursnummer staat als formuletekst (`="00008"`); DUO heeft het als getal.
"""

import io
import json
import zipfile

import httpx
import pytest

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from data import instellingen
from tools import fouten, inspectie
from tools.schemas import TOOL_GET_INSPECTIEOORDEEL

# De kolommen van het echte bg-bestand, in dezelfde volgorde (peilbestand 01-10-2026).
_KOP = ["Peildatum", "Bestuursnummer", "Bestuursnaam", "SectorenBijBestuur", "Eindoordeel",
        "VaststellingsdatumEindoordeel", "PublicatiedatumEindoordeel", "OnderzoeksnummerEindoordeel",
        "TypeOnderzoekCodeEindoordeel", "FinancieelBeheer", "FinancielePositie", "VaststellingsdatumFinancieel",
        "PublicatiedatumFinancieel", "OnderzoeksnummerFinancieel", "TypeOnderzoekCodeFinancieel",
        "KwaliteitszorgEnAmbitie", "VaststellingsdatumKwAmb", "PublicatiedatumKwAmb", "OnderzoeksnummerKwAmb",
        "TypeOnderzoekCodeKwAmb", "Onderwijsresultaten", "VaststellingsdatumOnderwijsres",
        "PublicatiedatumOnderwijsres", "OnderzoeksnummerOnderwijsres", "TypeOnderzoekCodeOnderwijsres", "Kader",
        "OR1", "RPO1", "RPO2", "RPO3", "KA1", "KA2", "KA3", "FB1", "FB2", "FB3", "BKA1", "BKA2", "BKA3"]  # fmt: skip


def _rij(**velden: str) -> list[str]:
    onbekend = set(velden) - set(_KOP)
    assert not onbekend, onbekend
    return [velden.get(kolom, "") for kolom in _KOP]


_RIJEN = [
    _rij(Peildatum="01-10-2026", Bestuursnummer='="00008"', Bestuursnaam="Rijksuniversiteit Groningen",
         SectorenBijBestuur="HO"),
    # Onderzoekskader 2021: de standaarden in BKA1-3, geen kwaliteitsgebieden.
    _rij(Peildatum="01-10-2026", Bestuursnummer='="34386"', Bestuursnaam="Stichting SOMA College",
         SectorenBijBestuur="MBO", Eindoordeel="Voldoende", VaststellingsdatumEindoordeel="20230906", Kader="BST2021",
         BKA1="Voldoende", BKA2="Goed", BKA3="Voldoende"),
    # Onderzoekskader 2017: oordelen per kwaliteitsgebied en de standaarden KA1-3 en FB1-3 eronder.
    _rij(Peildatum="01-10-2026", Bestuursnummer='="40740"', Bestuursnaam="Stichting Gemengd",
         SectorenBijBestuur="VO-MBO", Eindoordeel="Goed", VaststellingsdatumEindoordeel="20250115",
         FinancieelBeheer="Voldoende", KwaliteitszorgEnAmbitie="Goed", Kader="BST2017", KA1="Voldoende", KA2="Goed",
         KA3="Voldoende", FB1="Voldoende", FB2="Geen oordeel", FB3="Voldoende"),
    # Onderzoekskader 2021 in de versie van 2025: dezelfde standaarden.
    _rij(Peildatum="01-10-2026", Bestuursnummer='="40800"', Bestuursnaam="Stichting Versie 2025",
         SectorenBijBestuur="MBO", Eindoordeel="Onvoldoende", VaststellingsdatumEindoordeel="20260911",
         Kader="BST21_V25", BKA1="Voldoende", BKA2="Onvoldoende", BKA3="Onvoldoende"),
    _rij(Peildatum="01-10-2026", Bestuursnummer='="12345"', Bestuursnaam="Basisschoolbestuur", SectorenBijBestuur="PO",
         Eindoordeel="Voldoende", VaststellingsdatumEindoordeel="20240101", Kader="BST2021", BKA1="Voldoende"),
]  # fmt: skip


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
    assert len(rijen) == 5
    assert rijen[1]["Bestuursnummer"] == '="34386"' and rijen[1]["Eindoordeel"] == "Voldoende"
    assert rijen[0]["Eindoordeel"] == ""


@pytest.mark.parametrize(("waarde", "nummer"), [('="00008"', 8), ("00008", 8), (8, 8), (8.0, 8), ("34386.0", 34386)])
def test_het_bestuursnummer_wordt_een_getal(waarde, nummer):
    assert inspectie.bestuursnummer(waarde) == nummer


@pytest.mark.parametrize("waarde", ["", None, "abc", 8.5, True])
def test_geen_bestuursnummer_geeft_none(waarde):
    assert inspectie.bestuursnummer(waarde) is None


def _oordelen(rijen: list[dict] | None = None) -> dict[int, inspectie.Oordeel]:
    return inspectie.oordelen_mbo(inspectie.Peilbestand(_BG, "01-10-2026", rijen or inspectie.lees_ods(_ODS)))


def _met(nummer: str, **velden: str) -> list[dict]:
    """De rijen van het testbestand, met andere waarden bij één bestuur."""
    return [{**r, **velden} if r["Bestuursnummer"] == f'="{nummer}"' else r for r in inspectie.lees_ods(_ODS)]


def test_alleen_besturen_met_mbo_met_hun_oordeel_en_of_ze_gemengd_zijn():
    oordelen = _oordelen()

    assert set(oordelen) == {34386, 40740, 40800}
    soma, gemengd = oordelen[34386], oordelen[40740]
    assert (soma.eindoordeel, soma.vastgesteld, soma.gemengd) == ("Voldoende", "06-09-2023", False)
    assert gemengd.gemengd and gemengd.sectoren == ("VO", "MBO")
    assert soma.peildatum == "01-10-2026" and soma.url == _BG


def test_kader_2021_geeft_de_drie_standaarden_bka1_tot_en_met_3_met_hun_naam():
    """#874: de standaarden van het kader 2021 staan in BKA1-3; eerder kreeg zo'n bestuur `standaarden: {}`."""
    soma = _oordelen()[34386]

    assert soma.kader == "BST2021"
    assert soma.standaarden == {
        "Visie, ambities en doelen": "Voldoende",
        "Uitvoering en kwaliteitscultuur": "Goed",
        "Evaluatie, verantwoording en dialoog": "Voldoende",
    }
    assert soma.kwaliteitsgebieden == {}


def test_kader_2021_versie_2025_heeft_dezelfde_standaarden():
    versie = _oordelen()[40800]

    assert versie.kader == "BST21_V25"
    assert versie.standaarden == {
        "Visie, ambities en doelen": "Voldoende",
        "Uitvoering en kwaliteitscultuur": "Onvoldoende",
        "Evaluatie, verantwoording en dialoog": "Onvoldoende",
    }


def test_kader_2017_geeft_de_kwaliteitsgebieden_en_hun_standaarden():
    gemengd = _oordelen()[40740]

    assert gemengd.kader == "BST2017"
    assert gemengd.kwaliteitsgebieden == {"Financieel beheer": "Voldoende", "Kwaliteitszorg en ambitie": "Goed"}
    assert gemengd.standaarden == {
        "Kwaliteitszorg": "Voldoende",
        "Kwaliteitscultuur": "Goed",
        "Verantwoording en dialoog": "Voldoende",
        "Continuïteit": "Voldoende",
        "Doelmatigheid": "Geen oordeel",
        "Rechtmatigheid": "Voldoende",
    }


def test_een_kader_leest_alleen_zijn_eigen_kolommen():
    """Een kader-2021-bestuur met (onverwacht) een waarde in KA1 krijgt die niet bij zijn standaarden."""
    assert "Kwaliteitszorg" not in _oordelen(_met("34386", KA1="Goed"))[34386].standaarden


def test_zonder_kader_geen_standaarden_wel_de_kwaliteitsgebieden():
    """Een leeg Kader zijn oudere onderzoeken (voor 2021), volgens de toelichting van de Inspectie."""
    rijen = _met("34386", Kader="", BKA1="", BKA2="", BKA3="", FinancieelBeheer="Geen samenvattend oordeel")
    soma = _oordelen(rijen)[34386]

    assert (soma.kader, soma.standaarden) == (None, {})
    assert soma.kwaliteitsgebieden == {"Financieel beheer": "Geen samenvattend oordeel"}


def test_elk_kader_noemt_alleen_kolommen_die_de_app_kent():
    for code, kader in inspectie.KADERS.items():
        assert set(kader.standaarden) <= inspectie.BEKENDE_KOLOMMEN, code
    assert set(inspectie.KWALITEITSGEBIEDEN) <= inspectie.BEKENDE_KOLOMMEN
    assert set(_KOP) == inspectie.BEKENDE_KOLOMMEN  # de kop van het echte bestand van 01-10-2026


def test_een_ongeldig_bestand_is_een_melding_geen_crash():
    with pytest.raises(inspectie.InspectieOnbereikbaar, match="geen leesbaar ODS"):
        inspectie.lees_ods(b"geen zip")


# --- de pagina's volgen --------------------------------------------------------------------------------------


def test_de_code_volgt_de_paginas_naar_het_nieuwste_bg_bestand():
    bestand = inspectie.haal_peilbestand(_standaard_site())
    assert bestand.url == _BG
    assert bestand.peildatum == "01-10-2026"
    assert len(bestand.rijen) == 5


def test_een_bekend_bestand_geeft_geen_melding(caplog):
    with caplog.at_level("WARNING", logger=inspectie.logger.name):
        inspectie.haal_peilbestand(_standaard_site())
    assert "INSPECTIE_KADER_ONBEKEND" not in caplog.text


def test_een_onbekend_kader_of_een_nieuwe_kolom_wordt_gemeld_niet_stil_leeg_gelaten(caplog):
    """#874: een nieuw kader of een nieuwe kolom bij de Inspectie valt op in het log."""
    kop = [*_KOP, "BKA4"]
    rijen = [[*r, ""] for r in _RIJEN]
    rijen[1][kop.index("Kader")] = "BST2027"  # SOMA, mbo
    rijen[4][kop.index("Kader")] = "BSTPO2027"  # po-bestuur: hoort niet bij deze tool, geen melding
    site = _standaard_site(**{_BG: (200, _ods([kop, *rijen]))})

    with caplog.at_level("WARNING", logger=inspectie.logger.name):
        bestand = inspectie.haal_peilbestand(site)

    meldingen = [r.getMessage() for r in caplog.records if r.getMessage().startswith("INSPECTIE_KADER_ONBEKEND")]
    assert meldingen == ["INSPECTIE_KADER_ONBEKEND kolommen=BKA4", "INSPECTIE_KADER_ONBEKEND kader=BST2027 besturen=1"]
    soma = inspectie.oordelen_mbo(bestand)[34386]
    assert (soma.kader, soma.standaarden) == ("BST2027", {})


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


# --- de tool get_inspectieoordeel ----------------------------------------------------------------------------

_PROFIELEN = {
    "soma college": {"naam": "SOMA College", "sector": "mbo", "instellingscode": "04NZ"},
    "gemengd college": {"naam": "Gemengd College", "sector": "mbo", "instellingscode": "11AA"},
    "hu": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "los mbo": {"naam": "Los MBO", "sector": "mbo", "instellingscode": "99ZZ"},
}


@pytest.fixture
def tool(monkeypatch):
    bestand = inspectie.Peilbestand(_BG, "01-10-2026", inspectie.lees_ods(_ODS))
    monkeypatch.setattr(inspectie.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower()))
    monkeypatch.setattr(inspectie, "peilbestand", lambda: bestand)
    monkeypatch.setattr(
        inspectie, "get_adres_lookup", lambda: {"04NZ": {"bevoegd_gezag": 34386}, "11AA": {"bevoegd_gezag": 40740}}
    )
    return inspectie.get_inspectieoordeel


def test_het_oordeel_van_het_bestuur_met_peildatum_en_bron(tool):
    uit = json.loads(tool("SOMA College"))

    assert uit["instelling"] == {"naam": "SOMA College", "instellingscode": "04NZ"}
    assert uit["bestuur"] == {"naam": "Stichting SOMA College", "nummer": 34386, "sectoren": ["mbo"]}
    assert (uit["eindoordeel"], uit["vastgesteld"], uit["peildatum"]) == ("Voldoende", "06-09-2023", "01-10-2026")
    assert uit["gemengd"] is False and "noot" not in uit
    assert "per bestuur" in uit["betekenis"]
    assert uit["bron"] == {
        "naam": "Onderwijsinspectie, Oordelen per bevoegd gezag",
        "url": _BG,
        "licentie": inspectie.LICENTIE,
        "peildatum": "01-10-2026",
    }


def test_de_uitkomst_noemt_het_kader_en_dat_kaders_niet_te_vergelijken_zijn(tool):
    uit = json.loads(tool("SOMA College"))

    assert (uit["kader"]["code"], uit["kader"]["naam"]) == ("BST2021", "Onderzoekskader 2021")
    assert "Onderzoekskader 2021" in uit["kader"]["betekenis"] and "niet met elkaar" in uit["kader"]["betekenis"]
    assert uit["standaarden"]["Uitvoering en kwaliteitscultuur"] == "Goed"
    assert uit["kwaliteitsgebieden"] == {}


def test_kader_2017_in_de_uitkomst_met_kwaliteitsgebieden(tool):
    uit = json.loads(tool("Gemengd College"))

    assert uit["kader"]["naam"] == "Onderzoekskader 2017"
    assert uit["kwaliteitsgebieden"] == {"Financieel beheer": "Voldoende", "Kwaliteitszorg en ambitie": "Goed"}
    assert len(uit["standaarden"]) == 6


def test_een_onbekend_kader_in_de_uitkomst_is_een_noot_geen_gok(tool, monkeypatch):
    rijen = _met("34386", Kader="BST2027")
    monkeypatch.setattr(inspectie, "peilbestand", lambda: inspectie.Peilbestand(_BG, "01-10-2026", rijen))
    uit = json.loads(tool("SOMA College"))

    assert uit["kader"] == {"code": "BST2027", "naam": None}
    assert uit["standaarden"] == {} and "BST2027" in uit["noot"] and "kent deze app niet" in uit["noot"]


def test_zonder_kader_is_het_kaderveld_leeg_en_volgt_geen_noot(tool, monkeypatch):
    rijen = _met("34386", Kader="")
    monkeypatch.setattr(inspectie, "peilbestand", lambda: inspectie.Peilbestand(_BG, "01-10-2026", rijen))
    uit = json.loads(tool("SOMA College"))

    assert uit["kader"] is None and uit["standaarden"] == {} and "noot" not in uit


def test_een_gemengd_bestuur_krijgt_de_noot_dat_het_oordeel_het_hele_bestuur_betreft(tool):
    uit = json.loads(tool("Gemengd College"))
    assert uit["gemengd"] is True and uit["bestuur"]["sectoren"] == ["vo", "mbo"]
    assert "ook vo" in uit["noot"] and "niet alleen voor het mbo-deel" in uit["noot"]


def test_zonder_eindoordeel_een_noot_geen_gok(tool, monkeypatch):
    rijen = [{**r, "Eindoordeel": ""} if r["Bestuursnummer"] == '="34386"' else r for r in inspectie.lees_ods(_ODS)]
    monkeypatch.setattr(inspectie, "peilbestand", lambda: inspectie.Peilbestand(_BG, "01-10-2026", rijen))
    uit = json.loads(tool("SOMA College"))
    assert uit["eindoordeel"] is None and "geen eindoordeel" in uit["noot"]


@pytest.mark.parametrize(
    ("instelling", "tekst"),
    [
        ("Hogeschool Nergens", "Onbekende instelling"),
        ("HU", "NVAO"),
        ("HU", "get_accreditatie"),  # de accreditatiedatums per opleiding (#726)
        ("Los MBO", "staat geen bestuur met mbo in het peilbestand van de Inspectie van 01-10-2026"),
    ],
)
def test_zonder_oordeel_een_vaste_melding(tool, instelling, tekst):
    uit = tool(instelling)
    assert tekst in uit and not uit.startswith("{")


def test_een_onbereikbare_inspectie_is_een_gecodeerde_fout(tool, monkeypatch):
    def kapot():
        try:
            raise httpx.ConnectTimeout("te laat")
        except httpx.ConnectTimeout as e:
            raise inspectie.InspectieOnbereikbaar("de Inspectie antwoordde niet") from e

    monkeypatch.setattr(inspectie, "peilbestand", kapot)
    uit = tool("SOMA College")
    assert fouten.code(uit) == "bron_onbereikbaar" and "Onderwijsinspectie" in uit


def test_de_tool_staat_in_de_dispatch_en_de_bron_onder_het_antwoord(tool):
    uit, _ = tools.dispatch(TOOL_GET_INSPECTIEOORDEEL, {"instelling": "SOMA College"})
    stap = (TOOL_GET_INSPECTIEOORDEEL, uit)

    regel = "Onderwijsinspectie · Oordelen per bevoegd gezag, peildatum 01-10-2026"
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: _BG}
    assert TOOL_GET_INSPECTIEOORDEEL in tools.LABELS
