"""Het instellingsregister wordt na 24 uur opnieuw opgebouwd; mislukt dat, dan blijft het oude staan (#873).

Het register kwam bij de eerste aanroep uit live DUO-bestanden en bleef daarna tot de pod herstartte: een nieuwe,
gefuseerde of hernoemde instelling was tot dan onbekend. De klok wordt verzet, er wordt niet gewacht.
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from core import actualiteit
from data import instellingen

_START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def _ho(*namen: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"INSTELLINGSCODE_ACTUEEL": [f"{i:02d}XX" for i in range(len(namen))], "INSTELLINGSNAAM_ACTUEEL": list(namen)}
    )


class _Duo:
    """DUO met een register dat van naam kan wisselen of kan uitvallen; telt de opbouw via p01hoinges/0."""

    def __init__(self):
        self.hbo = ["Hogeschool Utrecht"]
        self.storing = False
        self.opbouwen = 0

    def load(self, dataset: str, resource: int = 0, **kwargs) -> pd.DataFrame:
        if dataset == "p01hoinges" and resource == 0:
            self.opbouwen += 1
            if self.storing:
                raise ConnectionError("DUO onbereikbaar")
            return _ho(*self.hbo)
        if dataset == "p01hoinges":
            return _ho()
        if dataset == "mbo-studenten-per-instelling":
            return pd.DataFrame({"INSTELLINGSCODE": [], "INSTELLINGSNAAM": []})
        return pd.DataFrame()  # adressen: geen


@pytest.fixture
def duo(monkeypatch):
    nep = _Duo()
    monkeypatch.setattr(instellingen.duo, "load", nep.load)
    for naam, waarde in (("_cache", None), ("_alias_lookup", None), ("_opgehaald_op", None), ("_geprobeerd_op", None)):
        monkeypatch.setattr(instellingen, naam, waarde)
    return nep


@pytest.fixture
def klok(monkeypatch):
    moment = [_START]
    monkeypatch.setattr(actualiteit, "nu", lambda: moment[0])

    def verzet(**delta):
        moment[0] += timedelta(**delta)

    return verzet


def _namen() -> list[str]:
    return [i["naam"] for i in instellingen.get_all()]


def test_binnen_de_ttl_blijft_het_register(duo, klok):
    assert _namen() == ["Hogeschool Utrecht"]
    duo.hbo = ["Hogeschool Utrecht", "Nieuwe Hogeschool"]
    klok(hours=23)
    assert _namen() == ["Hogeschool Utrecht"]
    assert duo.opbouwen == 1


def test_na_de_ttl_wordt_het_register_opnieuw_opgebouwd(duo, klok):
    assert instellingen.resolve_alias("HU") == "Hogeschool Utrecht"
    duo.hbo = ["Hogeschool Utrecht Nieuw"]  # hernoemd
    klok(hours=24)
    assert _namen() == ["Hogeschool Utrecht Nieuw"]
    # De aliaslookup is mee opnieuw opgebouwd: "HU" hoort bij de oude naam, die DUO niet meer kent.
    assert instellingen.resolve_alias("HU") == "HU"
    assert duo.opbouwen == 2


def test_bij_een_laadfout_blijft_het_oude_register_met_een_logregel(duo, klok, caplog):
    _namen()
    duo.storing = True
    klok(hours=25)
    with caplog.at_level(logging.WARNING, logger="data.instellingen"):
        assert _namen() == ["Hogeschool Utrecht"]
    assert any("herladen mislukt voor p01hoinges/0" in r.getMessage() for r in caplog.records)
    # Geen fouttekst en geen traceback op WARNING, ook niet in de regel van het mislukte bestand (#819).
    assert "DUO onbereikbaar" not in caplog.text
    assert any(
        "p01hoinges/0) niet beschikbaar: " in r.getMessage() and "fout_len=" in r.getMessage() for r in caplog.records
    )

    # Niet bij elke aanroep opnieuw: pas na de herpoging, en dan met de nieuwe stand.
    klok(minutes=30)
    _namen()
    assert duo.opbouwen == 2
    duo.storing = False
    duo.hbo = ["Hogeschool Utrecht", "Nieuwe Hogeschool"]
    klok(minutes=30)
    assert _namen() == ["Hogeschool Utrecht", "Nieuwe Hogeschool"]
    assert duo.opbouwen == 3
