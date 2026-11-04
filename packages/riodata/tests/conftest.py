"""Uitgaand netwerk dicht in de pakkettests (#915), zoals in de chattests; zie tests/netwerkblok.py.

De live-tests van dit pakket draaien alleen met ``RIODATA_LIVE=1``; dan staat het blok voor de hele run open.
"""

import os

import pytest

from tests.netwerkblok import BLOK, melding


def pytest_configure(config):
    BLOK.installeer()


def pytest_unconfigure(config):
    BLOK.verwijder()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    BLOK.begin(open=bool(os.environ.get("RIODATA_LIVE")))


@pytest.fixture(autouse=True)
def netwerk_dicht():
    yield
    if pogingen := BLOK.einde():
        pytest.fail(melding(pogingen), pytrace=False)
