import pytest

from tools import cbs, duo_meta, store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture(autouse=True)
def no_ckan_metadata(monkeypatch):
    """Unittests doen geen live CKAN-call; tests die de teldefinitie nodig hebben patchen zelf."""
    monkeypatch.setattr(duo_meta, "_fetch_notes", lambda dataset_id: "")
    duo_meta.clear_cache()


@pytest.fixture(autouse=True)
def no_cbs_dimension_call(monkeypatch):
    """Unittests doen geen live CBS-dimensiecall (Perioden.Status); tests die hem nodig hebben patchen zelf."""
    monkeypatch.setattr(cbs, "get", lambda dataset_id, endpoint, **params: [])
    cbs.get_cbs_dimension.cache_clear()
