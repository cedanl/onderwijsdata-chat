"""Eén logregel per gepubliceerd resultaat (#169): herkomst op INFO, de selectiestappen op DEBUG, geen inhoud."""

import logging

import pandas as pd
import pytest

from agent import publicatie
from agent.publicatie import ANTWOORD, CSV, log_publicatie
from tools import store
from tools.store import KeyMeta

_BRON = "duo:p01hoinges:3"
_SELECTIE = "duo:p01hoinges:3:ab12cd34"
_MANIFEST = {"model": "azure_ai/claude", "prompt_hash": "p" * 12, "catalogus": "c" * 12, "app": "2.2.1", "sampling": {}}


@pytest.fixture(autouse=True)
def _data():
    store.clear()
    store.put(
        _BRON,
        pd.DataFrame({"INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht"] * 3, "AANTAL": [1, 2, 3]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=3, laad=("get_duo_data", {"dataset_id": "p01hoinges"})),
    )
    store.derive(
        _BRON,
        _SELECTIE,
        pd.DataFrame({"AANTAL": [6]}),
        stap="filters {'INSTELLINGSNAAM_ACTUEEL': 'Hogeschool Utrecht'}",
    )
    yield
    store.clear()


def _regels(caplog, niveau: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "agent.publicatie" and r.levelno == niveau]


def test_de_regel_noemt_soort_bron_key_en_versies_zonder_inhoud(caplog):
    caplog.set_level(logging.DEBUG, logger="agent.publicatie")
    log_publicatie(ANTWOORD, [_SELECTIE, _BRON, _SELECTIE], _MANIFEST)

    (regel,) = _regels(caplog, logging.INFO)
    assert regel.startswith("GEPUBLICEERD soort=antwoord keys=2 ")
    assert f"bron=duo dataset=p01hoinges resource=3 key={_SELECTIE} afgeleid_van={_BRON} volledig=ja" in regel
    assert "rijen=1" in regel and "rijen=3" in regel
    assert "model=azure_ai/claude prompt_hash=pppppppppppp catalogus=cccccccccccc app=2.2.1" in regel
    # De filtertekst van de selectie kan een getypte naam bevatten: niet op INFO (#475), wel op DEBUG.
    assert "Hogeschool Utrecht" not in regel
    debug = _regels(caplog, logging.DEBUG)
    assert any("Hogeschool Utrecht" in r and f"key={_SELECTIE}" in r for r in debug)


def test_een_onbekende_key_en_een_leeg_manifest_breken_niets(caplog):
    caplog.set_level(logging.INFO, logger="agent.publicatie")
    log_publicatie(CSV, ["duo:weg:0"])
    (regel,) = _regels(caplog, logging.INFO)
    assert regel == "GEPUBLICEERD soort=csv keys=1 duo:weg:0(onbekend) "


def test_afronding_en_herlaaddatum_staan_erbij(caplog):
    store.put(
        "cbs:85423NED",
        pd.DataFrame({"TotaalIngeschrevenen_1": [378490]}),
        KeyMeta(bron="cbs", dataset="85423NED", afronding=10, herladen_op="13-10-2026"),
    )
    caplog.set_level(logging.INFO, logger="agent.publicatie")
    log_publicatie(publicatie.RAPPORT, ["cbs:85423NED"])
    (regel,) = _regels(caplog, logging.INFO)
    assert "bron=cbs dataset=85423NED key=cbs:85423NED volledig=ja afronding=10 herladen_op=13-10-2026 rijen=1" in regel
