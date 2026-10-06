"""Productscope mbo/hbo/wo als positieve, fail-closed grens van de chat (#355).

Testaudit 6 okt (L5): `search_catalog('mbo studenten per instelling DUO')` gaf
`voprognoses`. riodata sluit alleen expliciet gemarkeerde records uit (#375); alles
zonder besluit kwam erdoor. Nu laat de chat een record alleen toe als het aantoonbaar
over mbo, hbo of wo gaat, en een directe dataset-ID omzeilt dat niet.
"""

import json
from unittest.mock import patch

import pytest

from tools import scopeprofiel
from tools.catalog import _rio_duo, _rio_duo_alles, dataset_counts, dataset_details, search_catalog
from tools.duo import get_duo_data
from tools.rio import get_rio_data

_HO = {
    "leverancier": "DUO",
    "_ckan_id": "p01hoinges",
    "bron": "Ingeschrevenen hoger onderwijs",
    "onderwijstype": ["HO"],
}
_MBO_ALLEN = {
    "leverancier": "DUO",
    "_ckan_id": "mbo-studenten-per-instelling",
    "bron": "Mbo-studenten per instelling",
    "onderwijstype": ["Allen"],
}
_VO = {
    "leverancier": "DUO",
    "_ckan_id": "voprognoses",
    "bron": "Prognoses vo per instelling",
    "onderwijstype": ["VO"],
    "tags": ["prognoses", "instelling"],
}
_GEMENGD = {
    "leverancier": "DUO",
    "_ckan_id": "pogemeente",
    "bron": "Leerlingen per gemeente",
    "onderwijstype": ["PO", "SO", "VO"],
}
_ONBESLIST = {"leverancier": "DUO", "_ckan_id": "nieuw-bestand", "bron": "Nieuw bestand", "onderwijstype": ["Allen"]}
_RIO = {
    "leverancier": "RIO",
    "_rio_resource": "organisatorische-eenheden",
    "bron": "Organisatorische eenheden",
    "onderwijstype": ["Allen"],
}
_INSPECTIE_MBO = {
    "leverancier": "DUO",
    "_ckan_id": "mbo-oordelen",
    "bron": "Oordelen mbo",
    "onderwijstype": ["MBO"],
    "_scope": {"mbo_hbo_wo": "buiten_scope", "reden": "Inspectie-item."},
}


@pytest.mark.parametrize(
    ("record", "verwacht"),
    [
        (_HO, True),
        (_MBO_ALLEN, True),  # 'Allen' bij DUO, maar een mbo-bestand: besluit per ID
        (_RIO, True),
        (_VO, False),
        (_GEMENGD, False),  # gemengd zonder veilige sectorselectie
        (_ONBESLIST, False),  # geen besluit is niet toelaten
        (_INSPECTIE_MBO, False),  # het besluit van riodata blijft gelden
        ({"leverancier": "DUO", "_ckan_id": "leeg"}, False),
    ],
)
def test_alleen_aantoonbaar_mbo_hbo_wo_mag_erin(record, verwacht):
    assert scopeprofiel.in_scope(record) is verwacht


@pytest.fixture
def catalogus():
    with (
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_catalog", return_value=[_HO, _MBO_ALLEN, _VO, _GEMENGD, _ONBESLIST, _RIO]),
    ):
        _rio_duo_alles.cache_clear()
        _rio_duo.cache_clear()
        yield
    _rio_duo_alles.cache_clear()
    _rio_duo.cache_clear()


def test_een_vo_bestand_is_geen_kandidaat_bij_een_mbo_vraag(catalogus):
    """De letterlijke proef uit de testaudit: 'per instelling' trof voprognoses."""
    result = search_catalog("mbo studenten per instelling")

    assert "mbo-studenten-per-instelling" in result
    assert "voprognoses" not in result


def test_de_telling_volgt_de_grens(catalogus):
    assert dataset_counts() == {"CBS": 0, "DUO": 2, "RIO": 1}


def test_details_van_een_dataset_buiten_de_grens_zeggen_waarom(catalogus):
    """Geen 'niet gevonden': dan zegt het model dat de bron niet bestaat (#396)."""
    details = json.loads(dataset_details("voprognoses"))

    assert details["opvraagbaar"] is False
    assert details["buiten_scope"] is True
    assert "mbo, hbo en wo" in details["melding"]


def test_een_directe_id_buiten_de_grens_wordt_niet_geladen(catalogus):
    with patch("tools.duo._duo.load") as load:
        result = json.loads(get_duo_data("voprognoses"))

    load.assert_not_called()
    assert result["buiten_scope"] is True
    assert result["opvraagbaar"] is False


def test_een_onbekende_id_wordt_niet_geladen(catalogus):
    """Fail-closed: wat de catalogus niet kent, heeft geen scopebesluit."""
    with patch("tools.duo._duo.load") as load:
        result = get_duo_data("staat-nergens")

    load.assert_not_called()
    assert "staat-nergens" in result
    assert "niet in de catalogus" in result


def test_een_onbekende_id_noemt_vergelijkbare_ids_binnen_de_grens(catalogus):
    result = get_duo_data("p01ho")

    assert "p01hoinges" in result
    assert "voprognoses" not in result


def test_een_rio_resource_buiten_de_grens_wordt_niet_opgehaald(catalogus):
    """Een resource die het filtercontract kent maar de catalogus niet: geen scopebesluit."""
    with patch("tools.rio._filterfout", return_value=None), patch("tools.rio.fetch") as fetch:
        result = get_rio_data("onbekende-resource")

    fetch.assert_not_called()
    assert "niet in de catalogus" in result


def test_elk_besluit_in_de_tabel_heeft_een_reden():
    assert scopeprofiel.TOEGELATEN
    assert all(reden.strip() for reden in scopeprofiel.TOEGELATEN.values())


# ── Tegen de echte catalogus van riodata ──────────────────────────────────────


def _echt():
    from riodata import catalog

    return {scopeprofiel.dataset_id(e): e for e in catalog(source="all")}


def test_in_de_echte_catalogus_valt_geen_duo_bestand_over_po_so_of_vo_binnen_de_grens():
    toegelaten = [e for e in _echt().values() if scopeprofiel.in_scope(e)]
    po_vo = {"PO", "SO", "VO"}

    assert not [
        scopeprofiel.dataset_id(e)
        for e in toegelaten
        if e.get("leverancier") == "DUO" and po_vo & set(e["onderwijstype"])
    ]
    assert {"p01hoinges", "mbo-studenten-per-instelling", "organisatorische-eenheden"} <= {
        scopeprofiel.dataset_id(e) for e in toegelaten
    }
    assert not {"voprognoses", "02voins-v1", "06_vomtgo"} & {scopeprofiel.dataset_id(e) for e in toegelaten}


def test_elk_besluit_in_de_tabel_hoort_bij_een_bestaand_record():
    """Een besluit voor een verdwenen of hernoemd record is dode code."""
    assert set(scopeprofiel.TOEGELATEN) <= set(_echt())
