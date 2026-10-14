import importlib
from unittest.mock import patch

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
