"""Nulmeting #909: elke opgeslagen ID-vorm uit `tests/fixtures/bron_id_vormen.json` door de herleiding van nu.

De fixture somt op welke tool-namen, dataset-ID's, DUO-bestanden, store-keys en snippetregels in de opgeslagen
gegevens van test en playground staan (data_recipes, gesprekken, rapporten). Deze test legt vast waar elke vorm nu
naar herleidt: `catalog.bron_id`, `bron_ids.cbs_tabel_id`, `catalog.leverancier` en de scopegrens voor dataset-ID's,
`duo._resource_index` voor DUO-bestanden, `bron_ids.bron_van` voor store-keys, en `herlaad.herlaad` op de bevroren
bronnen van de gouden tests voor recepten. Dat is het referentiepunt voor de verhuizing naar `onderwijsbronnen` (#910)
en het ID-contract (#912): elke vorm levert hetzelfde op met de vlag BRON_ID_CONTRACT op `uit`, `schaduw` en `aan`, en
in `schaduw` telt de chat voor geen enkele vorm een verschil tussen de oude en de nieuwe herleiding. Een nieuwe
opgeslagen vorm hoort eerst in de fixture.
"""

import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import onderwijsbronnen
import pytest

import tools.cbs
from core import config
from scripts import gouden_testfixtures as g
from tools import bron_ids, catalog, duo, herlaad, store
from tools.maten import get_maat
from tools.query import query_data

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "bron_id_vormen.json").read_text(encoding="utf-8"))

_ID_VOORBEELDEN = [
    pytest.param(vorm, v["invoer"], v["dataset"], id=f"{v['invoer']}")
    for vorm in FIXTURE["dataset_ids"]
    for v in vorm["voorbeelden"]
]
_RESOURCE_VOORBEELDEN = [
    pytest.param(v["dataset"], v["invoer"], v["index"], id=f"{v['dataset']}-{v['invoer']}")
    for vorm in FIXTURE["duo_resources"]
    for v in vorm["voorbeelden"]
]
_HERLAAD = FIXTURE["herlaadvoorbeelden"]["recepten"]
_RECEPT_VAN = {r["key"]: r["recept"] for r in _HERLAAD}


@pytest.fixture(params=bron_ids.MODI)
def modus(request, monkeypatch):
    """Elke herleiding onder elke stand van BRON_ID_CONTRACT (#912); in `schaduw` zonder één gelogd verschil."""
    monkeypatch.setattr(config, "BRON_ID_CONTRACT", request.param)
    voor = bron_ids.verschillen()
    yield request.param
    assert bron_ids.verschillen() == voor, "de nieuwe herleiding wijkt af van de oude voor een opgeslagen vorm"


# --- dataset-ID's -----------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("modus")
@pytest.mark.parametrize(("vorm", "invoer", "dataset"), _ID_VOORBEELDEN)
def test_een_opgeslagen_dataset_id_herleidt_naar_zijn_dataset_en_bron(vorm, invoer, dataset):
    assert catalog.bron_id(invoer) == dataset
    assert catalog.leverancier(dataset) == vorm["leverancier"]
    assert (catalog.scope_blokkade(invoer) is None) is vorm["binnen_profiel"]


@pytest.mark.parametrize(
    ("invoer", "dataset"),
    [
        (v["invoer"], v["dataset"])
        for vorm in FIXTURE["dataset_ids"]
        if vorm["leverancier"] == "CBS" or vorm["vorm"].startswith("CBS")
        for v in vorm["voorbeelden"]
    ],
)
@pytest.mark.usefixtures("modus")
def test_een_cbs_id_krijgt_de_spelling_van_de_catalogus(invoer, dataset):
    """`cbs_tabel_id` aan de toolgrens van CBS (#370): 85423NED naast 71733ned, nooit upper()."""
    assert bron_ids.cbs_tabel_id(invoer) == dataset


@pytest.mark.parametrize(("vorm", "invoer", "dataset"), _ID_VOORBEELDEN)
def test_het_contract_kent_elke_opgeslagen_vorm_bij_precies_een_bron(vorm, invoer, dataset):
    """`bron:id` (#912): elke vorm, ook buiten het profiel, wijst naar één bron en de catalogusspelling.

    Een tabel die in geen enkele catalogus staat (`70060ned`), is ook voor het contract onbekend; de chat laat het ID
    dan staan, zoals voorheen.
    """
    if catalog._ruw_record(dataset) is None:
        with pytest.raises(onderwijsbronnen.OnbekendBronId):
            onderwijsbronnen.parse_bron_id(invoer)
        return
    gevonden = onderwijsbronnen.parse_bron_id(invoer)
    assert gevonden.id == dataset
    if vorm["leverancier"]:
        assert gevonden.bron == vorm["leverancier"].lower()
    assert onderwijsbronnen.normaliseer_bron_id(invoer) == str(gevonden)


# --- DUO-bestanden ----------------------------------------------------------------------------------------------------


def _bestanden_uit_de_catalogus(dataset_id: str) -> list[dict]:
    """De bestanden zoals riodata.duo.resources ze geeft, uit de gepinde catalogus in plaats van CKAN."""
    entry = next(e for e in catalog._rio_duo_alles() if catalog._dataset_id(e) == dataset_id)
    return [{"naam": r["naam"], "id": r["id"]} for r in entry["_resources"]]


@pytest.mark.usefixtures("modus")
@pytest.mark.parametrize(("dataset", "invoer", "index"), _RESOURCE_VOORBEELDEN)
def test_een_opgeslagen_duo_bestand_herleidt_naar_zijn_index(dataset, invoer, index):
    with patch.object(duo._duo, "resources", _bestanden_uit_de_catalogus):
        assert duo._resource_index(dataset, invoer) == index


# --- store-keys -------------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("modus")
@pytest.mark.parametrize("vorm", FIXTURE["store_keys"], ids=lambda v: v["voorbeeld"])
def test_een_store_key_zonder_metadata_noemt_zijn_bron_in_het_voorvoegsel(vorm):
    """Na een herstart kent de store een key niet meer: dan beslist het voorvoegsel (ook `analysis`, geen bron)."""
    store.clear()
    assert bron_ids.bron_van(vorm["voorbeeld"]) == vorm["bron"]


# --- recepten ---------------------------------------------------------------------------------------------------------

_LAADFUNCTIES = {naam: functie for naam, (functie, _bron) in herlaad._LADERS.items()}
_AFGELEID = {"query_data": query_data, "get_maat": get_maat}


@pytest.mark.parametrize("vorm", FIXTURE["recepten"]["laad"], ids=lambda v: f"{v['tool']}{v['argumenten']}")
def test_elke_opgeslagen_laadstap_is_een_bekende_lader_met_bekende_argumenten(vorm):
    functie = _LAADFUNCTIES.get(vorm["tool"])
    assert functie is not None, f"{vorm['tool']} staat niet in herlaad._LADERS"
    assert set(vorm["argumenten"]) <= set(inspect.signature(functie).parameters)


@pytest.mark.parametrize("vorm", FIXTURE["recepten"]["afgeleid"], ids=lambda v: f"{v['tool']}{v['argumenten']}")
def test_elke_opgeslagen_afleiding_is_een_bekende_stap_met_bekende_argumenten(vorm):
    functie = _AFGELEID[vorm["tool"]]
    assert set(vorm["argumenten"]) <= set(inspect.signature(functie).parameters)


def test_elke_opgeslagen_maat_bestaat_nog():
    from tools import maten

    assert set(FIXTURE["recepten"]["maten"]) <= set(maten.MATEN)


@pytest.fixture
def bevroren_bronnen(gouden, monkeypatch):
    """De gouden bronnen (#870), plus een RIO-register van één rij: RIO heeft geen gouden fixture."""
    # De gouden CBS-functies zijn lambda's zonder cache_clear; de verversing na de TTL (#864) zou ze legen.
    monkeypatch.setattr(tools.cbs._metadata, "actueel", lambda: None)
    monkeypatch.setattr("tools.rio.fetch", lambda *args, **kwargs: [{"code": "30TX", "naam": "Aeres"}])
    store.clear()
    yield
    store.clear()


@pytest.mark.usefixtures("bevroren_bronnen", "modus")
@pytest.mark.parametrize("voorbeeld", _HERLAAD, ids=lambda v: v["key"])
def test_een_opgeslagen_recept_geeft_dezelfde_key_bron_en_dataset(voorbeeld):
    uit = herlaad.herlaad(voorbeeld["key"], voorbeeld["recept"], _RECEPT_VAN.get)

    assert uit.gelukt, uit.melding
    meta = store.meta(voorbeeld["key"])
    assert meta is not None
    assert (meta.bron, meta.dataset, meta.resource) == (voorbeeld["bron"], voorbeeld["dataset"], voorbeeld["resource"])
    assert bron_ids.bron_van(voorbeeld["key"]) == voorbeeld["bron"]


@pytest.mark.usefixtures("bevroren_bronnen")
@pytest.mark.parametrize("voorbeeld", FIXTURE["herlaadvoorbeelden"]["niet_herlaadbaar"], ids=lambda v: v["key"])
def test_een_eigen_berekening_wordt_niet_herladen(voorbeeld):
    uit = herlaad.herlaad(voorbeeld["key"], voorbeeld["recept"], _RECEPT_VAN.get)
    assert not uit.gelukt
    assert voorbeeld["melding_bevat"] in uit.melding


def test_de_gouden_bronnen_dekken_de_herlaadvoorbeelden():
    """Een voorbeeld op een bestand zonder gouden fixture zou het netwerk op gaan: dan faalt de test, niet stil."""
    duo_bestanden = {g.duo_bestand(r["dataset"], r["resource"]) for r in _HERLAAD if r["bron"] == "duo"}
    assert duo_bestanden <= set(json.loads(g.TEKSTKOLOMMEN.read_text()))
    assert {r["dataset"] for r in _HERLAAD if r["bron"] == "cbs"} <= set(g.CBS_AANROEPEN)


# --- snippets ---------------------------------------------------------------------------------------------------------


def _in_een_schoon_proces(regels: list[str]) -> subprocess.CompletedProcess:
    """Zoals iemand een snippet draait: een eigen interpreter, de importregel bovenaan.

    Niet in dit proces: daar heeft de catalogus het subpakket `onderwijsdata.data` (de datamap) al geïmporteerd, en
    dat overschrijft het attribuut `data` van het pakket. `from onderwijsdata import data` geeft dan de map, niet de
    functie; in een snippet staat de import vóór elke catalogusaanroep, dus daar is het de functie.
    """
    return subprocess.run([sys.executable, "-c", "\n".join(regels)], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("regel", FIXTURE["snippets"]["imports"], ids=lambda r: r["regel"])
def test_elke_opgeslagen_importregel_werkt(regel):
    uit = _in_een_schoon_proces([regel["regel"], f"assert {regel['naam']} is not None"])
    assert uit.returncode == 0, uit.stderr


@pytest.mark.parametrize("aanroep", FIXTURE["snippets"]["aanroepen"], ids=lambda a: a["aanroep"])
def test_elke_opgeslagen_aanroep_bestaat(aanroep):
    module, naam, *rest = aanroep["object"]
    pad = ".".join([naam, *rest])
    uit = _in_een_schoon_proces([f"from {module} import {naam}", f"assert callable({pad}), {pad!r}"])
    assert uit.returncode == 0, uit.stderr


def test_in_een_proces_met_catalogus_is_onderwijsdata_data_de_datamap():
    """De naambotsing hierboven, vastgelegd: een shim of re-export (#910) moet `data` als functie houden."""
    import onderwijsdata

    catalog._cbs_alles()
    assert not callable(importlib.import_module("onderwijsdata").data)
    assert callable(onderwijsdata.client.data)
