"""De onderwijsaanbieders van een instelling in RIO v3 (#744), zonder netwerk.

De fixture bevriest wat RIO op 05-11-2026 gaf voor zes mbo-instellingen, onder meer Graafschap College (24ZZ) en
Zone.college (31JC). Zone.college biedt in Doetinchem mbo aan via aanbieder 100A932 ("Zone.college mbo"); het aanbod
per locatie noemt die aanbieder, niet het BRIN.
"""

import datetime as dt
import json
from pathlib import Path

import pytest
from onderwijsbronnen.rio import aanbieders, onderwijsaanbieders

_RIO = json.loads((Path(__file__).parent / "fixtures" / "rio_organisatorische_eenheden.json").read_text())


@pytest.fixture
def rio(monkeypatch):
    aanroepen: list[tuple[str, dict]] = []

    def related(resource, id, sub, **params):
        aanroepen.append((f"{resource}/{id}/{sub}", params))
        return list(_RIO.get(id, []))

    monkeypatch.setattr(aanbieders, "related", related)
    return aanroepen


def test_zone_college_heeft_de_aanbieder_van_doetinchem(rio):
    assert onderwijsaanbieders("31JC", "2026-11-05") == ["100A932", "100A933", "110A638"]


def test_graafschap_college_heeft_vier_aanbieders(rio):
    assert onderwijsaanbieders("24ZZ", "2026-11-05") == ["100A352", "100A354", "100A355", "100A689"]


def test_elke_aanroep_geeft_datum_geldig_op_mee(rio):
    onderwijsaanbieders("31JC", dt.date(2026, 11, 5))
    onderwijsaanbieders("24ZZ")

    assert rio == [
        ("erkenningen/31JC/organisatorische-eenheden", {"datumGeldigOp": "2026-11-05"}),
        ("erkenningen/24ZZ/organisatorische-eenheden", {"datumGeldigOp": dt.date.today().isoformat()}),
    ]


def test_een_onbekende_erkenning_heeft_geen_aanbieders(rio):
    assert onderwijsaanbieders("99XX", "2026-11-05") == []


def test_alleen_aanbieders_die_op_de_peildatum_in_bedrijf_zijn(monkeypatch):
    eenheden = [
        {"code": "100A001", "type": "ONDERWIJSAANBIEDER", "inbedrijfdatum": "2019-08-01", "uitbedrijfdatum": None},
        {"code": "100A002", "type": "ONDERWIJSAANBIEDER", "inbedrijfdatum": "2010-08-01", "uitbedrijfdatum": "2020-08-01"},
        {"code": "100A003", "type": "ONDERWIJSAANBIEDER", "inbedrijfdatum": "2027-08-01", "uitbedrijfdatum": None},
        {"code": "100B004", "type": "ONDERWIJSBESTUUR", "inbedrijfdatum": "2010-08-01", "uitbedrijfdatum": None},
    ]
    monkeypatch.setattr(aanbieders, "related", lambda *a, **k: eenheden)

    assert onderwijsaanbieders("11AA", "2026-11-05") == ["100A001"]
