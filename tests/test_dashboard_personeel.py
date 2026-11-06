"""Personeel van een universiteit op Mijn instelling (#936): `/api/dashboard/personeel`, `data/dashboard_personeel.py`.

Op het synthetische proefbestand van `onderwijsbronnen.unl`, zonder netwerk. Het dashboard rekent met `reken` van de
tool, dus elk getal is dat van de chat (tests/test_wo_personeel.py): Universiteit Utrecht 6.184,36 fte zonder GEZO in
2025, waarvan 3.584,05 wetenschappelijk personeel.
"""

import json
from datetime import UTC, datetime

import pytest
from onderwijsbronnen import unl
from onderwijsbronnen.unl import proefbestand

from core import actualiteit
from data import dashboard_personeel as dashboard
from data import instellingen
from tools import store, wo_personeel

_NU = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
_REGISTER = {
    "universiteit utrecht": ("Universiteit Utrecht", "wo", "21PD"),
    "hogeschool utrecht": ("Hogeschool Utrecht", "hbo", "25DW"),
    "roc midden nederland": ("ROC Midden Nederland", "mbo", "25LH"),
    "theologische universiteit apeldoorn": ("Theologische Universiteit Apeldoorn", "wo", "21QO"),
    "transnationale universiteit limburg": ("Transnationale Universiteit Limburg", "wo", "27YA"),
}


def _profiel(naam: str) -> dict | None:
    gevonden = _REGISTER.get(" ".join(naam.split()).lower())
    return None if gevonden is None else {"naam": gevonden[0], "sector": gevonden[1], "instellingscode": gevonden[2]}


@pytest.fixture(autouse=True)
def proefbestand_en_register(monkeypatch):
    monkeypatch.setattr(unl, "haal_op", proefbestand.standaard)
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    monkeypatch.setattr(actualiteit, "nu", lambda: _NU)
    wo_personeel._wopi.cache_clear()
    yield
    wo_personeel._wopi.cache_clear()


def _per_jaar(uit: dict) -> dict[int, dict]:
    return {r["jaar"]: r for r in uit["personeel"]["cijfers"]}


def test_fte_zonder_gezo_per_jaar_naar_wp_obp_en_aandeel_tijdelijk():
    uit = dashboard.load_dashboard_personeel("Universiteit Utrecht")

    assert (uit["gevonden"], uit["sector"]) == (True, "wo")
    pers = uit["personeel"]
    assert (pers["eenheid"], pers["gezo"]) == ("fte", "excl")
    assert pers["instelling"] == {"naam": "Universiteit Utrecht", "brin": "21PD"}
    rij = _per_jaar(uit)[2025]
    assert rij["peildatum"] == "31-12-2025"
    assert (rij["totaal"], rij["wetenschappelijk_personeel"], rij["obp"]) == (6184.36, 3584.05, 2600.31)
    assert rij["aandeel_tijdelijk_procent"] == round(100 * rij["tijdelijk"] / (rij["vast"] + rij["tijdelijk"]), 1)


def test_dezelfde_getallen_als_de_chat():
    per_jaar = _per_jaar(dashboard.load_dashboard_personeel("Universiteit Utrecht"))

    def chat(uitsplitsing: str) -> dict[int, dict]:
        uit = json.loads(wo_personeel.get_wo_personeel(instelling="21PD", reeks=True, uitsplitsing=uitsplitsing))
        return {r["jaar"]: r for r in uit["cijfers"]}

    for jaar, rij in chat("wp_obp").items():
        assert {k: per_jaar[jaar][k] for k in rij} == rij
    for jaar, rij in chat("vast_tijdelijk").items():
        assert {k: per_jaar[jaar][k] for k in rij} == rij


def test_voor_2003_is_vast_en_tijdelijk_leeg_geen_nul():
    per_jaar = _per_jaar(dashboard.load_dashboard_personeel("Universiteit Utrecht"))

    eerste = min(per_jaar)
    assert eerste < wo_personeel.AANSTELLING_VANAF
    assert per_jaar[eerste]["totaal"] > 0
    assert per_jaar[eerste]["vast"] is None and per_jaar[eerste]["aandeel_tijdelijk_procent"] is None


def test_de_vaste_zinnen_zonder_aanwijzingen_aan_het_model(monkeypatch):
    monkeypatch.setattr(store, "put", lambda *a, **k: pytest.fail("een dashboard schrijft niet in de store"))

    pers = dashboard.load_dashboard_personeel("Universiteit Utrecht")["personeel"]

    voorbehouden = " ".join(pers["voorbehouden"])
    assert wo_personeel.PEILDATUM in pers["voorbehouden"]
    assert "fte is geen aantal personen" in voorbehouden
    assert "Zonder het HOOP-gebied Gezondheid (GEZO)" in voorbehouden and "mét GEZO." in voorbehouden
    assert "Vast en tijdelijk bestaan vanaf 2003" in pers["noot"]
    assert (
        pers["bron"]["regel"]
        == "WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025, excl. sector Gezondheid"
    )
    tekst = json.dumps(pers, ensure_ascii=False)
    for aanwijzing in ("Schrijf 'fte'", "Zeg dat", "Noem geen", "uitdrukkelijk om vraagt", "Neem in het antwoord"):
        assert aanwijzing not in tekst


@pytest.mark.parametrize("naam", ["Hogeschool Utrecht", "ROC Midden Nederland"])
def test_hbo_en_mbo_krijgen_geen_kaart_en_laden_wopi_niet(monkeypatch, naam):
    monkeypatch.setattr(unl, "haal_op", lambda: pytest.fail("WOPI hoort niet te laden"))

    uit = dashboard.load_dashboard_personeel(naam)

    assert uit["gevonden"] is True and uit["personeel"] is None
    assert "melding" not in uit and uit["bronnen"] == []


@pytest.mark.parametrize(
    ("naam", "melding"),
    [
        (
            "Theologische Universiteit Apeldoorn",
            "Theologische Universiteit Apeldoorn (21QO) is een wo-instelling, maar geen lid van Universiteiten van "
            "Nederland en staat niet in het WOPI-bestand: er zijn geen personeelscijfers.",
        ),
        (
            "Transnationale Universiteit Limburg",
            "Transnationale Universiteit Limburg (27YA) staat niet in het WOPI-bestand: dat heeft alleen de 14 "
            "universiteiten van Universiteiten van Nederland.",
        ),
    ],
)
def test_een_universiteit_buiten_wopi_krijgt_de_vaste_melding(naam, melding):
    uit = dashboard.load_dashboard_personeel(naam)

    assert uit["personeel"] is None and uit["melding"] == melding
    # De chat zegt hetzelfde, met de aanwijzing aan het model erachter.
    assert wo_personeel.get_wo_personeel(instelling=naam) == f"{melding} {wo_personeel.GEEN_GETAL}"


def test_een_bron_die_uitvalt_is_een_gat_geen_kapot_dashboard(monkeypatch):
    def kapot():
        raise unl.WopiFout("geen draaitabel")

    monkeypatch.setattr(unl, "haal_op", kapot)

    uit = dashboard.load_dashboard_personeel("Universiteit Utrecht")

    assert (uit["gevonden"], uit["personeel"]) == (True, None)
    assert uit["niet_beschikbaar"] == [
        {"onderdeel": "Personeel (WOPI)", "bron": "UNL", "reden": "de data van de bron kon niet worden verwerkt"}
    ]


def test_het_bronblok_noemt_editie_en_peildatum():
    dashboard.load_dashboard_personeel("Universiteit Utrecht")
    [regel] = dashboard.load_dashboard_personeel("Universiteit Utrecht")["bronnen"]  # ook bij een cachetreffer

    assert (regel["bron"], regel["dataset"]) == ("UNL", "unl:wopi")
    assert regel["titel"] == "Universiteiten van Nederland, WOPI-personeelsbestand"
    assert regel["url"] == unl.PAGINA
    assert (regel["editie"], regel["peildatum"], regel["peilmoment"]) == ("2025", "31-12-2025", "editie 2025")
    assert regel["opgehaald_op"] == _NU.isoformat()


def test_een_onbekende_instelling_is_niet_gevonden():
    assert dashboard.load_dashboard_personeel("Universiteit Nergens") == {
        "instelling": "Universiteit Nergens",
        "gevonden": False,
    }
