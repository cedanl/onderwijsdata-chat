"""Productscope mbo/hbo/wo als positieve, fail-closed grens van de chat (#355).

Testaudit 6 okt (L5): `search_catalog('mbo studenten per instelling DUO')` gaf
`voprognoses`. riodata sluit alleen expliciet gemarkeerde records uit (#375); alles
zonder besluit kwam erdoor. Nu laat de chat een record alleen toe als het aantoonbaar
over mbo, hbo of wo gaat, en een directe dataset-ID omzeilt dat niet.
"""

import json
import re
from unittest.mock import patch

import pytest

from tests.zoekuitkomst import envelop, treffers
from tools import scopeprofiel
from tools.catalog import (
    _cbs,
    _cbs_alles,
    _rio_duo,
    _rio_duo_alles,
    dataset_counts,
    dataset_details,
    kandidaten,
    scope_blokkade,
    search_catalog,
)
from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.duo import get_duo_data
from tools.ho_markers import beurtvraag, noemt_ho, opent_vo_context
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
# Een vo-bron uit VO_CONTEXT (#557): binnen het profiel, maar alleen vindbaar bij een vraag die ho noemt.
_VO = {
    "leverancier": "DUO",
    "_ckan_id": "voprognoses",
    "bron": "Prognoses vo per instelling",
    "samenvatting": "Prognose van het aantal leerlingen in het vo per instelling tot 2030.",
    "onderwijstype": ["VO"],
    "tags": ["prognoses", "instelling", "voprognoses"],
}
# Een tweede DUO-bestand over vo, niet in VO_CONTEXT: blijft erbuiten, ook bij een ho-vraag.
_VO_VESTIGING = {
    "leverancier": "DUO",
    "_ckan_id": "02voins-v1",
    "bron": "VO-leerlingen per vestiging en leerjaar naar postcode, plaats en gemeente",
    "samenvatting": "Prognose en aantal leerlingen in het vo per instelling, niveau en provincie tot 2030.",
    "onderwijstype": ["VO"],
    "tags": ["prognoses", "instelling", "leerlingen", "doorstroom"],
}
_VO_INSTELLING = {**_VO_VESTIGING, "_ckan_id": "01voins-v1", "bron": "VO-leerlingen per vestiging naar onderwijstype"}
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
# Alle onderwijssoorten, ook po en vo, zonder sectorselectie in de code: blijft erbuiten.
_CBS_ALLEN = {
    "leverancier": "CBS",
    "_cbs_id": "37220",
    "bron": "Leerlingen en studenten; onderwijssoort, vanaf 1900",
    "onderwijstype": ["Allen"],
}
# De tabel uit de Assen-replay (CH-03): alle onderwijssoorten, maar de code selecteert mbo/hbo/wo (#473).
_CBS_WOONREGIO = {
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
# Dezelfde VSV naar leeftijd (v0.2.1): Onderwijssoort kent alleen totalen, mbo is A025290.
_CBS_VSV_LEEFTIJD = {
    "leverancier": "CBS",
    "_cbs_id": "85367NED",
    "bron": "Voortijdig schoolverlaters; geslacht, leeftijd en herkomst",
    "onderwijstype": ["VO", "MBO"],
}
_CBS_VO = {"leverancier": "CBS", "_cbs_id": "80040ned", "bron": "Vo; leerlingen", "onderwijstype": ["VO"]}
# De vo-contextbronnen van CBS (#557), met de woorden van hun catalogusrecord.
_CBS_VO_CONTEXT = {
    "leverancier": "CBS",
    "_cbs_id": "85566NED",
    "bron": "Vo en vso; doorstroom en uitstroom, achtergrondkenmerken",
    "beschrijving": "Doorstroom van vo- en vso-leerlingen (vmbo, havo, vwo) naar mbo, hbo en wo.",
    "onderwijstype": ["VO"],
}
_CBS_VO_LEERLINGEN = {
    "leverancier": "CBS",
    "_cbs_id": "85380NED",
    "bron": "Vo; leerlingen, onderwijssoort, leerjaar, woonregio",
    "beschrijving": "Vo-leerlingen per niveau en leerjaar naar woonregio (provincie, gemeente).",
    "onderwijstype": ["VO"],
}
_CBS_VO_CONTEXT_RECORDS = [
    _CBS_VO_CONTEXT,
    _CBS_VO_LEERLINGEN,
    {**_CBS_VO_LEERLINGEN, "_cbs_id": "85381NED", "bron": "Vo; examenkandidaten en gediplomeerden, onderwijssoort"},
    {**_CBS_VO_LEERLINGEN, "_cbs_id": "85382NED", "bron": "Vo; examenkandidaten en gediplomeerden, woonregio"},
]
# Een gearchiveerde vo-reeks, niet in VO_CONTEXT: dezelfde woorden als 85380NED, maar blijft erbuiten (#877).
_CBS_VO_DETAIL = {
    "leverancier": "CBS",
    "_cbs_id": "80041ned",
    "bron": "Vo; leerlingen, onderwijssoort, leerjaar, leeftijd",
    "beschrijving": "Vo-leerlingen per niveau, leerjaar en provincie; doorstroom naar hbo en wo.",
    "onderwijstype": ["VO"],
}
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
        (_CBS_WOONREGIO, True),  # gemengd, maar alleen met de sectorselectie uit CBS_SECTORFILTER (#473)
        (_CBS_VO, False),
        (_VO, True),  # vo-context (#557): de zoekpoort, niet in_scope, houdt hem uit gewone vragen
        (_VO_VESTIGING, False),
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
    rio_duo = [
        _HO,
        _MBO_ALLEN,
        _VO,
        _VO_VESTIGING,
        _VO_INSTELLING,
        _GEMENGD,
        _ONBESLIST,
        _RIO,
        _RIO_SECTORFILTER,
        _RIO_ZONDER_SECTOR,
    ]
    cbs = [
        _CBS_MBO,
        _CBS_ALLEN,
        _CBS_VO,
        _CBS_VO_DETAIL,
        _CBS_VSV,
        _CBS_VSV_LEEFTIJD,
        _CBS_WOONREGIO,
        *_CBS_VO_CONTEXT_RECORDS,
    ]
    with (
        patch("tools.catalog._cbs_alles", return_value=cbs),
        patch("tools.catalog._rio_duo_alles", return_value=rio_duo),
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
    assert "02voins-v1" not in result


def test_de_telling_volgt_de_grens(catalogus):
    """De vo-contextbronnen in de testcatalogus tellen mee (#557): vier CBS-tabellen en voprognoses."""
    assert dataset_counts() == {"CBS": 8, "DUO": 3, "RIO": 1}


def test_details_van_een_dataset_buiten_de_grens_zeggen_waarom(catalogus):
    """Geen 'niet gevonden': dan zegt het model dat de bron niet bestaat (#396)."""
    details = json.loads(dataset_details("02voins-v1"))

    assert details["opvraagbaar"] is False
    assert details["buiten_scope"] is True
    assert "mbo, hbo en wo" in details["melding"]


def test_een_directe_id_buiten_de_grens_wordt_niet_geladen(catalogus):
    with patch("tools.duo._duo.load") as load:
        result = json.loads(get_duo_data("02voins-v1"))

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
    result = search_catalog("leerlingen en studenten onderwijssoort vanaf 1900", source="cbs")

    assert "37220" not in result


def test_details_van_een_gemengde_cbs_tabel_zeggen_waarom(catalogus):
    details = json.loads(dataset_details("37220"))

    assert details["buiten_scope"] is True
    assert "mbo, hbo en wo" in details["melding"]


@pytest.mark.parametrize("dataset_id", ["37220", "80040ned"])
def test_een_cbs_tabel_buiten_de_grens_wordt_niet_geladen(catalogus, dataset_id):
    with patch("tools.cbs.data") as data:
        result = json.loads(get_cbs_data(dataset_id, {"$filter": "startswith(Regiokenmerken,'GM0106')"}))

    data.assert_not_called()
    assert result["buiten_scope"] is True


def test_ook_de_dimensies_van_een_cbs_tabel_buiten_de_grens_niet(catalogus):
    with patch("tools.cbs._dimension_rows") as rijen:
        result = json.loads(get_cbs_dimension("37220", "Onderwijssoort"))

    rijen.assert_not_called()
    assert result["buiten_scope"] is True


# Codes uit 85701NED (live 09-10): basisonderwijs, totaal vo, hbo, totaal mbo (excl. extranei).
_WOONREGIO_RIJEN = [
    {"Onderwijssoort": "A025280", "Regiokenmerken": "GM0106", "Perioden": "2024SJ00", "LeerlingenStudenten_1": 7000},
    {"Onderwijssoort": "T001345", "Regiokenmerken": "GM0106", "Perioden": "2024SJ00", "LeerlingenStudenten_1": 4000},
    {"Onderwijssoort": "A025294", "Regiokenmerken": "GM0106", "Perioden": "2024SJ00", "LeerlingenStudenten_1": 1500},
    {"Onderwijssoort": "A041867", "Regiokenmerken": "GM0106", "Perioden": "2024SJ00", "LeerlingenStudenten_1": 2000},
]


def test_assen_replay_laadt_alleen_mbo_hbo_en_wo(catalogus):
    """Live (CH-03): twee exacte filters gaven 0 rijen, de herstelpoging laadde 85701NED met
    startswith(Regiokenmerken,'GM0106') = 1.080 rijen incl. po/vo. Een fallback mag de
    sectorbinding niet afzwakken: de tabel komt alleen binnen met de mbo/hbo/wo-selectie (#473)."""
    from tools import store

    with (
        patch("tools.cbs.data", side_effect=[[], [], _WOONREGIO_RIJEN]) as data,
        patch("tools.cbs.definitions", return_value={}),
    ):
        get_cbs_data("85353NED", {"$filter": "RegioS eq 'GM0106'"})
        get_cbs_data("85353NED", {"$filter": "RegioS eq 'GM0106  '"})
        herstel = json.loads(get_cbs_data("85701NED", {"$filter": "startswith(Regiokenmerken,'GM0106')"}))

    filter_herstel = data.call_args_list[-1].kwargs["$filter"]
    assert filter_herstel.startswith("(Onderwijssoort eq ") and "A025280" not in filter_herstel
    assert sorted(store.get(herstel["data_key"])["Onderwijssoort"]) == ["A025294", "A041867"]


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
    with patch("tools.cbs.data", return_value=_VSV_RIJEN[:2]) as data, patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_data("85368NED", {"$filter": "Onderwijssoort eq 'A042781'"})

    data.assert_not_called()  # de scopegrens ligt vóór de netwerkaanroep (CH-03)
    assert "data_key" not in result
    assert "4000" not in result
    assert "A025290" in result  # de mbo-codes om mee te filteren


def test_vsv_naar_leeftijd_geeft_alleen_de_mbo_rij(catalogus):
    """85367NED (v0.2.1): de dimensie kent alleen totaal, vo, mbo en vavo; de code houdt A025290 over."""
    from tools import store

    rijen = [*_VSV_RIJEN, {"Onderwijssoort": "A025300", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 700}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data("85367NED"))

    assert data.call_args.kwargs["$filter"].startswith("Onderwijssoort eq 'A025290'")
    assert store.get(result["data_key"])["Onderwijssoort"].tolist() == ["A025290"]
    assert "700" not in json.dumps(result)  # vavo valt erbuiten


def test_vsv_naar_leeftijd_met_een_vo_code_wordt_niet_opgehaald(catalogus):
    with patch("tools.cbs.data") as data, patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_data("85367NED", {"$filter": "Onderwijssoort eq 'A042781'"})

    data.assert_not_called()
    assert "data_key" not in result and "A025290" in result


# De CBS-feed gebruikt bij twee clausules op dezelfde dimensie alleen de eerste (live 08-10:
# "(vo) and (mbo)" gaf de vo-rijen, "(mbo) and (vo)" de mbo-rijen). De mbo-selectie gaat dus vooraan.
_MBO_EERST = "(Onderwijssoort eq 'A025290' or "


def test_de_aanroep_van_een_mbo_en_vo_tabel_selecteert_mbo_vooraf(catalogus):
    """CH-03: de mock registreerde call('85368NED', $top=5000) zonder onderwijssoortfilter."""
    with patch("tools.cbs.data", return_value=_VSV_RIJEN) as data, patch("tools.cbs.definitions", return_value={}):
        get_cbs_data("85368NED")
        get_cbs_data("85368NED", {"$filter": "Perioden eq '2023SJ00'"})

    eerste, tweede = (c.kwargs["$filter"] for c in data.call_args_list)
    assert eerste.startswith(_MBO_EERST.removesuffix(" or ").removeprefix("("))
    assert "A042781" not in eerste and "A043837" not in eerste
    assert tweede.startswith(_MBO_EERST) and tweede.endswith(") and Perioden eq '2023SJ00'")


def test_een_mbo_code_van_het_model_versmalt_de_selectie(catalogus):
    """De feed negeert de tweede clausule op Onderwijssoort: de code zet de doorsnede vooraan en filtert erop."""
    from tools import store

    rijen = [*_VSV_RIJEN, {"Onderwijssoort": "A041868", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 3000}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value={}):
        result = json.loads(
            get_cbs_data("85368NED", {"$filter": "Onderwijssoort eq 'A041868' or Onderwijssoort eq 'A042781'"})
        )

    assert data.call_args.kwargs["$filter"].startswith("(Onderwijssoort eq 'A041868') and (")
    assert store.get(result["data_key"])["Onderwijssoort"].tolist() == ["A041868"]


# De CBS-feed geeft HTTP 500 op "(A or B) and (X and Y)": een haakjesgroep met een `and` erin naast de
# sectorgroep (gemeten 15-10-2026 op 85701NED; elke vraag met regio én periode gaf een serverfout).
# "(A or B) and X and Y" en "(A or B) and (X or Y)" geven 200.
def _sectorfilter(eigen: str) -> str:
    """Het $filter dat de sectorselectie van 85701NED om `eigen` bouwt."""
    from tools.scopeprofiel import CbsSectorselectie, cbs_sectorselectie

    selectie = cbs_sectorselectie("85701NED", {"$filter": eigen}, vo_context=False)
    assert isinstance(selectie, CbsSectorselectie)
    return selectie.params["$filter"]


def test_het_modelfilter_komt_zonder_haakjes_achter_de_sectorselectie():
    aanroep = _sectorfilter("trim(Regiokenmerken) eq 'PV26' and trim(Perioden) eq '2024SJ00'")
    assert aanroep.startswith("(Onderwijssoort eq ")
    assert aanroep.endswith(") and trim(Regiokenmerken) eq 'PV26' and trim(Perioden) eq '2024SJ00'")


def test_een_or_op_het_hoogste_niveau_houdt_zijn_haakjes_en_een_gebonden_or_niet():
    los = _sectorfilter("Regiokenmerken eq 'PV26' or Regiokenmerken eq 'PV27'")
    assert los.endswith(") and (Regiokenmerken eq 'PV26' or Regiokenmerken eq 'PV27')")
    # Eén dimensie met meer codes, zoals de compiler schrijft: de or staat al tussen haakjes.
    gebonden = _sectorfilter("(trim(Geslacht) eq '3000' or trim(Geslacht) eq '4000') and trim(Perioden) eq '2024SJ00'")
    assert gebonden.endswith(
        ") and (trim(Geslacht) eq '3000' or trim(Geslacht) eq '4000') and trim(Perioden) eq '2024SJ00'"
    )


def test_een_onbekende_vorm_van_het_sectorfilter_wordt_niet_opgehaald(catalogus):
    with patch("tools.cbs.data") as data:
        result = get_cbs_data("85368NED", {"$filter": "startswith(Onderwijssoort, 'A04')"})

    data.assert_not_called()
    assert "Onderwijssoort eq" in result


def test_select_houdt_de_sectordimensie(catalogus):
    """Zonder Onderwijssoort in $select valt elke rij weg in de controle achteraf."""
    with patch("tools.cbs.data", return_value=_VSV_RIJEN) as data, patch("tools.cbs.definitions", return_value={}):
        get_cbs_data("85368NED", {"$select": "Perioden,VoortijdigSchoolverlaters_1"})

    assert "Onderwijssoort" in data.call_args.kwargs["$select"].split(",")


def test_een_volle_pagina_zonder_mbo_rijen_is_onvolledig_niet_leeg(catalogus):
    """$top=2 met twee rijen buiten scope: de bron kan verder nog mbo-rijen hebben (CH-03, P2)."""
    with patch("tools.cbs.data", return_value=_VSV_RIJEN[:2]), patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_data("85368NED", {"$top": 2})

    assert "data_key" not in result
    assert "onvolledig" in result.lower()
    assert "bevat er geen" not in result


def test_de_snippet_laadt_met_dezelfde_aanroep():
    from tools.snippet import _cbs_laadregels

    regels = _cbs_laadregels({"dataset_id": "85368NED", "filters": {"$filter": "Perioden eq '2023SJ00'"}})

    assert _MBO_EERST in "\n".join(regels)


def test_de_snippet_selecteert_dezelfde_mbo_rijen():
    from tools.snippet import _cbs_laadregels

    regels = _cbs_laadregels({"dataset_id": "85368NED", "filters": {}})

    assert "isin(" in regels[-1] and "A025290" in regels[-1] and "A042781" not in regels[-1]


def test_elke_bronregel_van_een_mbo_en_vo_tabel_noemt_alleen_mbo(catalogus):
    """Audit 17 (CH-45): bij een vo-vraag noemde het antwoord 85368NED als bron, terwijl de chat
    alleen de mbo-rijen laadt. Elke bronregel volgt de selectie die get_cbs_data maakt."""
    from agent.citaties import _bron
    from agent.datasetcontext import _source_label
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


# ── CBS: woonregio over alle onderwijssoorten, de chat laadt mbo/hbo/wo (#473) ──


def test_een_woonregiotabel_geeft_alleen_mbo_hbo_en_wo(catalogus):
    """85701NED is de enige open bron voor hbo/wo-studenten naar woonregio (#452). Hij staat
    ook vol po/vo; die rijen gaan niet de aanroep in en komen niet door de controle erna."""
    from tools import store

    with (
        patch("tools.cbs.data", return_value=_WOONREGIO_RIJEN) as data,
        patch("tools.cbs.definitions", return_value={}),
    ):
        result = json.loads(get_cbs_data("85701NED", {"$filter": "Regiokenmerken eq 'GM0106'"}))

    aanroep = data.call_args.kwargs["$filter"]
    assert aanroep.startswith("(Onderwijssoort eq ") and aanroep.endswith(") and Regiokenmerken eq 'GM0106'")
    assert "A025280" not in aanroep and "T001345" not in aanroep
    assert sorted(store.get(result["data_key"])["Onderwijssoort"]) == ["A025294", "A041867"]


@pytest.mark.parametrize("code", ["T001345", "A025280", "A025300"])  # vo, basisonderwijs, vavo
def test_een_po_of_vo_code_in_een_woonregiotabel_wordt_niet_opgehaald(catalogus, code):
    with patch("tools.cbs.data") as data:
        result = get_cbs_data("85701NED", {"$filter": f"Onderwijssoort eq '{code}'"})

    data.assert_not_called()
    assert "mbo, hbo en wo" in result
    assert "A025294" in result and "A025297" in result  # de codes om mee te filteren


def test_een_volle_pagina_zonder_rijen_in_het_profiel_noemt_het_deel(catalogus):
    with patch("tools.cbs.data", return_value=_WOONREGIO_RIJEN[:2]), patch("tools.cbs.definitions", return_value={}):
        result = get_cbs_data("85701NED", {"$top": 2})

    assert "onvolledig" in result.lower()
    assert "mbo, hbo en wo" in result and "mbo-rijen" not in result


def test_de_bronregel_van_een_woonregiotabel_noemt_het_geladen_deel(catalogus):
    from tools.catalog import bron_naam

    assert bron_naam("85701NED") == f"85701NED ({_CBS_WOONREGIO['bron']}, alleen mbo, hbo en wo)"


@pytest.mark.parametrize(
    ("dataset_id", "hbo", "vo"), [("85701NED", "A025294", "T001345"), ("85702NED", "A043049", "A025285")]
)
def test_de_snippet_van_een_woonregiotabel_selecteert_dezelfde_rijen(dataset_id, hbo, vo):
    from tools.snippet import _cbs_laadregels

    regels = _cbs_laadregels({"dataset_id": dataset_id, "filters": {}})

    assert hbo in regels[-1] and vo not in regels[-1]
    assert regels[-1].endswith("# alleen mbo, hbo en wo")


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
    from onderwijsbronnen.rio import filtercontract

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
    from onderwijsbronnen import catalog
    from onderwijsbronnen.cbs import catalog as cbs_catalog

    return {scopeprofiel.dataset_id(e): e for e in [*cbs_catalog(), *catalog(source="all")]}


def test_in_de_echte_catalogus_valt_geen_duo_bestand_over_po_so_of_vo_binnen_de_grens():
    """Behalve de vo-context voor vervolgonderwijs (#557): voprognoses, alleen vindbaar bij een ho-vraag."""
    toegelaten = [e for e in _echt().values() if scopeprofiel.in_scope(e)]
    po_vo = {"PO", "SO", "VO"}

    assert [
        scopeprofiel.dataset_id(e)
        for e in toegelaten
        if e.get("leverancier") == "DUO" and po_vo & set(e["onderwijstype"])
    ] == ["voprognoses"]
    assert {"p01hoinges", "mbo-studenten-per-instelling", "opleidingserkenningen", "voprognoses"} <= {
        scopeprofiel.dataset_id(e) for e in toegelaten
    }
    assert not {"01voins-v1", "02voins-v1", "06_vomtgo", "pogemeente"} & {
        scopeprofiel.dataset_id(e) for e in toegelaten
    }


def test_in_de_echte_catalogus_valt_geen_gemengde_of_po_vo_cbs_tabel_binnen_de_grens():
    toegelaten = {scopeprofiel.dataset_id(e): e for e in _echt().values() if scopeprofiel.in_scope(e)}
    cbs = {i: e for i, e in toegelaten.items() if e.get("leverancier") == "CBS" or e.get("_cbs_id")}

    # Een tabel die ook over po/vo of alle onderwijssoorten gaat, alleen als de code de rijen
    # voor mbo/hbo/wo selecteert (CBS_SECTORFILTER), met een besluit dat hij alleen over ho gaat,
    # of als vo-context voor vervolgonderwijs (VO_CONTEXT, #557).
    gemengd = {i for i, e in cbs.items() if not set(e.get("onderwijstype") or []) <= scopeprofiel.SECTOREN}
    assert gemengd <= set(scopeprofiel.CBS_SECTORFILTER) | {"71229ned"} | set(scopeprofiel.VO_CONTEXT)
    # De gearchiveerde vo-reeksen blijven erbuiten (#877): pas mee bij een echte vraag.
    assert not {"80040ned", "80041ned", "80042ned", "80043ned", "71215ned"} & set(cbs)
    assert {"85701NED", "85702NED"} <= gemengd  # Assen-replay: toegelaten, met de sectorselectie (#473)
    assert {"85353NED", "85422NED", "85423NED"} <= set(cbs)  # tabellen die de code zelf noemt
    assert {"85367NED", "84312NED"} <= set(cbs)  # package v0.2.1: VSV naar leeftijd (filter) en Caribisch NL mbo
    assert "84312NED" not in gemengd and "85367NED" in gemengd  # Caribisch NL is puur mbo; VSV heeft het sectorfilter
    assert "84732NED" not in cbs  # Caribisch NL po/vo/mbo: één mbo-rij naast po en vo, 84312NED dekt mbo


def test_elk_besluit_in_de_tabel_hoort_bij_een_bestaand_record():
    """Een besluit voor een verdwenen of hernoemd record is dode code."""
    assert set(scopeprofiel.TOEGELATEN) <= set(_echt())


_VSV_DEFS = {
    "Onderwijssoort": {"type": "Dimension", "title": "Onderwijssoort"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "VoortijdigSchoolverlaters_1": {"type": "Topic", "title": "Voortijdig schoolverlaters"},
}


def test_een_gesloten_selectie_op_de_sectordimensie_versmalt_de_selectie(catalogus):
    """De compiler schrijft `trim(Onderwijssoort) eq 'A041868'` (#531); de sectorgrens leest die vorm ook."""
    from tools import store

    rijen = [*_VSV_RIJEN, {"Onderwijssoort": "A041868", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 3000}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value=_VSV_DEFS):
        result = json.loads(
            get_cbs_data("85368NED", selectie={"dimensies": {"Onderwijssoort": "A041868"}, "periode": ["2023/24"]})
        )

    assert data.call_args.kwargs["$filter"].startswith("(Onderwijssoort eq 'A041868') and trim(Onderwijssoort) eq ")
    assert store.get(result["data_key"])["Onderwijssoort"].tolist() == ["A041868"]


def test_een_gesloten_selectie_met_een_vo_code_wordt_niet_opgehaald(catalogus):
    with patch("tools.cbs.data") as data, patch("tools.cbs.definitions", return_value=_VSV_DEFS):
        result = get_cbs_data("85368NED", selectie={"dimensies": {"Onderwijssoort": "A042781"}, "periode": ["2023/24"]})

    data.assert_not_called()
    assert "data_key" not in result and "A025290" in result


# ── Vo-context voor vervolgonderwijs (#555, #557, epic #554, #877) ─────────────
# Een aparte categorie naast TOEGELATEN: binnen het profiel, maar search_catalog toont haar alleen bij een
# vraag over het ho of over doorstroom uit het vo (ho_markers.opent_vo_context), en elke treffer en bronregel
# zegt "vo-context voor vervolgonderwijs".

# De eerste set van #877: lopende CBS-tabellen en recente DUO-bestanden.
_VO_CONTEXT_IDS = (
    "85566NED",
    "85381NED",
    "85382NED",
    "85380NED",
    "85379NED",
    "85534NED",
    "85328NED",
    "85329NED",
    "85948NED",
    "voprognoses",
)
_ETIKET = (
    "vo-context voor vervolgonderwijs: leerlingen in het voortgezet onderwijs (ook vavo en vsv), "
    "geen mbo- of ho-studenten"
)
# Andere vo-, po- en so-records: geen ho-marker opent ze.
_ANDERE_VO = [_CBS_VO, _CBS_VO_DETAIL, _VO_VESTIGING, _VO_INSTELLING, _GEMENGD]


def test_de_vo_contextlijst_noemt_precies_de_eerste_set():
    assert set(scopeprofiel.VO_CONTEXT) == set(_VO_CONTEXT_IDS)


@pytest.mark.parametrize("dataset_id", _VO_CONTEXT_IDS)
def test_elke_ho_contextreden_is_een_zin_over_vo_leerlingen_geen_studenten(dataset_id):
    reden = scopeprofiel.VO_CONTEXT[dataset_id]

    assert reden.strip()
    assert re.search(r"\bvo\b", reden) and "studenten" in reden
    assert not re.search(r"[.!?]\s+\S", reden), "één zin"


def test_de_reden_van_de_doorstroomtabel_noemt_vso():
    """85566NED heet bij CBS 'Vo en vso; doorstroom en uitstroom': de reden stelt vso niet voor als vo."""
    reden = scopeprofiel.VO_CONTEXT["85566NED"]

    assert "vo- en vso-leerlingen" in reden
    assert "vo-leerlingen" not in reden


def test_ho_context_en_toegelaten_delen_geen_id():
    toegelaten = {i.lower() for i in scopeprofiel.TOEGELATEN}

    assert not {i.lower() for i in scopeprofiel.VO_CONTEXT} & toegelaten


@pytest.mark.parametrize(
    "spelling",
    [
        *_VO_CONTEXT_IDS,
        "85566ned",
        "85380ned",
        "cbs:85566NED",
        "cbs_85566ned",
        "VOPROGNOSES",
        "duo:voprognoses",
        _VO,
        _CBS_VO_CONTEXT,
        _CBS_VO_LEERLINGEN,
        {**_CBS_VO_CONTEXT, "_cbs_id": "85566ned"},
    ],
)
def test_een_ho_contextbron_wordt_herkend_in_elke_spelling(spelling):
    assert scopeprofiel.is_vo_context(spelling) is True


@pytest.mark.parametrize(
    "spelling",
    [_CBS_VO, "80040ned", "cbs:80040ned", "02voins-v1", "p01hoinges", "85701NED", _CBS_WOONREGIO, "", {}],
)
def test_een_andere_bron_is_geen_ho_context(spelling):
    assert scopeprofiel.is_vo_context(spelling) is False


@pytest.mark.parametrize("dataset_id", _VO_CONTEXT_IDS)
def test_een_ho_contextbron_valt_binnen_het_profiel(dataset_id):
    """in_scope laat haar toe (#557); de zoekpoort in search_catalog houdt haar uit vragen zonder ho."""
    sleutel = "_ckan_id" if dataset_id == "voprognoses" else "_cbs_id"
    buiten = {"mbo_hbo_wo": "buiten_scope", "reden": "Besluit van riodata."}

    assert scopeprofiel.in_scope({"leverancier": "?", sleutel: dataset_id, "onderwijstype": ["VO"]}) is True
    assert scopeprofiel.in_scope({"leverancier": "?", sleutel: dataset_id}) is True
    assert scopeprofiel.in_scope({"leverancier": "?", sleutel: dataset_id, "_scope": buiten}) is False


def test_elke_ho_contextbron_bestaat_in_de_echte_catalogus():
    """Hoofdletterongevoelig, zoals catalog.bron_id het ID terugvindt."""
    echt = {str(i).lower() for i in _echt()}

    assert {i.lower() for i in scopeprofiel.VO_CONTEXT} <= echt


def test_in_de_echte_catalogus_vallen_precies_de_vo_contextbronnen_binnen_de_grens():
    """Een record alleen over po/so/vo valt erbuiten, behalve die uit VO_CONTEXT; 85948NED is VO+MBO."""
    po_so_vo = {"PO", "SO", "VO"}
    vo = {
        i for i, e in _echt().items() if set(e.get("onderwijstype") or ["?"]) <= po_so_vo and scopeprofiel.in_scope(e)
    }

    assert vo == set(_VO_CONTEXT_IDS) - {"85948NED"}


# De zoekpoort (#557)


def _treffers(resultaat: str) -> list[dict]:
    """De treffers van search_catalog: de kandidaten bij `candidates`; andere uitkomsten hebben er geen."""
    uitkomst = envelop(resultaat)
    if uitkomst["status"] != "candidates":
        return []
    return [t for t in uitkomst["kandidaten"] if scopeprofiel.dataset_id(t)]


def _ids(resultaat: str) -> set[str]:
    return {i for t in _treffers(resultaat) if (i := scopeprofiel.dataset_id(t))}


def _noemt_vo_context(resultaat: str, vraag: str) -> bool:
    """Noemt het resultaat een vo-contextbron: als kandidaat met het etiket, of als suggestie bij needs_clarification.
    Alleen de kandidaten tellen: de zoekterm staat in `gezocht` en `melding` en is geen treffer."""
    ids = {i.lower() for i in _VO_CONTEXT_IDS}
    return any(
        k.get("context") or "vo-context" in k.get("bron", "") or str(k.get("dataset_id", "")).lower() in ids
        for k in treffers(resultaat)
    )


# Geen ho en geen doorstroom uit het vo (#877): de lektest ("Hoeveel mbo-studenten per instelling?"), doorstroom
# zonder vo-niveau, en een losse vo-vraag.
_ZONDER_HO = [
    "per instelling",
    "welke mbo-instellingen krimpen het sterkst richting 2030?",
    "Hoeveel mbo-studenten per instelling?",
    "doorstroom binnen het mbo per niveau",
    "hoeveel leerlingen per niveau in provincie Utrecht?",
    "Hoeveel leerlingen zitten er op het vwo in Utrecht?",
    "vo leerlingen per provincie",
    "prognoses leerlingen per instelling",
]


@pytest.mark.parametrize("vraag", _ZONDER_HO)
def test_zonder_ho_marker_is_geen_vo_contextbron_vindbaar(catalogus, vraag):
    assert not opent_vo_context(vraag)

    assert not _noemt_vo_context(search_catalog(vraag), vraag)
    assert not [k for k in kandidaten(vraag, 15) if scopeprofiel.is_vo_context(k["id"]) or "context" in k]
    assert not {"02voins-v1", "01voins-v1"} & _ids(search_catalog(vraag))


@pytest.mark.parametrize("vraag", _ZONDER_HO)
def test_de_poort_en_niet_de_weging_houdt_ze_buiten(catalogus, vraag):
    """Controle op de vorige test: met een open poort raakt elke vraag wel een vo-contextbron."""
    with patch("tools.ho_markers.noemt_ho", return_value=True):
        assert _noemt_vo_context(search_catalog(vraag), vraag)


@pytest.mark.parametrize(
    "zoekterm",
    ["rio/voprognoses prognoses", "cbs:85566NED doorstroom", "duo:voprognoses instelling", "85380NED leerlingen"],
)
def test_de_poort_beslist_op_het_record_niet_op_een_id_in_de_zoekterm(catalogus, zoekterm):
    """`is_vo_context('rio/voprognoses')` is waar: een poort op de zoekterm van het model zou de bron openen."""
    assert scopeprofiel.is_vo_context(zoekterm.split()[0]) and not opent_vo_context(zoekterm)

    assert not _noemt_vo_context(search_catalog(zoekterm), zoekterm)
    assert not _noemt_vo_context(search_catalog(zoekterm, source="cbs"), zoekterm)
    assert not _noemt_vo_context(search_catalog(zoekterm, source="duo"), zoekterm)


@pytest.mark.parametrize(
    ("vraag", "verwacht"),
    [
        ("doorstroom vwo naar wo", "85566NED"),
        ("Hoeveel havo- en vwo-leerlingen verwacht de prognose tot 2030, als instroom voor hbo en wo?", "voprognoses"),
        ("aansluiting hbo/wo: hoeveel vo-leerlingen per niveau wonen in provincie Utrecht?", "85380NED"),
    ],
)
def test_met_ho_marker_is_de_vo_contextbron_vindbaar_met_etiket(catalogus, vraag, verwacht):
    assert noemt_ho(vraag)

    treffer = next(t for t in _treffers(search_catalog(vraag)) if scopeprofiel.dataset_id(t) == verwacht)
    assert treffer["context"] == _ETIKET


@pytest.mark.parametrize(
    ("vraag", "zoekterm", "verwacht"),
    [
        # Doorstroom uit het vo zonder ho-woord (#877, besluit A): ook naar het mbo.
        ("Hoeveel vmbo-leerlingen stromen door naar het mbo?", "doorstroom vmbo mbo", "85566NED"),
        ("Waar gaan havo-leerlingen heen na hun diploma?", "doorstroom havo", "85566NED"),
        ("Hoeveel vo-leerlingen per niveau wonen in Utrecht, als instroom voor het mbo?", "vo leerlingen", "85380NED"),
    ],
)
def test_een_doorstroomvraag_uit_het_vo_vindt_de_vo_contextbron_met_etiket(catalogus, vraag, zoekterm, verwacht):
    assert not noemt_ho(vraag) and opent_vo_context(vraag)

    with beurtvraag(vraag):
        treffer = next(t for t in _treffers(search_catalog(zoekterm)) if scopeprofiel.dataset_id(t) == verwacht)
    assert treffer["context"] == _ETIKET


# Per richting (#877): een doorstroomvraag vindt een vo-bron met etiket; dezelfde zoekterm bij een losse vo-vraag
# niet. Tegen de echte catalogus, offline, met de zoekterm die het model stuurt en de vraag van de gebruiker.
_RICHTINGEN = {
    "vmbo-mbo": (
        "Hoeveel vmbo-leerlingen zitten er per leerweg in het examenjaar, als instroom in het mbo?",
        "Hoeveel vmbo-leerlingen zitten er per leerweg?",
        "vmbo leerlingen leerweg leerjaar",
        "85379NED",
    ),
    "havo-hbo": (
        "Waar gaan havo-leerlingen heen na hun diploma?",
        "Hoeveel havo-leerlingen halen hun diploma?",
        "havo leerlingen diploma",
        "85534NED",
    ),
    "vwo-wo": (
        "Welk diploma halen vwo-leerlingen uiteindelijk, en hoeveel gaan door naar het wo?",
        "Welk diploma halen vwo-leerlingen uiteindelijk?",
        "vo cohort hoogst behaald diploma",
        "85534NED",
    ),
    "vavo": (
        "Hoeveel deelnemers volgen het vavo als tweede kans op een vervolgopleiding?",
        "Hoeveel deelnemers volgen het vavo?",
        "vavo studenten onderwijssoort",
        "85329NED",
    ),
    "vsv-terugkeer": (
        "Hoeveel voortijdig schoolverlaters keren terug in het onderwijs?",
        "Hoeveel voortijdig schoolverlaters zijn er?",
        "vsv terugkeer onderwijs",
        "85948NED",
    ),
}


def _echte_treffers(vraag: str, zoekterm: str) -> list[dict]:
    from tests.retrieval_baseline import harnas

    with harnas.zonder_netwerk(), harnas.zonder_instellingsregister(), beurtvraag(vraag):
        return _treffers(search_catalog(zoekterm))


@pytest.mark.parametrize("richting", sorted(_RICHTINGEN))
def test_een_doorstroomvraag_per_richting_vindt_een_vo_bron_en_een_losse_vo_vraag_niet(richting):
    open_, dicht, zoekterm, verwacht = _RICHTINGEN[richting]
    assert opent_vo_context(open_) and not opent_vo_context(dicht)

    treffer = next((t for t in _echte_treffers(open_, zoekterm) if scopeprofiel.dataset_id(t) == verwacht), None)
    assert treffer is not None and treffer["context"] == scopeprofiel.VO_CONTEXT_ETIKET
    assert not [t for t in _echte_treffers(dicht, zoekterm) if scopeprofiel.is_vo_context(t) or "context" in t]


# De poort beslist op de vraag van de gebruiker, niet op de zoekterm van het model (#597).
def test_het_model_opent_de_poort_niet_met_een_ho_woord_in_de_zoekterm(catalogus):
    with beurtvraag("Hoeveel leerlingen zitten er op het vwo?"):
        resultaat = search_catalog("vwo leerlingen hbo doorstroom")
    assert not _noemt_vo_context(resultaat, "vwo leerlingen hbo doorstroom")


def test_een_ho_vraag_vindt_de_vo_context_ook_zonder_ho_woord_in_de_zoekterm(catalogus):
    with beurtvraag("Hoeveel vwo-leerlingen stromen door naar het wo?"):
        treffers = _treffers(search_catalog("doorstroom vwo"))
    treffer = next(t for t in treffers if scopeprofiel.dataset_id(t) == "85566NED")
    assert treffer["context"] == _ETIKET


def test_kandidaten_volgt_dezelfde_poort(catalogus):
    met_ho = kandidaten("doorstroom vwo wo", 15)

    assert {"id": "85566NED", "context": _ETIKET}.items() <= next(k for k in met_ho if k["id"] == "85566NED").items()
    assert not [k for k in kandidaten("vo leerlingen per provincie", 15) if scopeprofiel.is_vo_context(k["id"])]


@pytest.mark.parametrize("record", _ANDERE_VO, ids=scopeprofiel.dataset_id)
def test_een_ho_marker_opent_alleen_de_vo_context(catalogus, record):
    dataset_id = scopeprofiel.dataset_id(record)
    vraag = f"{record['bron']} doorstroom naar hbo en wo"
    assert noemt_ho(vraag) and dataset_id

    assert dataset_id not in _ids(search_catalog(vraag))
    assert scopeprofiel.in_scope(record) is False
    assert json.loads(scope_blokkade(dataset_id) or "{}") == scopeprofiel.buiten_scope_voor(record)


def test_de_scopegrens_leest_de_vraag_niet(catalogus):
    """De poort opent alleen het zoeken: in_scope en scope_blokkade kennen geen vraag."""
    fout = AssertionError("de vraag in de scopegrens")
    with (
        patch("tools.ho_markers.noemt_ho", side_effect=fout),
        patch("tools.ho_markers.noemt_vo_doorstroom", side_effect=fout),
        patch("tools.ho_markers.opent_vo_context", side_effect=fout),
    ):
        for record in [_VO, *_CBS_VO_CONTEXT_RECORDS, *_ANDERE_VO]:
            scopeprofiel.in_scope(record)
            scope_blokkade(scopeprofiel.dataset_id(record) or "")


@pytest.mark.parametrize(
    "spelling", ["cbs:85566ned", "85566NED", "85380ned", "cbs_85381NED", "85382NED", "duo:voprognoses", "VOPROGNOSES"]
)
def test_een_directe_id_van_een_vo_contextbron_laadt_zonder_ho_marker(catalogus, spelling):
    assert scope_blokkade(spelling) is None

    with patch("tools.catalog.cbs_meta.metadata", return_value={}):
        details = json.loads(dataset_details(spelling))
    assert "buiten_scope" not in details and "niet gevonden" not in json.dumps(details)


@pytest.mark.parametrize(
    "dataset_id",
    [
        "80040ned",  # gearchiveerde vo-reeks: pas mee bij een echte vraag (#877)
        "37220",  # 'Allen', vanaf 1900
        "01voins-v1",  # DUO-bestand t/m 2019
        "03_voex-v1",
        "06_vomtgo",  # toegestaan vo per vestiging: geen doorstroom
        # Adressen in het vo: in VO_CONTEXT zou elke ho-adresvraag ("Wat is het adres van de Hogeschool Utrecht?")
        # de poort openen via noemt_ho en adressen_vo op rang 3 krijgen (retrieval-baseline hbo-15, kritiek; #877).
        "adressen_vo",
        "leerling_so_en_vso-v1",  # (v)so blijft dicht
        "oordelen-v02",  # inspectieoordelen po/so/vo
    ],
)
def test_een_directe_id_buiten_het_besluit_blijft_dicht_ook_bij_een_doorstroomvraag(dataset_id):
    """Tegen de echte catalogus: de poort opent alleen het zoeken naar VO_CONTEXT, geen ander vo-record (#877)."""
    assert not scopeprofiel.is_vo_context(dataset_id)

    with beurtvraag("Hoeveel vmbo-leerlingen stromen door naar het mbo?"):
        uitkomst = json.loads(scope_blokkade(dataset_id) or "{}")
    assert uitkomst.get("buiten_scope") is True and uitkomst.get("opvraagbaar") is False, uitkomst


def _vergelijkbaar(melding: str) -> str:
    """Het hintdeel van scope_blokkade bij een onbekend ID, zonder het gezochte ID vooraan."""
    return melding.partition("staat niet in de catalogus")[2]


@pytest.mark.parametrize("onbekend", ["vo", "8538", "prognoses", "voprog"])
def test_de_hint_bij_een_onbekend_id_noemt_geen_vo_contextbron(onbekend):
    """De hint is een zoekroute zonder poort en zonder etiket (#573); tegen de echte catalogus."""
    melding = scope_blokkade(onbekend) or ""

    assert "staat niet in de catalogus" in melding
    assert not [i for i in _VO_CONTEXT_IDS if i.lower() in _vergelijkbaar(melding).lower()], melding


def test_de_hint_bij_een_onbekend_id_noemt_wel_andere_datasets():
    assert "studentprognoses-mbo-per-instelling" in (scope_blokkade("prognoses") or "")
    assert "85423NED" in (scope_blokkade("85423") or "")


def test_zonder_vergelijkbare_dataset_verwijst_de_hint_naar_search_catalog():
    """`voprog` raakt alleen voprognoses: na de poort blijft er niets over."""
    melding = scope_blokkade("voprog") or ""

    assert "staat niet in de catalogus" in melding
    assert melding.endswith("Zoek de juiste dataset-ID met search_catalog.")


def test_een_no_match_suggestie_uit_de_vo_context_draagt_het_etiket():
    """De poort laat ze bij een ho-vraag door (#557); dan noemt de suggestie het deel, zoals een bronregel."""
    from tools.catalog import _no_match

    zwak = [
        (2.0, {**_CBS_VO_CONTEXT, "bron": "Doorstroom vo", "context": _ETIKET}),
        (1.0, {"_ckan_id": "voprognoses", "bron": "Prognose leerlingen vo"}),
        (1.5, {**_CBS_MBO, "bron": "Mbo-studenten"}),
    ]
    uitkomst = envelop(_no_match("doorstroom naar hbo", ["doorstroom", "hbo"], zwak, None))

    assert uitkomst["status"] == "needs_clarification"
    suggesties = {k["dataset_id"]: k["bron"] for k in uitkomst["kandidaten"]}
    assert suggesties["85566NED"] == "Doorstroom vo, vo-context voor vervolgonderwijs"
    assert suggesties["voprognoses"] == "Prognose leerlingen vo, vo-context voor vervolgonderwijs"
    assert suggesties["85353NED"] == "Mbo-studenten"


def test_een_vo_contexttreffer_draagt_het_etiket_en_het_catalogusrecord_niet(catalogus):
    vraag = "Hoeveel leerlingen stromen door van vwo naar wo?"
    treffers = _treffers(search_catalog(vraag))
    context = [t for t in treffers if scopeprofiel.is_vo_context(t)]
    gewoon = [t for t in treffers if not scopeprofiel.is_vo_context(t)]

    assert context and all(t["context"] == _ETIKET for t in context)
    assert gewoon and all("context" not in t for t in gewoon)
    assert not [e for e in [*_cbs(), *_rio_duo()] if "context" in e]


# Bronregels (#557): net als 'alleen mbo' bij een gemengde tabel (CH-45)


@pytest.mark.parametrize("dataset_id", [*_VO_CONTEXT_IDS, "cbs:85566ned", "85380ned", "duo:voprognoses"])
def test_de_bronregel_van_een_vo_contextbron_zegt_vo_context_voor_vervolgonderwijs(dataset_id):
    """Tegen de echte catalogus: elke bron uit de eerste set (#877) heeft een titel en het etiket."""
    from tools.catalog import bron_naam, bron_titel

    assert bron_titel(dataset_id).endswith(", vo-context voor vervolgonderwijs")
    assert bron_naam(dataset_id) == f"{dataset_id} ({bron_titel(dataset_id)})"


def test_de_bronregel_van_een_andere_tabel_houdt_haar_deel(catalogus):
    from tools.catalog import bron_naam, bron_titel

    assert bron_titel("85353NED") == _CBS_MBO["bron"]
    assert bron_naam("85368NED") == f"85368NED ({_CBS_VSV['bron']}, alleen mbo)"


def _bronregels(result: dict, dataset_id: str, bron: str, tool: str) -> list[str]:
    from agent.citaties import _bron
    from agent.datasetcontext import _source_label
    from agent.selectie import selectie_in_woorden
    from tools import store
    from tools.catalog import bron_naam

    return [
        result["catalogus_titel"],
        _bron(result["data_key"], tool),
        selectie_in_woorden(result["data_key"]) or "",
        bron_naam(dataset_id),
        _source_label(bron, dataset_id, None),
        store.herkomst(result["data_key"])[0],  # CSV- en grafiekexport
    ]


def test_elke_bronregel_van_een_geladen_vo_contexttabel_noemt_vo_context(catalogus):
    rijen = [{"Onderwijssoort": "A1", "Perioden": "2024SJ00", "Leerlingen_1": 10}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data("cbs:85566ned"))

    data.assert_called_once()  # een directe ID zonder ho-marker passeert de scopegrens
    regels = _bronregels(result, "85566NED", "CBS", "get_cbs_data")
    assert all("vo-context voor vervolgonderwijs" in regel for regel in regels), regels


@pytest.mark.parametrize(
    ("dataset_id", "meetwaarde"),
    [
        ("85379NED", "AantalLeerlingen_1"),
        ("85534NED", "LeerlingenAantal_1"),
        ("85328NED", "GediplomeerdenVavo_1"),
        ("85329NED", "VavoStudenten_1"),
        ("85948NED", "VoortijdigSchoolverlatersVo_2"),
    ],
)
def test_elke_bronregel_van_een_nieuwe_vo_contexttabel_noemt_vo_context(dataset_id, meetwaarde):
    """De CBS-tabellen uit de eerste set van #877, tegen de echte catalogus: een directe ID laadt, en de
    bronregel, de Bronnen, de rapportgrafiek en de kop van de CSV zeggen dat het vo-context is."""
    rijen = [{"Perioden": "2021SJ00", meetwaarde: 10}]
    with patch("tools.cbs.data", return_value=rijen) as data, patch("tools.cbs.definitions", return_value={}):
        result = json.loads(get_cbs_data(dataset_id))

    data.assert_called_once()
    regels = _bronregels(result, dataset_id, "CBS", "get_cbs_data")
    assert all("vo-context voor vervolgonderwijs" in regel for regel in regels), regels


def test_elke_bronregel_van_een_geladen_vo_contextbestand_noemt_vo_context(catalogus):
    import pandas as pd

    with patch("tools.duo._duo.load", return_value=pd.DataFrame({"JAAR": [2030], "AANTAL": [10.5]})) as load:
        result = json.loads(get_duo_data("duo:voprognoses"))

    load.assert_called_once()
    regels = _bronregels(result, "voprognoses", "DUO", "get_duo_data")
    assert all("vo-context voor vervolgonderwijs" in regel for regel in regels), regels


def _vragen_van(records) -> set[str]:
    return {v for e in records for v in e.get("voorbeeldvragen", [])}


@pytest.mark.parametrize("aantal", [4, 1000])  # 1000: elke vraag met een startertag, niet alleen de steekproef
def test_geen_startervraag_komt_uit_een_vo_contextbron(aantal):
    """De startpagina biedt geen pure vo-vraag aan (#557): een startervraag heeft geen ho-vraag achter zich,
    dus de zoekpoort kan haar niet tegenhouden. Tegen de echte catalogus."""
    from routes.instellingen import TAG_STARTERS, tag_voorbeeldvragen

    echt = list(_echt().values())
    context = _vragen_van(e for e in echt if scopeprofiel.is_vo_context(e))
    alleen_context = context - _vragen_van(e for e in echt if not scopeprofiel.is_vo_context(e))
    assert alleen_context, "de vo-contextbronnen hebben eigen voorbeeldvragen, anders toetst deze test niets"

    for label, tags in TAG_STARTERS.items():
        assert not alleen_context & set(tag_voorbeeldvragen(tags, n=aantal)), label


def test_sectorfilters_bestaan_in_het_riodata_contract():
    """De filternaam en de waarden per RIO-register komen uit het contract van riodata (v3: `type`, #627);
    een hernoeming in de RIO-API valt zo hier op in plaats van live met HTTP 400."""
    from onderwijsbronnen.rio import filtercontract

    from tools.scopeprofiel import SECTORFILTER

    for resource, (naam, waarden) in SECTORFILTER.items():
        res = filtercontract()["resources"][resource]
        assert res.get("lijst_endpoint", True), resource
        (filter_,) = [f for f in res["filters"] if f["naam"] == naam]
        assert waarden <= set(filter_["enum"]), resource


# ── Het vo-deel van een bron over meer onderwijssoorten bij een doorstroomvraag (#879, #880) ──

_VSV_DOORSTROOM = "Hoeveel vo-leerlingen worden voortijdig schoolverlater en hoeveel daarvan in het mbo?"
_VSV_MBO = "Hoeveel mbo-studenten verlaten voortijdig de school?"
_VO_DEEL = "vo-context voor vervolgonderwijs"
# _VSV_RIJEN met een vavo-rij: het vo-deel van 85368NED is vmbo/havo/vwo en vavo, niet het totaal over vo en mbo.
_VSV_MET_VAVO = [*_VSV_RIJEN, {"Onderwijssoort": "A025300", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 700}]


def _lading(key: str) -> tuple[bool, dict]:
    """Van een lading `vo_context` en de argumenten van haar herlaadrecept; een test faalt hier als er geen is."""
    from tools import store

    known = store.meta(key)
    assert known is not None and known.laad is not None
    return known.vo_context, known.laad[1]


def _laad_vsv(vraag: str | None, filters: dict | None = None) -> tuple[dict, str]:
    """get_cbs_data op 85368NED in een beurt met `vraag` (None: buiten een beurt); het resultaat en het $filter."""
    from contextlib import nullcontext

    with (
        beurtvraag(vraag) if vraag is not None else nullcontext(),
        patch("tools.cbs.data", return_value=_VSV_MET_VAVO) as data,
        patch("tools.cbs.definitions", return_value={}),
    ):
        result = json.loads(get_cbs_data("85368NED", filters))
    return result, data.call_args.kwargs["$filter"]


def test_een_doorstroomvraag_laadt_de_vo_rijen_met_een_bronregel_die_het_vo_context_noemt(catalogus):
    """Acceptatie #879: de vo- en vavo-rijen komen mee, niet het totaal over vo en mbo samen, en elke bronregel
    (antwoord, Bronnen, citatie, rapportbron, CSV-kop) zegt welk deel geladen is."""
    from agent.figuurbron import figuurbron
    from tools import store

    result, aanroep = _laad_vsv(_VSV_DOORSTROOM)

    assert aanroep.startswith("Onderwijssoort eq 'A025290' or ") and "A042781" in aanroep
    assert "A043837" not in aanroep
    assert sorted(store.get(result["data_key"])["Onderwijssoort"]) == ["A025290", "A025300", "A042781"]
    deel = f"{_CBS_VSV['bron']}, alleen mbo en vo ({_VO_DEEL})"
    grafiek = figuurbron(result["data_key"])
    assert grafiek is not None
    regels = [*_bronregels(result, "85368NED", "CBS", "get_cbs_data")[:3], grafiek["tekst"]]
    assert all(deel in regel for regel in regels), regels
    assert store.herkomst(result["data_key"])[0] == f"bron: CBS, dataset 85368NED, alleen mbo en vo ({_VO_DEEL})"
    assert result["context"] == scopeprofiel.VO_CONTEXT_ETIKET  # vo-leerlingen zijn geen studenten
    assert _lading(result["data_key"])[1]["vo_context"] is True


@pytest.mark.parametrize("vraag", [_VSV_MBO, "Hoeveel hbo-studenten stoppen voortijdig?", None])
def test_zonder_doorstroomvraag_laadt_een_mbo_en_vo_tabel_alleen_de_mbo_rijen(catalogus, vraag):
    """De lektest (#879): een mbo-vraag, een ho-vraag zonder vo-niveau (die opent wel de zoekpoort) en een aanroep
    buiten de chat (MCP) laden de mbo-rijen, met de bronregel van vóór #879."""
    from tools import store

    result, aanroep = _laad_vsv(vraag)

    assert "A042781" not in aanroep and "A025300" not in aanroep
    assert store.get(result["data_key"])["Onderwijssoort"].tolist() == ["A025290"]
    assert result["catalogus_titel"] == f"{_CBS_VSV['bron']}, alleen mbo" and "context" not in result
    assert "vo_context" not in _lading(result["data_key"])[1]


def test_een_eerdere_bronregel_verandert_niet_door_een_latere_beurt(catalogus):
    """Acceptatie #879: het deel staat per lading in de store, niet per tabel. Dezelfde filters in een mbo-beurt
    geven een eigen key; de vo-lading houdt haar rijen en haar bronregel."""
    from agent.selectie import selectie_in_woorden
    from tools import store

    filters = {"$filter": "Perioden eq '2023SJ00'"}
    eerst, _ = _laad_vsv(_VSV_DOORSTROOM, filters)
    regel = selectie_in_woorden(eerst["data_key"]) or ""
    later, _ = _laad_vsv(_VSV_MBO, filters)

    assert later["data_key"] != eerst["data_key"]
    assert selectie_in_woorden(eerst["data_key"]) == regel and _VO_DEEL in regel
    assert _VO_DEEL not in (selectie_in_woorden(later["data_key"]) or "")
    assert "A042781" in store.get(eerst["data_key"])["Onderwijssoort"].tolist()


def test_een_recept_herlaadt_de_vo_lading_in_een_latere_beurt_zonder_doorstroom(catalogus):
    """Het recept onthoudt de poort (#472): na een herstart, in een beurt met een mbo-vraag, komt dezelfde key terug
    met dezelfde rijen en hetzelfde deel."""
    from tools import herlaad, store

    result, _ = _laad_vsv(_VSV_DOORSTROOM)
    key = result["data_key"]
    recept = herlaad.recept(key, {"name": "get_cbs_data", "arguments": {"dataset_id": "85368NED"}})
    store.clear()
    with (
        beurtvraag(_VSV_MBO),
        patch("tools.cbs.data", return_value=_VSV_MET_VAVO),
        patch("tools.cbs.definitions", return_value={}),
    ):
        assert recept is not None and herlaad.herlaad(key, recept).gelukt

    assert sorted(store.get(key)["Onderwijssoort"]) == ["A025290", "A025300", "A042781"]
    assert _lading(key)[0] is True


def test_het_model_opent_de_vo_rijen_niet_zelf(catalogus):
    """Code beslist over de poort (#191): een argument `vo_context` van het model wordt geen aanroep."""
    from tools import dispatch

    with patch("tools.cbs.data") as data:
        tekst, _ = dispatch("get_cbs_data", {"dataset_id": "85368NED", "vo_context": True})

    data.assert_not_called()
    assert "data_key" not in tekst


@pytest.mark.parametrize(("vraag", "vo"), [(_VSV_DOORSTROOM, True), (_VSV_MBO, False)])
def test_de_herstelmelding_noemt_de_vo_codes_alleen_bij_een_doorstroomvraag(catalogus, vraag, vo):
    """Een po-code (geen rijen in het profiel) geeft een melding met de codes om mee te filteren: de vo-codes alleen
    als de poort open is, zodat een herstelpoging de selectie niet verbreedt."""
    with beurtvraag(vraag), patch("tools.cbs.data") as data:
        result = get_cbs_data("85701NED", {"$filter": "Onderwijssoort eq 'A025280'"})

    data.assert_not_called()
    assert ("T001345" in result) is vo and ("vo-context" in result) is vo
    assert "A025280" not in result.split("bevat er geen")[-1]


def test_een_vo_code_van_het_model_versmalt_bij_een_doorstroomvraag_tot_het_vo(catalogus):
    """85367NED kent alleen totalen: met de poort open is 'Vo' te kiezen, en dan is de lading alleen het vo."""
    from tools import store

    rijen = [*_VSV_RIJEN, {"Onderwijssoort": "A025300", "Perioden": "2023SJ00", "VoortijdigSchoolverlaters_1": 700}]
    with (
        beurtvraag(_VSV_DOORSTROOM),
        patch("tools.cbs.data", return_value=rijen) as data,
        patch("tools.cbs.definitions", return_value={}),
    ):
        result = json.loads(get_cbs_data("85367NED", {"$filter": "Onderwijssoort eq 'A042781'"}))

    assert data.call_args.kwargs["$filter"].startswith("(Onderwijssoort eq 'A042781') and ")
    assert store.get(result["data_key"])["Onderwijssoort"].tolist() == ["A042781"]


def test_de_snippet_laadt_de_vo_rijen_zoals_de_lading():
    """De snippet volgt het recept (`vo_context`), en de snippet van de stap volgt de lading, niet de modelargumenten."""
    from tools.snippet import _cbs_laadregels

    regels = _cbs_laadregels({"dataset_id": "85368NED", "filters": {}, "vo_context": True})

    assert "A042781" in regels[-1] and "A043837" not in regels[-1]
    assert regels[-1].endswith(f"# alleen mbo en vo ({_VO_DEEL})")


def test_de_snippet_van_de_stap_laadt_wat_de_app_laadde(catalogus):
    from tools import snippet

    result, _ = _laad_vsv(_VSV_DOORSTROOM)
    code = snippet.generate("get_cbs_data", {"dataset_id": "85368NED"}, json.dumps(result))

    assert code is not None and "A042781" in code and f"# alleen mbo en vo ({_VO_DEEL})" in code


def test_de_bronnen_van_het_rapport_volgen_de_lading(catalogus):
    from agent.datasetcontext import build_recipe, sources_from_recipe

    result, _ = _laad_vsv(_VSV_DOORSTROOM)
    herkomst = [{"name": "get_cbs_data", "arguments": {"dataset_id": "85368NED"}}]
    bronnen = sources_from_recipe(build_recipe([{"data_key": result["data_key"], "herkomst": herkomst}]))

    assert bronnen == [f"CBS — {_CBS_VSV['bron']}, alleen mbo en vo ({_VO_DEEL}) (85368NED)"]


def test_elke_gemengde_cbs_tabel_heeft_vo_codes_buiten_haar_profielcodes():
    """De vo-codes zijn een tweede set naast de mbo/hbo/wo-codes (#879), nooit een totaal of po/(v)so-code
    (live nagelopen op 03-11-2026 tegen de dimensie Onderwijssoort)."""
    gemengd = {"85368NED", "85367NED", "85701NED", "85702NED"}
    for tabel, filter_ in scopeprofiel.CBS_SECTORFILTER.items():
        assert bool(filter_.vo_codes) is (tabel in gemengd), tabel
        assert not filter_.vo_codes & filter_.codes, tabel
        assert not filter_.vo_codes & {"A043837", "A025279", "A025280", "A025281", "A025282", "A049120", "A049121"}


# RIO: de vo- en vavo-typen per register (#880). Een doorstroomvraag die RIO nodig heeft: welke vavo-opleiding een roc
# aanbiedt, de tweedekansroute naar een vo-diploma en daarmee naar vervolgonderwijs. CBS telt vavo-deelnemers, maar
# alleen RIO kent het aanbod.
_VAVO_AANBOD = "Welke vavo-opleidingen bieden roc's in Utrecht aan?"
_MBO_AANBOD = "Welke mbo-opleidingen biedt het ROC van Amsterdam aan?"
_VAVO = {"type": "AANGEBODENVAVOOPLEIDING"}


def _laad_rio(vraag: str | None, filters: dict, resource: str = "aangeboden-opleidingen"):
    from contextlib import nullcontext

    with (
        beurtvraag(vraag) if vraag is not None else nullcontext(),
        patch("tools.rio._filterfout", return_value=None),
        patch("tools.rio.fetch", return_value=[{"eigennaam": "VAVO havo", "type": filters.get("type")}]) as fetch,
    ):
        return get_rio_data(resource, filters), fetch


def test_een_doorstroomvraag_haalt_het_vavo_aanbod_op_met_het_etiket_van_de_vo_context(catalogus):
    from agent.selectie import selectie_in_woorden
    from tools import store

    tekst, fetch = _laad_rio(_VAVO_AANBOD, _VAVO)
    result = json.loads(tekst)

    fetch.assert_called_once()
    assert fetch.call_args.kwargs["type"] == "AANGEBODENVAVOOPLEIDING"
    assert result["catalogus_titel"] == f"{_RIO_SECTORFILTER['bron']}, {_VO_DEEL}"
    assert result["context"] == scopeprofiel.VO_CONTEXT_ETIKET
    assert _VO_DEEL in (selectie_in_woorden(result["data_key"]) or "")
    known = store.meta(result["data_key"])
    assert known is not None
    peilmoment = known.peilmoment  # de stand van het register (#956)
    assert (
        store.herkomst(result["data_key"])[0] == f"bron: RIO, dataset aangeboden-opleidingen, {_VO_DEEL}, {peilmoment}"
    )
    assert _lading(result["data_key"])[1]["vo_context"] is True


@pytest.mark.parametrize("vraag", [_MBO_AANBOD, "Welke hbo-opleidingen biedt de Hogeschool Utrecht aan?", None])
def test_zonder_doorstroomvraag_blijft_een_vo_type_dicht(catalogus, vraag):
    """Ook een directe aanroep (MCP, None) en een ho-vraag zonder vo-niveau openen de vo-records niet (#880)."""
    tekst, fetch = _laad_rio(vraag, {"type": "AANGEBODENVOOPLEIDING"})

    fetch.assert_not_called()
    assert "AANGEBODENMBOOPLEIDING" in tekst and "AANGEBODENVOOPLEIDING" not in tekst


def test_een_mbo_type_in_een_doorstroombeurt_houdt_zijn_bronregel(catalogus):
    tekst, fetch = _laad_rio(_VAVO_AANBOD, {"type": "AANGEBODENMBOOPLEIDING"})
    result = json.loads(tekst)

    fetch.assert_called_once()
    assert result["catalogus_titel"] == _RIO_SECTORFILTER["bron"] and "context" not in result


def test_de_melding_noemt_de_vo_typen_alleen_bij_een_doorstroomvraag(catalogus):
    open_, _ = _laad_rio(_VAVO_AANBOD, {})
    dicht, _ = _laad_rio(_MBO_AANBOD, {})

    assert "AANGEBODENVAVOOPLEIDING" in open_ and _VO_DEEL in open_
    assert "AANGEBODENVAVOOPLEIDING" not in dicht


def test_een_register_zonder_typefilter_blijft_dicht_bij_een_doorstroomvraag(catalogus):
    tekst, fetch = _laad_rio(_VAVO_AANBOD, {"contactadrestype": "BEZOEKNL"}, "contactadressen")

    fetch.assert_not_called()
    assert json.loads(tekst)["buiten_scope"] is True


def test_een_recept_herlaadt_het_vavo_aanbod_in_een_latere_beurt(catalogus):
    from tools import herlaad, store

    tekst, _ = _laad_rio(_VAVO_AANBOD, _VAVO)
    key = json.loads(tekst)["data_key"]
    recept = herlaad.recept(key, {"name": "get_rio_data", "arguments": {"resource": "aangeboden-opleidingen"}})
    store.clear()
    with (
        beurtvraag(_MBO_AANBOD),
        patch("tools.rio._filterfout", return_value=None),
        patch("tools.rio.fetch", return_value=[{"eigennaam": "VAVO havo"}]),
    ):
        assert recept is not None and herlaad.herlaad(key, recept).gelukt

    assert _lading(key)[0] is True


def test_het_model_opent_een_vo_type_niet_zelf(catalogus):
    from tools import dispatch

    with patch("tools.rio.fetch") as fetch:
        tekst, _ = dispatch(
            "get_rio_data", {"resource": "aangeboden-opleidingen", "filters": _VAVO, "vo_context": True}
        )

    fetch.assert_not_called()
    assert "data_key" not in tekst


def test_de_vo_typen_bestaan_in_het_riodata_contract_naast_het_sectorfilter():
    """De namen per register uit het contract (#880); geen mbo/ho-waarde dubbel, en geen po of (v)so."""
    from onderwijsbronnen.rio import filtercontract

    assert set(scopeprofiel.SECTORFILTER_VO_CONTEXT) == set(scopeprofiel.SECTORFILTER)
    for resource, vo_waarden in scopeprofiel.SECTORFILTER_VO_CONTEXT.items():
        naam, waarden = scopeprofiel.SECTORFILTER[resource]
        (filter_,) = [f for f in filtercontract()["resources"][resource]["filters"] if f["naam"] == naam]
        assert vo_waarden <= set(filter_["enum"]), resource
        assert not vo_waarden & waarden, resource
        assert all(re.match(r"(?:AANGEBODEN)?(?:VO|VAVO)", w) for w in vo_waarden), resource  # VSO begint met VS
