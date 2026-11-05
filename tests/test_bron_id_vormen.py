"""Nulmeting #909: elke opgeslagen ID-vorm uit `tests/fixtures/bron_id_vormen.json` door de herleiding van nu.

De fixture somt op welke tool-namen, dataset-ID's, DUO-bestanden, store-keys en snippetregels in de opgeslagen
gegevens van test en playground staan (data_recipes, gesprekken, rapporten). Deze test legt vast waar elke vorm nu
naar herleidt: `catalog.bron_id`, `bron_ids.cbs_tabel_id`, `catalog.leverancier` en de scopegrens voor dataset-ID's,
`duo._resource_index` voor DUO-bestanden, `bron_ids.bron_van` voor store-keys, en `herlaad.herlaad` op de bevroren
bronnen van de gouden tests voor recepten. Sinds #914 is het ID-contract `bron:id` (#912) het enige pad: elke oude
vorm is daar een alias en levert dezelfde bron, dataset en hetzelfde bestand op als vóór de overgang. Een nieuwe
opgeslagen vorm hoort eerst in de fixture.
"""

import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import onderwijsbronnen
import pytest

import tools.cbs
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


# --- dataset-ID's -----------------------------------------------------------------------------------------------------


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
    """De bestanden zoals onderwijsbronnen.duo.resources ze geeft, uit de gepinde catalogus in plaats van CKAN."""
    entry = next(e for e in catalog._rio_duo_alles() if catalog._dataset_id(e) == dataset_id)
    return [{"naam": r["naam"], "id": r["id"]} for r in entry["_resources"]]


@pytest.mark.parametrize(("dataset", "invoer", "index"), _RESOURCE_VOORBEELDEN)
def test_een_opgeslagen_duo_bestand_herleidt_naar_zijn_index(dataset, invoer, index):
    with patch.object(duo._duo, "resources", _bestanden_uit_de_catalogus):
        assert duo._resource_index(dataset, invoer) == index


# --- store-keys -------------------------------------------------------------------------------------------------------


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


@pytest.mark.usefixtures("bevroren_bronnen")
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
#
# Een opgeslagen snippet importeert `riodata` of `onderwijsdata`, de pakketnamen van vóór #910. Sinds #914 bestaan die
# namen in deze installatie niet meer (de shims zijn weg): een oude snippet draait tegen zijn eigen installatie. Sinds
# #714/#888 noemt de kop die zelf, met de commit (de vier installatievormen in de fixture); een snippet van daarvóór
# noemt er geen en hoort bij de oude pakketrepo's, die gearchiveerd blijven bestaan (#889). Dat die installaties de
# opgeslagen regels nog draaien, toont `test_een_oude_snippet_draait_tegen_zijn_eigen_installatie` (live: netwerk).

# Per repo in de installatievormen een commit waarmee opgeslagen snippets zijn gemaakt.
_OUDE_COMMIT = {
    "rio-onderwijsdata.git": "21c37577fccb8bf2586eeb069b5925fbb2257d40",  # riodata 0.7.0, de pin van playground 2.5.2
    "cbs-onderwijsdata.git": "6ada0b0813f051440c9674c1eae7160e1651e11a",  # onderwijsdata 0.2.2 (tag v0.2.2)
    "onderwijsdata-chat": "4688c4c8d573973a3c637897ec481dff8a54ed36",  # release 2.6.0, de laatste vóór #910
}
# Een snippet zonder kop (vóór #714): de oude repo zoals hij gearchiveerd is.
_OUDE_REPO = {
    "riodata": "https://github.com/cedanl/rio-onderwijsdata.git",
    "onderwijsdata": "https://github.com/cedanl/cbs-onderwijsdata.git",
}
_OUDE_MODULES = {r["module"] for r in FIXTURE["snippets"]["imports"]} | {
    a["object"][0] for a in FIXTURE["snippets"]["aanroepen"]
}


def _module_van(vorm: str) -> str:
    """Welke oude pakketnaam een installatievorm levert."""
    return "riodata" if "riodata" in vorm or "rio-onderwijsdata" in vorm else "onderwijsdata"


def _repo_van(vorm: str) -> str | None:
    return next((repo for repo in _OUDE_COMMIT if repo in vorm), None)


def _installaties() -> list:
    """(module, pip-spec) per installatievorm uit de fixture met een echte commit, plus elke oude repo zonder pin."""
    met_kop = [
        pytest.param(_module_van(r["vorm"]), r["vorm"].replace("<sha>", _OUDE_COMMIT[repo]), id=r["vorm"])
        for r in FIXTURE["snippets"]["installatieregels"]
        if (repo := _repo_van(r["vorm"]))
    ]
    zonder_kop = [pytest.param(m, f"{m} @ git+{url}", id=f"{m} zonder kop") for m, url in _OUDE_REPO.items()]
    return met_kop + zonder_kop


def _snippetregels(module: str) -> list[str]:
    """De opgeslagen importregels en aanroepen van één oude pakketnaam, zoals een snippet ze draait."""
    regels = [r["regel"] for r in FIXTURE["snippets"]["imports"] if r["module"] == module]
    for a in FIXTURE["snippets"]["aanroepen"]:
        if a["object"][0] == module:
            pad = ".".join(a["object"][1:])
            regels.append(f"assert callable({pad}), {pad!r}")
    return regels


def test_elke_installatievorm_heeft_een_commit_en_elke_oude_naam_een_installatie():
    """Een nieuwe vorm in de fixture zonder commit hier, of een oude naam zonder installatie, valt hier op."""
    vormen = [r["vorm"] for r in FIXTURE["snippets"]["installatieregels"]]
    assert all(_repo_van(v) for v in vormen), vormen
    assert _OUDE_MODULES <= {_module_van(v) for v in vormen} <= set(_OUDE_REPO)


@pytest.mark.parametrize("module", sorted(_OUDE_MODULES))
def test_de_oude_pakketnaam_bestaat_hier_niet_meer(module):
    """De shims van #910 zijn weg (#914): een oude snippet hoort bij zijn eigen installatie, niet bij deze.

    Een lege map van een oude checkout (alleen `__pycache__`) is hooguit een namespace-pakket zonder code.
    """
    spec = importlib.util.find_spec(module)
    assert spec is None or spec.origin is None, spec


@pytest.mark.live
@pytest.mark.parametrize(("module", "spec"), _installaties())
def test_een_oude_snippet_draait_tegen_zijn_eigen_installatie(module, spec, tmp_path):
    """De opgeslagen importregels en aanroepen, in een eigen venv met de installatie die de snippet noemt."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv ontbreekt")
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "-q", "--python", sys.executable, str(venv)], check=True, timeout=120)
    python = str(venv / "bin" / "python")
    installatie = subprocess.run(
        [uv, "pip", "install", "-q", "--python", python, spec], capture_output=True, text=True, timeout=600
    )
    assert installatie.returncode == 0, installatie.stderr
    uit = subprocess.run(
        [python, "-I", "-c", "\n".join(_snippetregels(module))], capture_output=True, text=True, timeout=120
    )
    assert uit.returncode == 0, uit.stderr


def _in_een_schoon_proces(regels: list[str]) -> subprocess.CompletedProcess:
    """Zoals iemand een snippet draait: een eigen interpreter, de importregel bovenaan.

    Niet in dit proces: daar heeft de catalogus het subpakket `onderwijsbronnen.cbs.data` (de datamap) al
    geïmporteerd, en dat overschrijft het attribuut `data` van `onderwijsbronnen.cbs`. In een snippet staat de import
    vóór elke catalogusaanroep, dus daar is `data` de functie.
    """
    return subprocess.run([sys.executable, "-c", "\n".join(regels)], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize(
    "regels",
    [
        ["from onderwijsbronnen import duo, roa, uwv", "assert callable(duo.load) and callable(roa.load)"],
        ["from onderwijsbronnen.cbs import data", "assert callable(data)"],
        ["from onderwijsbronnen.rio import fetch", "assert callable(fetch)"],
    ],
    ids=lambda r: r[0],
)
def test_de_importregels_van_een_nieuwe_snippet_werken_in_een_schoon_proces(regels):
    uit = _in_een_schoon_proces(regels)
    assert uit.returncode == 0, uit.stderr


def test_in_een_proces_met_catalogus_is_cbs_data_de_datamap():
    """De naambotsing hierboven, vastgelegd: `cbs.client.data` is altijd de functie."""
    from onderwijsbronnen import cbs

    catalog._cbs_alles()
    assert not callable(cbs.data)
    assert callable(cbs.client.data)
