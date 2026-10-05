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
