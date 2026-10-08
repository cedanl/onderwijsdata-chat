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
from tools.catalog import _cbs, _cbs_alles, _rio_duo, _rio_duo_alles, dataset_counts, dataset_details, search_catalog
from tools.cbs import get_cbs_data, get_cbs_dimension
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
_CBS_MBO = {
    "leverancier": "CBS",
    "_cbs_id": "85353NED",
    "bron": "Mbo; studenten, niveau, leerweg, studierichting, regiokenmerken",
    "onderwijstype": ["MBO"],
}
# De tabel uit de Assen-replay (CH-03): alle onderwijssoorten, ook po en vo.
_CBS_ALLEN = {
    "leverancier": "CBS",
    "_cbs_id": "85701NED",
    "bron": "Leerlingen en studenten; onderwijssoort, woonregio",
    "onderwijstype": ["Allen"],
}
_CBS_VSV = {
    "leverancier": "CBS",
    "_cbs_id": "85368NED",
    "bron": "Voortijdig schoolverlaters; geslacht, onderwijssoort en herkomst",
    "onderwijstype": ["VO", "MBO"],
}
_CBS_VO = {"leverancier": "CBS", "_cbs_id": "80040ned", "bron": "Vo; leerlingen", "onderwijstype": ["VO"]}
_RIO_SECTORFILTER = {
    "leverancier": "RIO",
    "_rio_resource": "aangeboden-opleidingen",
    "bron": "Aangeboden opleidingen",
    "onderwijstype": ["PO", "VO", "MBO", "HBO", "WO"],
}
_RIO_ZONDER_SECTOR = {
    "leverancier": "RIO",
    "_rio_resource": "contactadressen",
    "bron": "Contactadressen",
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
        (_RIO, False),  # register zonder sectorfilter: een pagina bevat ook po/vo (CH-03)
        (_RIO_SECTORFILTER, True),  # alleen met sectorfilter, zie sectorfilter_ontbreekt
        (_RIO_ZONDER_SECTOR, False),
        (_CBS_MBO, True),
        (_CBS_ALLEN, False),  # gemengde CBS-tabel: dezelfde regel als DUO (CH-03)
        (_CBS_VO, False),
        (_VO, False),
        (_GEMENGD, False),  # gemengd zonder veilige sectorselectie
        (_ONBESLIST, False),  # geen besluit is niet toelaten
        (_INSPECTIE_MBO, False),  # het besluit van riodata blijft gelden
        ({"leverancier": "DUO", "_ckan_id": "leeg"}, False),
    ],
)
def test_alleen_aantoonbaar_mbo_hbo_wo_mag_erin(record, verwacht):
    assert scopeprofiel.in_scope(record) is verwacht


_CACHES = (_cbs_alles, _cbs, _rio_duo_alles, _rio_duo)


@pytest.fixture
def catalogus():
    rio_duo = [_HO, _MBO_ALLEN, _VO, _GEMENGD, _ONBESLIST, _RIO, _RIO_SECTORFILTER, _RIO_ZONDER_SECTOR]
    with (
        patch("tools.catalog._cbs_catalog", return_value=[_CBS_MBO, _CBS_ALLEN, _CBS_VO, _CBS_VSV]),
        patch("tools.catalog._rio_catalog", return_value=rio_duo),
    ):
        for c in _CACHES:
            c.cache_clear()
        yield
    for c in _CACHES:
        c.cache_clear()


def test_een_vo_bestand_is_geen_kandidaat_bij_een_mbo_vraag(catalogus):
    """De letterlijke proef uit de testaudit: 'per instelling' trof voprognoses."""
    result = search_catalog("mbo studenten per instelling")

    assert "mbo-studenten-per-instelling" in result
    assert "voprognoses" not in result


def test_de_telling_volgt_de_grens(catalogus):
    assert dataset_counts() == {"CBS": 2, "DUO": 2, "RIO": 1}


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


# ── CBS: dezelfde regel als DUO (CH-03) ─────────────────────────────────────


def test_een_gemengde_cbs_tabel_is_geen_zoektreffer(catalogus):
    result = search_catalog("leerlingen en studenten onderwijssoort woonregio", source="cbs")

    assert "85701NED" not in result


def test_details_van_een_gemengde_cbs_tabel_zeggen_waarom(catalogus):
    details = json.loads(dataset_details("85701NED"))

    assert details["buiten_scope"] is True
    assert "mbo, hbo en wo" in details["melding"]


@pytest.mark.parametrize("dataset_id", ["85701NED", "80040ned"])
def test_een_cbs_tabel_buiten_de_grens_wordt_niet_geladen(catalogus, dataset_id):
    with patch("tools.cbs.data") as data:
        result = json.loads(get_cbs_data(dataset_id, {"$filter": "startswith(Regiokenmerken,'GM0106')"}))

    data.assert_not_called()
    assert result["buiten_scope"] is True


def test_ook_de_dimensies_van_een_cbs_tabel_buiten_de_grens_niet(catalogus):
    with patch("tools.cbs._dimension_rows") as rijen:
        result = json.loads(get_cbs_dimension("85701NED", "Onderwijssoort"))

    rijen.assert_not_called()
    assert result["buiten_scope"] is True


def test_assen_replay_wordt_geweigerd_voor_de_brede_call(catalogus):
    """Live (CH-03): twee exacte filters gaven 0 rijen, de herstelpoging laadde 85701NED met
    startswith(Regiokenmerken,'GM0106') = 1.080 rijen incl. po/vo. Een fallback mag de
    sectorbinding niet afzwakken."""
    with patch("tools.cbs.data", return_value=[]) as data, patch("tools.cbs.definitions", return_value={}):
        get_cbs_data("85353NED", {"$filter": "RegioS eq 'GM0106'"})
        get_cbs_data("85353NED", {"$filter": "RegioS eq 'GM0106  '"})
        herstel = json.loads(get_cbs_data("85701NED", {"$filter": "startswith(Regiokenmerken,'GM0106')"}))

    assert [c.args[0] for c in data.call_args_list] == ["85353NED", "85353NED"]
    assert herstel["buiten_scope"] is True


def test_een_mbo_tabel_van_cbs_laadt_gewoon(catalogus):
    rijen = [{"RegioS": "GM0106", "Studenten_1": 10}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data("85353NED", {"$filter": "RegioS eq 'GM0106'"}))

    data.assert_called_once()
    assert result["data_key"].startswith("cbs:85353NED")


_VSV_RIJEN = [
    {"Onderwijssoort": "A042781", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 4000},  # vmbo/havo/vwo
    {"Onderwijssoort": "A043837", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 9000},  # totaal
    {"Onderwijssoort": "A025290", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 5000},  # mbo
]


def test_een_cbs_tabel_over_mbo_en_vo_geeft_alleen_de_mbo_rijen(catalogus):
    """Een EN-clausule in $filter is geen grens: de CBS-feed gaf de vo-rijen toch. De code selecteert."""
    from tools import store

    with patch("tools.cbs.data", return_value=_VSV_RIJEN), patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data("85368NED"))

    df = store.get(result["data_key"])
    assert df["Onderwijssoort"].tolist() == ["A025290"]
    assert "4000" not in json.dumps(result) and "9000" not in json.dumps(result)


def test_een_vo_selectie_uit_een_mbo_en_vo_tabel_geeft_geen_data(catalogus):
    with patch("tools.cbs.data", return_value=_VSV_RIJEN[:2]), patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_data("85368NED", {"$filter": "Onderwijssoort eq 'A042781'"})

    assert "data_key" not in result
    assert "4000" not in result
    assert "A025290" in result  # de mbo-codes om mee te filteren


def test_de_snippet_selecteert_dezelfde_mbo_rijen():
    from tools.snippet import _cbs_laadregels

    regels = _cbs_laadregels({"dataset_id": "85368NED", "filters": {}})

    assert "isin(" in regels[-1] and "A025290" in regels[-1] and "A042781" not in regels[-1]


def test_elke_bronregel_van_een_mbo_en_vo_tabel_noemt_alleen_mbo(catalogus):
    """Audit 17 (CH-45): bij een vo-vraag noemde het antwoord 85368NED als bron, terwijl de chat
    alleen de mbo-rijen laadt. Elke bronregel volgt de selectie die get_cbs_data maakt."""
    from agent.citaties import _bron
    from agent.dashboard import _source_label
    from agent.selectie import selectie_in_woorden
    from tools import store
    from tools.catalog import bron_naam

    with patch("tools.cbs.data", return_value=_VSV_RIJEN), patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data("85368NED"))

    regels = [
        result["catalogus_titel"],
        _bron(result["data_key"], "get_cbs_data"),
        selectie_in_woorden(result["data_key"]) or "",
        bron_naam("85368NED"),
        _source_label("CBS", "85368NED", None),
    ]
    assert all(f"{_CBS_VSV['bron']}, alleen mbo" in regel for regel in regels), regels
    assert store.herkomst(result["data_key"])[0] == "bron: CBS, dataset 85368NED, alleen mbo"  # CSV- en grafiekexport


def test_de_bronregel_van_een_mbo_tabel_is_de_catalogustitel(catalogus):
    from tools.catalog import bron_naam, bron_titel

    assert bron_titel("85353NED") == _CBS_MBO["bron"]
    assert bron_naam("85353NED") == f"85353NED ({_CBS_MBO['bron']})"
    assert bron_naam("onbekend-id") == "onbekend-id"


# ── RIO: registers over alle sectoren alleen met een sectorfilter (CH-03) ────────


@pytest.fixture
def filtercontract_akkoord():
    with patch("tools.rio._filterfout", return_value=None):
        yield


@pytest.mark.parametrize("filters", [{}, {"type": "AANGEBODENVOOPLEIDING"}, {"onderwijslocatieId": "x"}])
def test_een_rio_register_zonder_sectorfilter_wordt_niet_opgehaald(catalogus, filtercontract_akkoord, filters):
    with patch("tools.rio.fetch") as fetch:
        result = get_rio_data("aangeboden-opleidingen", filters)

    fetch.assert_not_called()
    assert "AANGEBODENMBOOPLEIDING" in result


def test_een_rio_register_met_sectorfilter_wordt_opgehaald(catalogus, filtercontract_akkoord):
    with patch("tools.rio.fetch", return_value=[{"code": "1"}]) as fetch:
        result = json.loads(get_rio_data("aangeboden-opleidingen", {"type": "AANGEBODENMBOOPLEIDING"}))

    fetch.assert_called_once()
    assert result["data_key"].startswith("rio:aangeboden-opleidingen")


def test_een_rio_register_dat_niet_per_sector_te_selecteren_is_verwijst_naar_de_instellingsroute(
    catalogus, filtercontract_akkoord
):
    with patch("tools.rio.fetch") as fetch:
        result = json.loads(get_rio_data("contactadressen", {"contactadrestype": "BEZOEKNL"}))

    fetch.assert_not_called()
    assert result["buiten_scope"] is True
    assert "get_rio_instelling" in result["melding"]


def test_elk_sectorfilter_bestaat_in_het_filtercontract():
    """Een sectorfilter op een filter of waarde die RIO niet kent, laat niets meer door."""
    from riodata import filtercontract

    contract = filtercontract()["resources"]
    for resource, (naam, waarden) in scopeprofiel.SECTORFILTER.items():
        filters = {f["naam"]: f for f in contract[resource]["filters"]}
        assert naam in filters, resource
        assert waarden <= set(filters[naam]["enum"]), resource


def test_elk_besluit_in_de_tabel_heeft_een_reden():
    assert scopeprofiel.TOEGELATEN
    assert all(reden.strip() for reden in scopeprofiel.TOEGELATEN.values())


# ── Tegen de echte catalogus van riodata ──────────────────────────────────────


def _echt():
    from onderwijsdata import catalog as cbs_catalog
    from riodata import catalog

    return {scopeprofiel.dataset_id(e): e for e in [*cbs_catalog(), *catalog(source="all")]}


def test_in_de_echte_catalogus_valt_geen_duo_bestand_over_po_so_of_vo_binnen_de_grens():
    toegelaten = [e for e in _echt().values() if scopeprofiel.in_scope(e)]
    po_vo = {"PO", "SO", "VO"}

    assert not [
        scopeprofiel.dataset_id(e)
        for e in toegelaten
        if e.get("leverancier") == "DUO" and po_vo & set(e["onderwijstype"])
    ]
    assert {"p01hoinges", "mbo-studenten-per-instelling", "opleidingserkenningen"} <= {
        scopeprofiel.dataset_id(e) for e in toegelaten
    }
    assert not {"voprognoses", "02voins-v1", "06_vomtgo"} & {scopeprofiel.dataset_id(e) for e in toegelaten}


def test_in_de_echte_catalogus_valt_geen_gemengde_of_po_vo_cbs_tabel_binnen_de_grens():
    toegelaten = {scopeprofiel.dataset_id(e): e for e in _echt().values() if scopeprofiel.in_scope(e)}
    cbs = {i: e for i, e in toegelaten.items() if e.get("leverancier") == "CBS" or e.get("_cbs_id")}

    # Een tabel over mbo én vo alleen als de code de mbo-rijen selecteert (CBS_SECTORFILTER).
    po_vo = [i for i, e in cbs.items() if {"PO", "SO", "VO"} & set(e.get("onderwijstype") or [])]
    assert set(po_vo) <= set(scopeprofiel.CBS_SECTORFILTER)
    assert "85701NED" not in cbs  # Assen-replay
    assert {"85353NED", "85422NED", "85423NED"} <= set(cbs)  # tabellen die de code zelf noemt


def test_elk_besluit_in_de_tabel_hoort_bij_een_bestaand_record():
    """Een besluit voor een verdwenen of hernoemd record is dode code."""
    assert set(scopeprofiel.TOEGELATEN) <= set(_echt())
