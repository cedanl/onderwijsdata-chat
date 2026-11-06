"""Eén bron van waarheid voor de bronnen die van de omgeving afhangen (#956): tools/beschikbaarheid.py.

De financiën van DUO geven alleen cijfers waar de licentie het toelaat (tot de bevestiging lokaal en op test), WOPI alleen
met de vlag ENABLE_WO_PERSONEEL. /api/config, search_catalog, dataset_details, de tellingen en de tool zelf volgen
dezelfde regel; hier beide standen, met monkeypatch.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.datasetcontext import build_recipe, sources_from_recipe
from core import config
from routes import config as config_route
from tests.test_financien import _BESTUUR, _DATA, _PROFIELEN
from tools import beschikbaarheid, catalog, fusies
from tools import financien as fin
from tools.schemas import TOOL_GET_BESTUURSFINANCIEN, TOOL_GET_WO_PERSONEEL


@pytest.fixture(autouse=True)
def financien(monkeypatch):
    monkeypatch.setattr(fin.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower()))
    monkeypatch.setattr(fin, "bestuur_van", lambda code: _BESTUUR.get(code))
    monkeypatch.setattr(fin, "_bron", lambda: _DATA)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: ())


@pytest.fixture
def omgeving(monkeypatch):
    """Zet de vlag van WOPI en de omgeving (licentie van de financiën) en lees de catalogus opnieuw: de catalogus leest
    de vlag één keer per proces (tools/catalog.py, _TOOLBRONNEN)."""

    def zet(*, wopi: bool, app_env: str = "test", licentie: bool = False) -> None:
        monkeypatch.setattr(config, "WO_PERSONEEL_ENABLED", wopi)
        monkeypatch.setattr(beschikbaarheid.Config, "APP_ENV", app_env)
        monkeypatch.setattr(beschikbaarheid, "LICENTIE_BEVESTIGD", licentie)
        _wis_catalogus()

    yield zet
    monkeypatch.undo()
    _wis_catalogus()


def _wis_catalogus() -> None:
    for gecached in (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest):
        gecached.cache_clear()


def _wis_catalogus() -> None:
    for gecached in (catalog._rio_duo_alles, catalog._rio_duo, catalog.catalogus_digest):
        gecached.cache_clear()


def test_tool_volgt_de_regel():
    assert beschikbaarheid.tool("search_catalog") is True


@pytest.mark.parametrize(("app_env", "bevestigd", "verwacht"), [
    ("local", False, True), ("test", False, True), ("playground", False, False), ("production", False, False),
    ("production", True, True),
])  # fmt: skip
def test_de_financien_volgen_omgeving_en_licentie(monkeypatch, app_env, bevestigd, verwacht):
    monkeypatch.setattr(beschikbaarheid.Config, "APP_ENV", app_env)
    monkeypatch.setattr(beschikbaarheid, "LICENTIE_BEVESTIGD", bevestigd)
    assert beschikbaarheid.financien() is verwacht
    assert beschikbaarheid.tool(TOOL_GET_BESTUURSFINANCIEN) is verwacht
    assert beschikbaarheid.bronnen()["financien"] is verwacht


@pytest.mark.parametrize("vlag", [True, False])
def test_wopi_volgt_de_vlag(monkeypatch, vlag):
    monkeypatch.setattr(config, "WO_PERSONEEL_ENABLED", vlag)
    assert beschikbaarheid.tool(TOOL_GET_WO_PERSONEEL) is vlag
    assert beschikbaarheid.bronnen()["wo_personeel"] is vlag


def test_met_de_vlag_noemt_het_rapport_de_titel_van_wopi(omgeving):
    omgeving(wopi=True)
    datasets = [{"data_key": "wopi:landelijk", "herkomst": [{"name": TOOL_GET_WO_PERSONEEL, "arguments": {}}]}]
    assert sources_from_recipe(build_recipe(datasets)) == ["UNL — WOPI-personeelsbestand (wo) (unl:wopi)"]


# --- één bron van waarheid: /api/config, catalogus en tellingen ----------------------------------------------------


def _config() -> dict:
    app = FastAPI()
    app.include_router(config_route.router)
    client = TestClient(app)
    return {"config": client.get("/api/config").json(), "counts": client.get("/api/catalog/counts").json()}


def _zoek(vraag: str) -> list[tuple[str, str]]:
    uit = json.loads(catalog.search_catalog(vraag))
    return [(k["dataset_id"], k.get("status")) for k in uit.get("kandidaten", [])]


def test_op_test_geven_beide_bronnen_antwoord_en_vindt_de_catalogus_ze_als_via_tool(omgeving):
    omgeving(wopi=True, app_env="test")
    antwoord = _config()
    assert antwoord["config"]["bronnen"] == {"financien": True, "wo_personeel": True}
    assert ("wopi", "via_tool") in _zoek("wetenschappelijk personeel universiteit")
    assert ("financien", "via_tool") in _zoek("financien bestuur solvabiliteit")
    details = json.loads(catalog.dataset_details("unl:wopi"))
    assert (details["status"], details["via_tool"]) == ("via_tool", TOOL_GET_WO_PERSONEEL)
    # De tellingen volgen wat search_catalog vindt: UNL telt mee, de financiën bij DUO; de docs-telling niet.
    assert catalog.via_tool_aantallen() == {"DUO": 1, "UWV": 1, "ROA": 1, "UNL": 1}
    assert antwoord["counts"] == catalog.catalogus_aantallen()
    assert antwoord["counts"]["DUO"] == catalog.dataset_counts()["DUO"] + 1
    assert json.loads(catalog.catalogus_telling())["via_eigen_tool"]["UNL"] == 1


def test_op_playground_geven_de_financien_cijfers_zodra_de_licentie_geldt(omgeving):
    omgeving(wopi=False, app_env="playground", licentie=True)
    assert _config()["config"]["bronnen"] == {"financien": True, "wo_personeel": False}
    assert ("financien", "via_tool") in _zoek("financien bestuur solvabiliteit")


def test_de_licentie_van_de_financien_geldt_als_bevestigd():
    assert beschikbaarheid.LICENTIE_BEVESTIGD is True  # CC0 van DUO; False zet de financiën weer terug naar test


def test_op_playground_zonder_vlag_geeft_geen_van_beide_cijfers(omgeving):
    omgeving(wopi=False, app_env="playground")
    antwoord = _config()
    assert antwoord["config"]["bronnen"] == {"financien": False, "wo_personeel": False}
    # WOPI staat uit: niet vindbaar, zoals vóór #956. De financiën blijven vindbaar, maar zeggen dat de tool hier
    # geen cijfers geeft: geen kandidaat die alleen een melding oplevert.
    assert all(dataset != "wopi" for dataset, _ in _zoek("wetenschappelijk personeel universiteit"))
    assert ("financien", "alleen_catalogus") in _zoek("financien bestuur solvabiliteit")
    details = json.loads(catalog.dataset_details("duo:financien"))
    assert details["status"] == "alleen_catalogus" and "in deze omgeving geen cijfers" in details["melding"]
    assert catalog.via_tool_aantallen() == {"UWV": 1, "ROA": 1}
    assert "UNL" not in antwoord["counts"] and antwoord["counts"]["DUO"] == catalog.dataset_counts()["DUO"]
    # De tool zelf volgt dezelfde regel.
    assert fin.get_bestuursfinancien("ROC Midden Nederland") == fin.NIET_BESCHIKBAAR


def test_de_docs_telling_hangt_niet_van_de_omgeving_af(omgeving):
    omgeving(wopi=True, app_env="test")
    op_test = catalog.dataset_counts()
    omgeving(wopi=False, app_env="playground")
    assert catalog.dataset_counts() == op_test
