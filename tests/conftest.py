import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent import recepten
from tools import cbs, cbs_preflight, profiel, store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    recepten.wis()
    profiel.vergeet()
    yield
    store.clear()
    recepten.wis()
    profiel.vergeet()


@pytest.fixture(autouse=True)
def no_cbs_dimension_call(monkeypatch):
    """Unittests doen geen live CBS-dimensiecall (Perioden.Status); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: [])
    cbs._dimension_rows.cache_clear()
    cbs._tabelbeschrijving.cache_clear()


@pytest.fixture(autouse=True)
def geen_cbs_preflight(monkeypatch):
    """Unittests vragen het CBS-contract niet live om een oordeel (#370); tests van de preflight patchen zelf."""
    monkeypatch.setattr(
        cbs_preflight,
        "validate_selection",
        lambda dataset_id, eis, live=False: {"dataset_id": dataset_id, "status": "unknown", "checks": []},
    )


@pytest.fixture(autouse=True)
def geen_adresdownload(monkeypatch):
    """Unittests downloaden geen DUO-adresbestanden voor de instellingsprovincie (#453); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr("tools.instellingsprovincie.get_adres_lookup", lambda: {})


@pytest.fixture
def duo_fixtures(monkeypatch):
    """`duo.load` leest de bevroren DUO-bestanden van `scripts/duo_testfixtures.py`, niet onderwijsdata.duo.nl (#766).

    Voor de instellingenregister- en dashboardtests: de pytest-job blokkeert elke MR en mag niet omvallen
    op een storing bij DUO. Een bestand zonder fixture faalt met de naam erbij, zodat het script hem krijgt.
    """
    from riodata import duo

    import data.dashboard
    import data.instellingen
    from scripts.duo_testfixtures import MAP, bestandsnaam

    tekst = json.loads((MAP / "tekstkolommen.json").read_text())

    def load(dataset_id: str, resource: int | str = 0, **kwargs) -> pd.DataFrame:
        naam = bestandsnaam(dataset_id, resource)
        if naam not in tekst:
            raise AssertionError(f"geen DUO-fixture {naam}: voeg hem toe in scripts/duo_testfixtures.py")
        return pd.read_csv(MAP / naam, dtype=dict.fromkeys(tekst[naam], str))

    def wis_caches():
        # Het register en de dashboardladers cachen in de module: anders blijft data van een andere test staan.
        data.instellingen._cache = data.instellingen._alias_lookup = data.instellingen._ADRES_CACHE = None
        for functie in vars(data.dashboard).values():
            if hasattr(functie, "cache_clear"):
                functie.cache_clear()

    monkeypatch.setattr(duo, "load", load)
    wis_caches()
    yield
    wis_caches()


@pytest.fixture
def dashboards_aan(monkeypatch):
    """De dashboardvlag staat standaard uit (#765); tests van de dashboardroutes en -acties zetten hem hiermee aan."""
    import routes.chat
    import routes.instellingen

    monkeypatch.setattr(routes.chat, "DASHBOARDS_ENABLED", True)
    monkeypatch.setattr(routes.instellingen, "DASHBOARDS_ENABLED", True)


@pytest.fixture
def zonder_scopegrens():
    """Voor tests van de laad- en metadatamechaniek met test-ID's of vo-bestanden.

    De mbo/hbo/wo-grens zelf staat in test_scopeprofiel.py (#355).
    """
    from tools.catalog import _rio_duo_alles

    with (
        patch("tools.cbs.scope_blokkade", return_value=None),
        patch("tools.duo.scope_blokkade", return_value=None),
        patch("tools.rio.scope_blokkade", return_value=None),
        patch("tools.rio.scopeprofiel.sectorfilter_ontbreekt", return_value=None),
        patch("tools.catalog._rio_duo", side_effect=_rio_duo_alles),
    ):
        yield


@pytest.fixture
def zonder_scopekaart(monkeypatch):
    """Voor tests van de beurt met een nagebootst model: geen verduidelijkingskaart uit code vóór het model.

    Of een korte testvraag als "vraag" een maatkaart krijgt (#348), hangt af van de gepinde catalogus;
    zulke tests gaan over wat het model daarna doet. De kaart zelf staat in test_scopevraag.py.
    """
    # agent/__init__ exporteert run(), dat het module-attribuut agent.run overschaduwt.
    run_module = importlib.import_module("agent.run")
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings: None)
