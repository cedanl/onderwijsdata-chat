import pytest
from tools import store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()
