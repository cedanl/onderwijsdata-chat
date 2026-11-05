"""Uitgaand netwerk dicht in de pakkettests (#915), zoals in de chattests; zie tests/netwerkblok.py.

Dit pakket heeft geen live-tests: het blok staat voor elke test dicht.
"""

import pytest

from tests.netwerkblok import BLOK, melding


def pytest_configure(config):
    BLOK.installeer()


def pytest_unconfigure(config):
    BLOK.verwijder()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    BLOK.begin(open=False)


@pytest.fixture(autouse=True)
def netwerk_dicht():
    yield
    if pogingen := BLOK.einde():
        pytest.fail(melding(pogingen), pytrace=False)
