import pytest
from tools import store


@pytest.fixture(autouse=True)
def clear_store():
    """Reset de in-memory store tussen tests (Chainlit-context ontbreekt in tests)."""
    store._fallback.clear()
    yield
    store._fallback.clear()
