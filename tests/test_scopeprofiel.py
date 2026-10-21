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
from tools.ho_markers import beurtvraag, noemt_ho
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
# Een vo-bron uit HO_CONTEXT (#557): binnen het profiel, maar alleen vindbaar bij een vraag die ho noemt.
_VO = {
    "leverancier": "DUO",
    "_ckan_id": "voprognoses",
    "bron": "Prognoses vo per instelling",
    "samenvatting": "Prognose van het aantal leerlingen in het vo per instelling tot 2030.",
    "onderwijstype": ["VO"],
    "tags": ["prognoses", "instelling", "voprognoses"],
}
# Een tweede DUO-bestand over vo, niet in HO_CONTEXT: blijft erbuiten, ook bij een ho-vraag.
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
_CBS_HO_CONTEXT = {
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
_CBS_HO_CONTEXT_RECORDS = [
    _CBS_HO_CONTEXT,
    _CBS_VO_LEERLINGEN,
    {**_CBS_VO_LEERLINGEN, "_cbs_id": "85381NED", "bron": "Vo; examenkandidaten en gediplomeerden, onderwijssoort"},
    {**_CBS_VO_LEERLINGEN, "_cbs_id": "85382NED", "bron": "Vo; examenkandidaten en gediplomeerden, woonregio"},
]
# Vo-leerlingen naar woonregio, niet in HO_CONTEXT: dezelfde woorden als 85380NED, maar blijft erbuiten.
_CBS_VO_DETAIL = {
    "leverancier": "CBS",
    "_cbs_id": "85379NED",
    "bron": "Vo; leerlingen, onderwijssoort in detail, leerjaar, herkomst",
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
        (_VO, True),  # vo-context voor ho (#557): de zoekpoort, niet in_scope, houdt hem uit gewone vragen
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
        *_CBS_HO_CONTEXT_RECORDS,
    ]
    with (
        patch("tools.catalog._cbs_catalog", return_value=cbs),
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
    assert "02voins-v1" not in result


def test_de_telling_volgt_de_grens(catalogus):
    """De vijf vo-contextbronnen tellen mee (#557): vier CBS-tabellen en voprognoses."""
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

    selectie = cbs_sectorselectie("85701NED", {"$filter": eigen})
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
    """Behalve de vo-context voor ho (#557): voprognoses, alleen vindbaar bij een ho-vraag."""
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
    # of als vo-context voor ho (HO_CONTEXT, #557).
    gemengd = {i for i, e in cbs.items() if not set(e.get("onderwijstype") or []) <= scopeprofiel.SECTOREN}
    assert gemengd <= set(scopeprofiel.CBS_SECTORFILTER) | {"71229ned"} | set(scopeprofiel.HO_CONTEXT)
    assert not {"80040ned", "85379NED", "85534NED"} & set(cbs)  # andere vo-tabellen blijven erbuiten
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


# ── Vo-context voor ho-vragen (#555, #557, epic #554) ──────────────────────────
# Een aparte categorie naast TOEGELATEN: binnen het profiel, maar search_catalog toont haar alleen bij een
# vraag die ho noemt (ho_markers.noemt_ho), en elke treffer en bronregel zegt "vo-context voor ho".

_HO_CONTEXT_IDS = ("85566NED", "85381NED", "85382NED", "85380NED", "voprognoses")
_ETIKET = "vo-context voor ho: leerlingen in het voortgezet onderwijs, geen studenten"
# Andere vo-, po- en so-records: geen ho-marker opent ze.
_ANDERE_VO = [_CBS_VO, _CBS_VO_DETAIL, _VO_VESTIGING, _VO_INSTELLING, _GEMENGD]


def test_de_ho_contextlijst_noemt_precies_de_vijf_vo_bronnen():
    assert set(scopeprofiel.HO_CONTEXT) == set(_HO_CONTEXT_IDS)


@pytest.mark.parametrize("dataset_id", _HO_CONTEXT_IDS)
def test_elke_ho_contextreden_is_een_zin_over_vo_leerlingen_geen_studenten(dataset_id):
    reden = scopeprofiel.HO_CONTEXT[dataset_id]

    assert reden.strip()
    assert re.search(r"\bvo\b", reden) and "studenten" in reden
    assert not re.search(r"[.!?]\s+\S", reden), "één zin"


def test_de_reden_van_de_doorstroomtabel_noemt_vso():
    """85566NED heet bij CBS 'Vo en vso; doorstroom en uitstroom': de reden stelt vso niet voor als vo."""
    reden = scopeprofiel.HO_CONTEXT["85566NED"]

    assert "vo- en vso-leerlingen" in reden
    assert "vo-leerlingen" not in reden


def test_ho_context_en_toegelaten_delen_geen_id():
    toegelaten = {i.lower() for i in scopeprofiel.TOEGELATEN}

    assert not {i.lower() for i in scopeprofiel.HO_CONTEXT} & toegelaten


@pytest.mark.parametrize(
    "spelling",
    [
        *_HO_CONTEXT_IDS,
        "85566ned",
        "85380ned",
        "cbs:85566NED",
        "cbs_85566ned",
        "VOPROGNOSES",
        "duo:voprognoses",
        _VO,
        _CBS_HO_CONTEXT,
        _CBS_VO_LEERLINGEN,
        {**_CBS_HO_CONTEXT, "_cbs_id": "85566ned"},
    ],
)
def test_een_ho_contextbron_wordt_herkend_in_elke_spelling(spelling):
    assert scopeprofiel.is_ho_context(spelling) is True


@pytest.mark.parametrize(
    "spelling",
    [_CBS_VO, "80040ned", "cbs:80040ned", "02voins-v1", "p01hoinges", "85701NED", _CBS_WOONREGIO, "", {}],
)
def test_een_andere_bron_is_geen_ho_context(spelling):
    assert scopeprofiel.is_ho_context(spelling) is False


@pytest.mark.parametrize("dataset_id", _HO_CONTEXT_IDS)
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

    assert {i.lower() for i in scopeprofiel.HO_CONTEXT} <= echt


def test_in_de_echte_catalogus_vallen_precies_de_vijf_vo_contextbronnen_binnen_de_grens():
    """Een record alleen over po/so/vo valt erbuiten, behalve de vijf uit HO_CONTEXT."""
    po_so_vo = {"PO", "SO", "VO"}
    vo = {
        i for i, e in _echt().items() if set(e.get("onderwijstype") or ["?"]) <= po_so_vo and scopeprofiel.in_scope(e)
    }

    assert vo == set(_HO_CONTEXT_IDS)


# De zoekpoort (#557)


def _treffers(resultaat: str) -> list[dict]:
    """De treffers van search_catalog; een melding (no_match) heeft er geen."""
    try:
        lijst = json.loads(resultaat)
    except ValueError:
        return []
    return [t for t in lijst if scopeprofiel.dataset_id(t)]


def _ids(resultaat: str) -> set[str]:
    return {i for t in _treffers(resultaat) if (i := scopeprofiel.dataset_id(t))}


def _noemt_vo_context(resultaat: str, vraag: str) -> bool:
    """Noemt het resultaat een vo-contextbron: als treffer, met het etiket of als suggestie bij no_match.
    De zoekterm zelf staat in een no_match-melding en telt niet."""
    tekst = resultaat.replace(vraag, "").lower()
    return "vo-context" in tekst or any(i.lower() in tekst for i in _HO_CONTEXT_IDS)


_ZONDER_HO = [
    "per instelling",
    "welke mbo-instellingen krimpen het sterkst richting 2030?",
    "hoeveel leerlingen per niveau in provincie Utrecht?",
    "doorstroom vo leerlingen",
    "prognoses leerlingen per instelling",
]


@pytest.mark.parametrize("vraag", _ZONDER_HO)
def test_zonder_ho_marker_is_geen_vo_contextbron_vindbaar(catalogus, vraag):
    assert not noemt_ho(vraag)

    assert not _noemt_vo_context(search_catalog(vraag), vraag)
    assert not [k for k in kandidaten(vraag, 15) if scopeprofiel.is_ho_context(k["id"]) or "context" in k]
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
    """`is_ho_context('rio/voprognoses')` is waar: een poort op de zoekterm van het model zou de bron openen."""
    assert scopeprofiel.is_ho_context(zoekterm.split()[0]) and not noemt_ho(zoekterm)

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
    assert not [k for k in kandidaten("doorstroom vo leerlingen", 15) if scopeprofiel.is_ho_context(k["id"])]


@pytest.mark.parametrize("record", _ANDERE_VO, ids=scopeprofiel.dataset_id)
def test_een_ho_marker_opent_alleen_de_vo_context(catalogus, record):
    dataset_id = scopeprofiel.dataset_id(record)
    vraag = f"{record['bron']} doorstroom naar hbo en wo"
    assert noemt_ho(vraag) and dataset_id

    assert dataset_id not in _ids(search_catalog(vraag))
    assert scopeprofiel.in_scope(record) is False
    assert json.loads(scope_blokkade(dataset_id) or "{}") == scopeprofiel.buiten_scope_voor(record)


def test_de_scopegrens_leest_de_vraag_niet(catalogus):
    """noemt_ho opent alleen het zoeken: in_scope en scope_blokkade kennen geen vraag."""
    with patch("tools.ho_markers.noemt_ho", side_effect=AssertionError("noemt_ho in de scopegrens")):
        for record in [_VO, *_CBS_HO_CONTEXT_RECORDS, *_ANDERE_VO]:
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


def _vergelijkbaar(melding: str) -> str:
    """Het hintdeel van scope_blokkade bij een onbekend ID, zonder het gezochte ID vooraan."""
    return melding.partition("staat niet in de catalogus")[2]


@pytest.mark.parametrize("onbekend", ["vo", "8538", "prognoses", "voprog"])
def test_de_hint_bij_een_onbekend_id_noemt_geen_vo_contextbron(onbekend):
    """De hint is een zoekroute zonder poort en zonder etiket (#573); tegen de echte catalogus."""
    melding = scope_blokkade(onbekend) or ""

    assert "staat niet in de catalogus" in melding
    assert not [i for i in _HO_CONTEXT_IDS if i.lower() in _vergelijkbaar(melding).lower()], melding


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
        (2.0, {**_CBS_HO_CONTEXT, "bron": "Doorstroom vo", "context": _ETIKET}),
        (1.0, {"_ckan_id": "voprognoses", "bron": "Prognose leerlingen vo"}),
        (1.5, {**_CBS_MBO, "bron": "Mbo-studenten"}),
    ]
    melding = _no_match("doorstroom naar hbo", zwak, None)

    assert "85566NED (Doorstroom vo, vo-context voor ho)" in melding
    assert "voprognoses (Prognose leerlingen vo, vo-context voor ho)" in melding
    assert "85353NED (Mbo-studenten)," in melding


def test_een_vo_contexttreffer_draagt_het_etiket_en_het_catalogusrecord_niet(catalogus):
    vraag = "Hoeveel leerlingen stromen door van vwo naar wo?"
    treffers = _treffers(search_catalog(vraag))
    context = [t for t in treffers if scopeprofiel.is_ho_context(t)]
    gewoon = [t for t in treffers if not scopeprofiel.is_ho_context(t)]

    assert context and all(t["context"] == _ETIKET for t in context)
    assert gewoon and all("context" not in t for t in gewoon)
    assert not [e for e in [*_cbs(), *_rio_duo()] if "context" in e]


# Bronregels (#557): net als 'alleen mbo' bij een gemengde tabel (CH-45)


@pytest.mark.parametrize("dataset_id", [*_HO_CONTEXT_IDS, "cbs:85566ned", "85380ned", "duo:voprognoses"])
def test_de_bronregel_van_een_vo_contextbron_zegt_vo_context_voor_ho(catalogus, dataset_id):
    from tools.catalog import bron_naam, bron_titel

    assert bron_titel(dataset_id).endswith(", vo-context voor ho")
    assert bron_naam(dataset_id) == f"{dataset_id} ({bron_titel(dataset_id)})"


def test_de_bronregel_van_een_andere_tabel_houdt_haar_deel(catalogus):
    from tools.catalog import bron_naam, bron_titel

    assert bron_titel("85353NED") == _CBS_MBO["bron"]
    assert bron_naam("85368NED") == f"85368NED ({_CBS_VSV['bron']}, alleen mbo)"


def _bronregels(result: dict, dataset_id: str, bron: str, tool: str) -> list[str]:
    from agent.citaties import _bron
    from agent.dashboard import _source_label
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
    assert all("vo-context voor ho" in regel for regel in regels), regels


def test_elke_bronregel_van_een_geladen_vo_contextbestand_noemt_vo_context(catalogus):
    import pandas as pd

    with patch("tools.duo._duo.load", return_value=pd.DataFrame({"JAAR": [2030], "AANTAL": [10.5]})) as load:
        result = json.loads(get_duo_data("duo:voprognoses"))

    load.assert_called_once()
    regels = _bronregels(result, "voprognoses", "DUO", "get_duo_data")
    assert all("vo-context voor ho" in regel for regel in regels), regels


def _vragen_van(records) -> set[str]:
    return {v for e in records for v in e.get("voorbeeldvragen", [])}


@pytest.mark.parametrize("aantal", [4, 1000])  # 1000: elke vraag met een startertag, niet alleen de steekproef
def test_geen_startervraag_komt_uit_een_vo_contextbron(aantal):
    """De startpagina biedt geen pure vo-vraag aan (#557): een startervraag heeft geen ho-vraag achter zich,
    dus de zoekpoort kan haar niet tegenhouden. Tegen de echte catalogus."""
    from routes.instellingen import TAG_STARTERS, tag_voorbeeldvragen

    echt = list(_echt().values())
    context = _vragen_van(e for e in echt if scopeprofiel.is_ho_context(e))
    alleen_context = context - _vragen_van(e for e in echt if not scopeprofiel.is_ho_context(e))
    assert alleen_context, "de vo-contextbronnen hebben eigen voorbeeldvragen, anders toetst deze test niets"

    for label, tags in TAG_STARTERS.items():
        assert not alleen_context & set(tag_voorbeeldvragen(tags, n=aantal)), label


def test_sectorfilters_bestaan_in_het_riodata_contract():
    """De filternaam en de waarden per RIO-register komen uit het contract van riodata (v3: `type`, #627);
    een hernoeming in de RIO-API valt zo hier op in plaats van live met HTTP 400."""
    from riodata import filtercontract

    from tools.scopeprofiel import SECTORFILTER

    for resource, (naam, waarden) in SECTORFILTER.items():
        res = filtercontract()["resources"][resource]
        assert res.get("lijst_endpoint", True), resource
        (filter_,) = [f for f in res["filters"] if f["naam"] == naam]
        assert waarden <= set(filter_["enum"]), resource
