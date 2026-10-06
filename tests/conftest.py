from unittest.mock import patch

import pytest

from tools import cbs, store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture(autouse=True)
def no_cbs_dimension_call(monkeypatch):
    """Unittests doen geen live CBS-dimensiecall (Perioden.Status); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: [])
    cbs._dimension_rows.cache_clear()
    cbs._tabelbeschrijving.cache_clear()


@pytest.fixture
def zonder_scopegrens():
    """Voor tests van de laad- en metadatamechaniek met test-ID's of vo-bestanden.

    De mbo/hbo/wo-grens zelf staat in test_scopeprofiel.py (#355).
    """
    from tools.catalog import _rio_duo_alles

    with (
        patch("tools.duo.scope_blokkade", return_value=None),
        patch("tools.rio.scope_blokkade", return_value=None),
        patch("tools.catalog._rio_duo", side_effect=_rio_duo_alles),
    ):
        yield
