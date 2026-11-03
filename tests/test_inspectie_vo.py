"""Inspectieoordelen van vo-scholen als vo-context voor vervolgonderwijs (#881, vervolg op #877).

De tool staat achter de vo-contextpoort van de beurt (`ho_markers.vo_deel_poort`): code beslist, niet het model. Po en
(v)so blijven dicht, ook als het bestand van de Inspectie die rijen heeft, en een losse vraag over één vo-school krijgt
het vaste vo-antwoord. De echte bestanden staan in de gouden test (`tests/test_gouden_inspectie_vo.py`).
"""

import json
import logging
from contextlib import nullcontext

import httpx
import pytest

import tools
from agent.bronvermelding import bronlinks_van, bronnen_van
from agent.po_vraag import po_vraag
from agent.vaste_antwoorden import VO_ANTWOORD
from agent.vo_school import vo_schoolvraag
from core.config import TOOL_RESULT_MAX_CHARS
from tests.test_inspectie import _JAAR, _ods, _site
from tests.test_scopevraag import _REGISTER
from tools import fouten, inspectie, inspectie_vo, scopeprofiel
from tools.ho_markers import beurtvraag, vo_context_poort
from tools.inspectie_vo import Vestiging
from tools.schemas import TOOL_GET_INSPECTIEOORDEEL_VO, TOOL_SCHEMAS

# De testvraag van #881: een doorstroomvraag die het vo zelf noemt (havo/vwo) naast het hbo.
DOORSTROOMVRAAG = (
    "Hoe beoordeelt de inspectie de havo/vwo-afdelingen van de scholen waar onze eerstejaars hbo vandaan komen in "
    "Utrecht?"
)

# De kolommen van het echte po-so-vo-bestand die de tool leest (peilbestand 01-11-2026).
_KOP = ["Peildatum", "Sector", "OVT", "OVTNaam", "Elementtype", "KwaliteitOnderwijs", "Vaststellingsdatum",
        "Bestuursnummer", "Bestuursnaam", "TypeOVT", "BRIN", "Vestiging"]  # fmt: skip


def _rij(sector: str, brin: str, vestiging: str, naam: str, oordeel: str, element: str = "ODS", type_ovt: str = "VOS",
         vastgesteld: str = "") -> dict:  # fmt: skip
    return {"Peildatum": "01-11-2026", "Sector": sector, "OVT": f"{brin}|{vestiging}|{naam}", "OVTNaam": naam,
            "Elementtype": element, "KwaliteitOnderwijs": oordeel, "Vaststellingsdatum": vastgesteld,
            "Bestuursnummer": "41475", "Bestuursnaam": "Stichting X", "TypeOVT": type_ovt, "BRIN": brin,
            "Vestiging": vestiging}  # fmt: skip


_RIJEN = [
    _rij("VO", "14OY", "00", "HAVO", "Onvoldoende", vastgesteld="20260706"),
    _rij("VO", "14OY", "00", "VWO", "Geen eindoordeel"),
    _rij("VO", "14OY", "00", "VMBOGT", "Voldoende", vastgesteld="20240101"),
    _rij("VO", "30UB", "02", "HAVO", "Voldoende", vastgesteld="20250610"),
    _rij("VO", "30UB", "02", "VWO", "Voldoende", vastgesteld="20250610"),
    _rij("VO", "25PM", "01", "VMBOK", "Voldoende", type_ovt="ROCV", vastgesteld="20250101"),  # vo-onderdeel van een roc
    _rij("VO", "99ZZ", "00", "HAVO", "Goed"),  # een vestiging buiten de gemeente
    # Po, so en een speciale school onder vo, met een vestigingscode die DUO hier als vo-vestiging in Utrecht noemt:
    # alleen de sector en het type houden ze buiten het resultaat, niet de koppeling met DUO.
    _rij("PO", "14OY", "00", "basisschool De Toekomst", "Zeer zwak", element="CLR", type_ovt="BAS"),
    _rij("SO", "30UB", "02", "SO De Brug", "Onvoldoende", element="OKE", type_ovt="SPEC"),
    _rij("VO", "30UB", "02", "VWO", "Zeer zwak", type_ovt="SPEC"),
    _rij("VO", "14OY", "00", "OPDC Utrecht", "Voldoende", element="VST", type_ovt="OPDV"),
]
_URL = (
    "https://www.onderwijsinspectie.nl/site/binaries/documents/2026/11/03/x/20261102-oordeel-en-standaard-po-so-vo.ods"
)
_VESTIGINGEN = {
    "14OY00": Vestiging("14OY00", "Gerrit Rietveld College", "UTRECHT", "UTRECHT"),
    "30UB02": Vestiging("30UB02", "School aan de Singel (HV)", "UTRECHT", "UTRECHT"),
    "25PM01": Vestiging("25PM01", "ROC Vavo-vmbo", "UTRECHT", "UTRECHT"),
    "99ZZ00": Vestiging("99ZZ00", "Haags Lyceum", "S GRAVENHAGE", "S GRAVENHAGE"),
}
_GEEN_VO = ("basisschool De Toekomst", "SO De Brug", "Zeer zwak", "OPDC Utrecht")


@pytest.fixture
def bronnen(monkeypatch):
    """Het po-so-vo-bestand en DUO's vo-vestigingen, zonder netwerk; faalt als de tool ze laadt bij een dichte poort."""
    geladen: list[str] = []

    def peilbestand():
        geladen.append("inspectie")
        return inspectie.Peilbestand(_URL, "01-11-2026", [dict(r) for r in _RIJEN])

    def vestigingen():
        geladen.append("duo")
        return _VESTIGINGEN

    monkeypatch.setattr(inspectie_vo, "peilbestand", peilbestand)
    monkeypatch.setattr(inspectie_vo, "vestigingen", vestigingen)
    return geladen


def _tool(vraag: str | None, **args) -> str:
    with beurtvraag(vraag) if vraag is not None else nullcontext():
        uit, _ = tools.dispatch(TOOL_GET_INSPECTIEOORDEEL_VO, {"gemeente": "Utrecht", **args})
    return uit


def _json(tekst: str) -> dict:
    uit = json.loads(tekst)
    assert isinstance(uit, dict), tekst
    return uit


# --- de poort: code beslist, op de vraag van de gebruiker ------------------------------------------------------------


@pytest.mark.parametrize(
    "vraag",
    [
        DOORSTROOMVRAAG,
        "Hoeveel havisten en vwo'ers in Utrecht stromen door naar het hbo, en hoe beoordeelt de inspectie hun scholen?",
        "Hoe beoordeelt de inspectie de vmbo-scholen waarvan de leerlingen doorstromen naar het mbo in Utrecht?",
    ],
)
def test_een_doorstroomvraag_die_het_vo_noemt_opent_de_tool(bronnen, vraag):
    uit = _json(_tool(vraag))
    assert uit["gemeente"] == "Utrecht" and uit["context"] == inspectie_vo.ETIKET
    assert bronnen == ["inspectie", "duo"]


@pytest.mark.parametrize(
    ("vraag", "zoekpoort"),
    [
        ("Wat is het inspectieoordeel van ROC Midden Nederland?", False),  # mbo, de lektest
        ("Hoe beoordeelt de inspectie de opleidingen van de Hogeschool Utrecht?", True),  # ho zonder vo-niveau
        ("Hoe beoordeelt de inspectie de havo-afdelingen in Utrecht?", False),  # een losse vo-vraag
        ("Hoe beoordeelt de inspectie de basisscholen waar onze vwo'ers vandaan komen die naar het hbo gaan?", True),
        ("Hoe beoordeelt de inspectie het vso in Utrecht, waar onze mbo-studenten vandaan komen?", False),
        (None, None),  # buiten de chat (MCP, evals) is er geen vraag
    ],
)
def test_zonder_doorstroomvraag_die_het_vo_noemt_een_vaste_weigering_zonder_bron(bronnen, vraag, zoekpoort):
    """De strengste poort (`vo_deel_poort`), niet de zoekpoort: die gaat open bij elke ho-vraag (zie `zoekpoort`)."""
    assert _tool(vraag) == inspectie_vo.POORT_DICHT
    assert bronnen == []  # geen bestand geladen
    if vraag is not None:
        with beurtvraag(vraag):
            assert vo_context_poort("") is zoekpoort


def test_het_model_opent_de_poort_niet_met_zijn_argumenten(bronnen):
    """Een argument dat het vo of het hbo noemt, verandert niets: alleen de vraag van de gebruiker telt."""
    uit = _tool("Wat is het inspectieoordeel van ROC Midden Nederland?", gemeente="hbo doorstroom havo Utrecht")
    assert uit == inspectie_vo.POORT_DICHT


def test_de_weigering_noemt_geen_oordeel_en_verwijst_naar_de_mbo_tool():
    assert "Noem geen oordeel" in inspectie_vo.POORT_DICHT
    assert "get_inspectieoordeel" in inspectie_vo.POORT_DICHT and "{" not in inspectie_vo.POORT_DICHT


# --- de lektest: een losse vo-schoolvraag krijgt het vaste vo-antwoord, vóór het model -------------------------------


@pytest.fixture
def register(monkeypatch):
    from agent import vo_school
    from tools import instelling

    for module in (vo_school, instelling):
        monkeypatch.setattr(module, "get_all", lambda: _REGISTER)


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is het inspectieoordeel van het Utrechts Stedelijk Gymnasium?",
        "Hoe beoordeelt de inspectie het Mendel College?",
    ],
)
def test_een_losse_vo_schoolvraag_krijgt_het_vo_antwoord_en_de_tool_niet(register, bronnen, vraag):
    assert vo_schoolvraag(vraag) == VO_ANTWOORD
    assert _tool(vraag) == inspectie_vo.POORT_DICHT and bronnen == []


def test_de_testvraag_gaat_langs_de_vaste_antwoorden_naar_het_model(register):
    """Geen vo-schoolnaam en geen losse po/so/vo-vraag: het model krijgt haar, met de poort open."""
    assert vo_schoolvraag(DOORSTROOMVRAAG) is None
    assert po_vraag(DOORSTROOMVRAAG) is None


# --- alleen vo, met het etiket ---------------------------------------------------------------------------------------


def test_geen_po_so_of_vso_rijen_in_het_resultaat(bronnen):
    tekst = _tool(DOORSTROOMVRAAG)
    uit = _json(tekst)

    for naam in _GEEN_VO:
        assert naam not in tekst
    soorten = {s for v in uit["vestigingen"] for s in v["afdelingen"]}
    assert soorten <= set(inspectie_vo.ONDERWIJSSOORTEN.values())
    assert uit["telling"] == {"vmbo-k": {"Voldoende": 1}, "vmbo-gt": {"Voldoende": 1},
                              "havo": {"Onvoldoende": 1, "Voldoende": 1},
                              "vwo": {"Voldoende": 1, "Geen eindoordeel": 1}}  # fmt: skip


def test_afdelingen_vo_laat_po_so_en_speciale_scholen_weg():
    afdelingen = inspectie_vo.afdelingen_vo(_RIJEN)
    assert len(afdelingen) == 7
    assert {a.onderwijssoort for a in afdelingen} == {"havo", "vwo", "vmbo-gt", "vmbo-k"}
    assert "Zeer zwak" not in {a.oordeel for a in afdelingen}


def test_het_etiket_staat_in_het_resultaat_de_bronregel_en_de_bronnen(bronnen):
    tekst = _tool(DOORSTROOMVRAAG, onderwijssoorten=["havo", "vwo"])
    uit = _json(tekst)
    stap = (TOOL_GET_INSPECTIEOORDEEL_VO, tekst)

    deel = scopeprofiel.VO_CONTEXT_DEEL
    assert uit["context"].startswith(deel) and "geen mbo- of ho-instellingen" in uit["context"]
    assert uit["bron"] == {
        "naam": f"Onderwijsinspectie, Oordelen per school (po/so/vo), {deel}",
        "url": _URL,
        "licentie": inspectie.LICENTIE,
        "peildatum": "01-11-2026",
    }
    regel = f"Onderwijsinspectie · Oordelen per school (po/so/vo), {deel}, peildatum 01-11-2026"
    assert bronnen_van([stap]) == [regel]
    assert bronlinks_van([stap]) == {regel: _URL}


def test_per_vestiging_het_oordeel_per_afdeling_met_de_vaststellingsdatum(bronnen):
    uit = _json(_tool(DOORSTROOMVRAAG, onderwijssoorten=["havo", "vwo"]))

    assert uit["onderwijssoorten"] == ["havo", "vwo"] and uit["vestigingen_totaal"] == 2
    assert uit["vestigingen"] == [
        {"naam": "Gerrit Rietveld College", "vestiging": "14OY00", "plaats": "Utrecht",
         "afdelingen": {"havo": "Onvoldoende (06-07-2026)", "vwo": "Geen eindoordeel"}},
        {"naam": "School aan de Singel (HV)", "vestiging": "30UB02", "plaats": "Utrecht",
         "afdelingen": {"havo": "Voldoende (10-06-2025)", "vwo": "Voldoende (10-06-2025)"}},
    ]  # fmt: skip
    assert "per onderwijssoort (afdeling)" in uit["betekenis"] and "geen onvoldoende" in uit["betekenis"]
    assert "niet waar studenten vandaan komen" in uit["noot"]


def test_een_vo_onderdeel_van_een_roc_krijgt_de_noot_dat_het_oordeel_niet_over_het_mbo_gaat(bronnen):
    """Zoals de melding bij een gemengd bestuur in get_inspectieoordeel: het oordeel gaat over het vo-deel."""
    uit = _json(_tool(DOORSTROOMVRAAG, onderwijssoorten=["vmbo-k"]))

    assert uit["vestigingen"][0]["onderdeel_van"] == "een roc"
    assert "vo-onderdeel van een roc" in uit["noot"] and "niet over het mbo" in uit["noot"]


def test_zonder_eindoordeel_een_noot_geen_gok(bronnen, monkeypatch):
    rijen = [_rij("VO", "14OY", "00", "VWO", "Geen eindoordeel")]
    monkeypatch.setattr(inspectie_vo, "peilbestand", lambda: inspectie.Peilbestand(_URL, "01-11-2026", rijen))
    assert "noem geen oordeel" in _json(_tool(DOORSTROOMVRAAG))["noot"]


# --- gemeente, onderwijssoort en afkappen ----------------------------------------------------------------------------


@pytest.mark.parametrize("gemeente", ["Den Haag", "'s-Gravenhage", "S GRAVENHAGE", "gemeente 's-Gravenhage"])
def test_de_spelling_van_de_gemeente_telt_niet(bronnen, gemeente):
    uit = _json(_tool(DOORSTROOMVRAAG, gemeente=gemeente))
    assert uit["gemeente"] == "'s-Gravenhage" and uit["vestigingen"][0]["plaats"] == "'s-Gravenhage"


def test_een_onbekende_gemeente_geeft_een_suggestie_en_geen_oordeel(bronnen):
    uit = _tool(DOORSTROOMVRAAG, gemeente="Utrect")
    assert "Bedoel je Utrecht?" in uit and "noem geen oordeel" in uit and not uit.startswith("{")


@pytest.mark.parametrize("soort", ["basisschool", "vso", "mbo"])
def test_een_onderwijssoort_buiten_het_vo_wordt_geweigerd(bronnen, soort):
    uit = _tool(DOORSTROOMVRAAG, onderwijssoorten=[soort])
    assert "Onbekende onderwijssoort" in uit and "Po en (v)so" in uit and bronnen == []


def test_een_gemeente_zonder_de_gevraagde_afdeling_is_een_melding(bronnen):
    uit = _tool(DOORSTROOMVRAAG, onderwijssoorten=["pro"])
    assert "geen vo-afdeling pro" in uit and "Noem geen oordeel" in uit


def test_veel_vestigingen_worden_afgekapt_de_telling_telt_alle(bronnen, monkeypatch):
    """Een grote gemeente (Amsterdam: 91 vestigingen) blijft onder TOOL_RESULT_MAX_CHARS, ook met lange namen."""
    soorten = list(inspectie_vo.ONDERWIJSSOORTEN)
    rijen = [
        _rij("VO", f"{i:02d}AA", "00", soort, "Voldoende", vastgesteld="20250101")
        for i in range(91)
        for soort in soorten
    ]
    vestigingen = {f"{i:02d}AA00": Vestiging(f"{i:02d}AA00", f"Scholengemeenschap {i:02d} " + "x" * 50, "AMSTERDAM",
                                             "AMSTERDAM") for i in range(91)}  # fmt: skip
    monkeypatch.setattr(inspectie_vo, "peilbestand", lambda: inspectie.Peilbestand(_URL, "01-11-2026", rijen))
    monkeypatch.setattr(inspectie_vo, "vestigingen", lambda: vestigingen)

    tekst = _tool(DOORSTROOMVRAAG, gemeente="Amsterdam")
    uit = _json(tekst)

    assert len(tekst) < TOOL_RESULT_MAX_CHARS
    assert len(uit["vestigingen"]) == inspectie_vo.MAX_VESTIGINGEN and uit["vestigingen_totaal"] == 91
    assert uit["telling"]["havo"] == {"Voldoende": 91}
    assert f"Afgekapt: {inspectie_vo.MAX_VESTIGINGEN} van de 91 vestigingen" in uit["noot"]


# --- de bron ---------------------------------------------------------------------------------------------------------


def test_de_code_volgt_de_paginas_naar_het_po_so_vo_bestand_in_hetzelfde_document():
    b = inspectie.BASIS
    document = "/documenten/2026/11/03/oordelen-1-november-2026"
    site = _site({
        inspectie.OVERZICHT: (200, f'<a href="{_JAAR.format(2026, 2027)}">26</a>'),
        b + _JAAR.format(2026, 2027): (200, f'<a href="{document}">nov</a>'),
        b + document: (200, f'<a href="https://x/20261102-oordeel-en-standaard-bg.ods">bg</a><a href="{_URL}">po</a>'),
        _URL: (200, _ods([_KOP, *[[r[k] for k in _KOP] for r in _RIJEN]])),
    })  # fmt: skip
    bestand = inspectie_vo.haal_peilbestand_vo(site)

    assert (bestand.url, bestand.peildatum, len(bestand.rijen)) == (_URL, "01-11-2026", len(_RIJEN))


def test_een_onbekende_vo_onderwijssoort_komt_in_het_log(caplog):
    rijen = [*_RIJEN, _rij("VO", "14OY", "00", "Overig EOA", "Voldoende"), _rij("PO", "11AA", "00", "Iets", "Goed")]
    with caplog.at_level(logging.WARNING, logger=inspectie_vo.logger.name):
        inspectie_vo.meld_onbekend(rijen)
    assert [r.getMessage() for r in caplog.records] == ["INSPECTIE_VO_ONBEKEND onderwijssoort=Overig EOA afdelingen=1"]


def test_een_onbereikbare_inspectie_is_een_gecodeerde_fout(bronnen, monkeypatch):
    def kapot():
        try:
            raise httpx.ConnectTimeout("te laat")
        except httpx.ConnectTimeout as e:
            raise inspectie.InspectieOnbereikbaar("de Inspectie antwoordde niet") from e

    monkeypatch.setattr(inspectie_vo, "peilbestand", kapot)
    uit = _tool(DOORSTROOMVRAAG)
    assert fouten.code(uit) == "bron_onbereikbaar" and "Onderwijsinspectie" in uit


def test_duo_onbereikbaar_is_een_gecodeerde_fout(bronnen, monkeypatch):
    def kapot():
        raise httpx.ConnectError("weg")

    monkeypatch.setattr(inspectie_vo, "vestigingen", kapot)
    assert fouten.code(_tool(DOORSTROOMVRAAG)) == "bron_onbereikbaar"


# --- de tool in de app -----------------------------------------------------------------------------------------------


def test_de_tool_staat_in_de_dispatch_de_labels_en_het_schema():
    schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_INSPECTIEOORDEEL_VO)
    enum = schema["parameters"]["properties"]["onderwijssoorten"]["items"]["enum"]

    assert enum == list(inspectie_vo.ONDERWIJSSOORTEN.values())
    assert schema["parameters"]["required"] == ["gemeente"]
    assert "vo-context voor vervolgonderwijs" in schema["description"]
    assert TOOL_GET_INSPECTIEOORDEEL_VO in tools.LABELS and TOOL_GET_INSPECTIEOORDEEL_VO in tools._HANDLERS
