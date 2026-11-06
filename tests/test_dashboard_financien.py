"""Financiën van het bestuur op Mijn instelling (#935): `/api/dashboard/financien`, `data/dashboard_financien.py`.

Zonder netwerk, op de synthetische eenheden van tests/test_financien.py: het pakket rekent er zelf mee (sectorcijfer,
signaleringen). Het dashboard rekent niet opnieuw: het geeft de uitkomst van `tools.financien.voor_instelling`, de
regels van de chat, zonder de aanwijzingen aan het model en zonder de tabel in de store.
"""

import json
from datetime import UTC, datetime

import httpx
import pytest
from onderwijsbronnen.duo import financien

from core import actualiteit
from data import dashboard_financien as dashboard
from data import instellingen
from tests.test_financien import _BESTUUR, _DATA, _PROFIELEN
from tools import financien as tool
from tools import fusies, store

_NU = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
# Het register: de profielen van de tooltest, plus een hogeschool met een leeg kengetal en een tweede instelling onder
# het bestuur van Aeres (40687) en van 40833 (dat een eenheid per BRIN heeft).
_REGISTER = _PROFIELEN | {
    "hogeschool dun": {"naam": "Hogeschool Dun", "sector": "hbo", "instellingscode": "30DN"},
    "aeres mbo": {"naam": "Aeres MBO", "sector": "mbo", "instellingscode": "01OE"},
    "roc van flevoland": {"naam": "ROC van Flevoland", "sector": "mbo", "instellingscode": "25LR"},
}
_BESTUREN = _BESTUUR | {"30DN": 30000, "01OE": 40687, "25LR": 40833}
# Aanwijzingen aan het model: die staan in de chat, niet op een dashboard.
_AANWIJZINGEN = ("Zeg dat", "Noem geen", "Reken niets", "Neem de voorbehouden op")


@pytest.fixture(autouse=True)
def bron(monkeypatch):
    """De pakketlader nagebootst: zo loopt de melding voor het bronblok (`tool._bron`) gewoon mee."""
    monkeypatch.setattr(instellingen, "instellingsprofiel", lambda naam: _REGISTER.get(naam.strip().lower()))
    monkeypatch.setattr(instellingen, "get_all", lambda: list(_REGISTER.values()))
    monkeypatch.setattr(tool, "bestuur_van", lambda code: _BESTUREN.get(code))
    monkeypatch.setattr(financien, "laad", lambda haler: _DATA)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: ())
    monkeypatch.setattr(actualiteit, "nu", lambda: _NU)
    tool._bron.cache_clear()
    yield
    tool._bron.cache_clear()


def _jaar(uit: dict, jaar: int) -> dict:
    [eenheid] = uit["financien"]["eenheden"]
    return next(j for j in eenheid["reeks"] if j["verslagjaar"] == jaar)


def test_de_kengetallen_van_het_bestuur_naast_het_sectorcijfer_met_signaal_en_voorbehouden():
    uit = dashboard.load_dashboard_financien("ROC Midden Nederland")

    assert (uit["gevonden"], uit["instelling"], uit["sector"]) == (True, "ROC Midden Nederland", "mbo")
    fin = uit["financien"]
    assert fin["bestuur"]["nummer"] == "40597" and fin["instelling"]["instellingscode"] == "25LH"
    # Dezelfde getallen als de chat (tests/test_financien.py): het gewogen sectorcijfer, niet de mediaan.
    assert _jaar(uit, 2025)["solvabiliteit_1"] == {"bestuur": 0.69, "sector": 0.64, "verschil": 0.05}
    assert [j["verslagjaar"] for j in fin["eenheden"][0]["reeks"]] == [2024, 2025]
    assert fin["sectorcijfer"]["sector"] == "mbo" and "Gewogen" in fin["sectorcijfer"]["methode"]
    assert fin["signaleringswaarden"]["solvabiliteit_2"] == "onder 0,30"
    voorbehouden = " ".join(fin["voorbehouden"])
    assert "hele bestuur" in voorbehouden and "niets over de kwaliteit" in voorbehouden
    assert "signaal, geen oordeel" in voorbehouden


def test_het_dashboard_geeft_geen_aanwijzingen_aan_het_model_en_bewaart_niets(monkeypatch):
    monkeypatch.setattr(store, "put", lambda *a, **k: pytest.fail("een dashboard schrijft niet in de store"))

    for naam in ("ROC Midden Nederland", "Aeres Hogeschool", "ROC van Amsterdam", "Hogeschool Dun"):
        uit = dashboard.load_dashboard_financien(naam)
        tekst = json.dumps(uit, ensure_ascii=False)
        assert not any(a in tekst for a in _AANWIJZINGEN), naam
        assert "noot" not in uit["financien"] and "data_key" not in uit["financien"]


def test_de_chat_houdt_haar_aanwijzingen():
    """De feiten zijn gedeeld; de tool zet de aanwijzing erachter, zoals voor het dashboard (#935)."""
    uit = json.loads(tool.get_bestuursfinancien("Aeres Hogeschool"))
    assert "DUO rekent het bestuur toe aan het mbo: de cijfers gaan over het hele bestuur" in uit["noot"]
    assert "het mbo. Zeg dat." in uit["noot"]
    [eenheid] = json.loads(tool.get_bestuursfinancien("ROC van Amsterdam"))["eenheden"]
    assert "financiële positie." in eenheid["melding"] and eenheid["melding"].endswith(" Zeg dat.")
    assert tool.get_bestuursfinancien("Transnationale Universiteit Limburg").endswith("Noem geen cijfers.")


def test_leeg_blijft_leeg():
    j = _jaar(dashboard.load_dashboard_financien("Hogeschool Dun"), 2025)

    assert j["rentabiliteit_procent"] == {"bestuur": None, "sector": -4.55}  # geen verschil zonder bestuur
    assert j["solvabiliteit_2"]["bestuur"] == 0.25  # wel gevuld: alleen de lege waarde is null


def test_een_signaal_onder_de_waarden_van_de_inspectie():
    j = _jaar(dashboard.load_dashboard_financien("Hogeschool Dun"), 2025)
    assert {s["kengetal"] for s in j["signaleringen"]} == {"solvabiliteit_2", "liquiditeit"}


def test_een_instelling_met_een_eigen_eenheid_krijgt_alleen_die_en_geen_gedeeld_bestuur():
    fin = dashboard.load_dashboard_financien("ROC van Amsterdam")["financien"]

    assert [e["eenheid"] for e in fin["eenheden"]] == ["40833-25PZ"]
    assert "variant wisselt" in fin["eenheden"][0]["melding"]
    assert fin["meldingen"] == []


def test_een_gedeeld_bestuur_en_een_andere_sector_staan_er_als_feit():
    fin = dashboard.load_dashboard_financien("Aeres Hogeschool")["financien"]

    assert fin["meldingen"] == [
        "Aeres Hogeschool is een hbo-instelling, maar DUO rekent het bestuur toe aan het mbo: de cijfers gaan over het "
        "hele bestuur en het sectorcijfer is dat van het mbo.",
        "Ook Aeres MBO valt onder dit bestuur: de cijfers gelden voor het hele bestuur, voor elk van zijn instellingen "
        "gelijk.",
    ]


def test_een_instelling_zonder_bestuur_krijgt_een_nette_melding():
    uit = dashboard.load_dashboard_financien("Transnationale Universiteit Limburg")

    assert uit["gevonden"] is True and uit["financien"] is None
    assert uit["melding"] == (
        "Voor tUL (27YA) staat geen bestuur in DUO's adressenbestand: er zijn geen financiële cijfers aan te koppelen."
    )
    assert "niet_beschikbaar" not in uit


def test_een_onbekende_instelling_is_niet_gevonden():
    assert dashboard.load_dashboard_financien("Hogeschool Nergens") == {
        "instelling": "Hogeschool Nergens",
        "gevonden": False,
    }


def test_een_bron_die_uitvalt_is_een_gat_geen_kapot_dashboard(monkeypatch):
    def te_laat(haler):
        raise financien.FinancienOnbereikbaar("DUO") from httpx.ConnectTimeout("te laat")

    monkeypatch.setattr(financien, "laad", te_laat)

    uit = dashboard.load_dashboard_financien("ROC Midden Nederland")

    assert (uit["gevonden"], uit["financien"]) == (True, None)
    assert uit["niet_beschikbaar"] == [
        {"onderdeel": "Financiën van het bestuur", "bron": "DUO", "reden": "de bron antwoordde niet op tijd"}
    ]
    assert uit["bronnen"] == []


def test_het_bronblok_noemt_de_editie_ook_bij_een_cachetreffer():
    dashboard.load_dashboard_financien("ROC Midden Nederland")
    [regel] = dashboard.load_dashboard_financien("ROC Midden Nederland")["bronnen"]

    assert regel["bron"] == "DUO" and regel["dataset"] == "financien"
    assert regel["titel"].startswith("Financiële verantwoording uit XBRL")  # de titel uit de catalogus
    assert regel["url"] == financien.PAGINA
    assert regel["editie"] == "verslagjaren 2021-2025"
    assert regel["peildatum"] == "31 december 2025"
    assert regel["peilmoment"] == "editie verslagjaren 2021-2025, versie van 15 september 2026"
    assert regel["opgehaald_op"] == _NU.isoformat()
