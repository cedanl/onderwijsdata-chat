import pytest

from tools import duo_meta, store


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
