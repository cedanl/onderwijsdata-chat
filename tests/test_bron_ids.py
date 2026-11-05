"""De vlag BRON_ID_CONTRACT (#912): uit, schaduw en aan, en wat het schaduwlog wel en niet zegt."""

import logging

import pytest

from core import config
from tools import bron_ids, store


@pytest.fixture
def stand(monkeypatch):
    def zet(waarde: str) -> None:
        monkeypatch.setattr(config, "BRON_ID_CONTRACT", waarde)

    return zet


# `roa:ais2030` kent alleen het contract: de oude herleiding haalde alleen cbs/duo/rio als voorvoegsel weg.
_ALLEEN_NIEUW = ("roa:ais2030", "roa:ais2030", "ais2030")


def test_uit_gebruikt_de_oude_herleiding_en_logt_niets(stand, caplog):
    stand("uit")
    invoer, oud, _nieuw = _ALLEEN_NIEUW
    with caplog.at_level(logging.WARNING, logger="tools.bron_ids"):
        assert bron_ids.bron_id(invoer) == oud
    assert "BRON_ID_VERSCHIL" not in caplog.text


def test_aan_gebruikt_het_contract(stand):
    stand("aan")
    invoer, _oud, nieuw = _ALLEEN_NIEUW
    assert bron_ids.bron_id(invoer) == nieuw
    assert bron_ids.bron_id("cbs_85423ned") == "85423NED"
    assert bron_ids.cbs_tabel_id("71733NED") == "71733ned"
    assert bron_ids.cbs_tabel_id("p01hoinges") == "p01hoinges"  # een DUO-ID aan de CBS-toolgrens blijft zoals het is


def test_schaduw_houdt_de_oude_uitkomst_en_telt_en_logt_het_verschil(stand, caplog):
    stand("schaduw")
    invoer, oud, nieuw = _ALLEEN_NIEUW
    voor = bron_ids.verschillen().get("dataset", 0)
    with caplog.at_level(logging.WARNING, logger="tools.bron_ids"):
        assert bron_ids.bron_id(invoer) == oud
    assert bron_ids.verschillen()["dataset"] == voor + 1
    regel = next(r.getMessage() for r in caplog.records if "BRON_ID_VERSCHIL" in r.getMessage())
    assert f"soort=dataset aantal={voor + 1} invoer={invoer} oud={oud} nieuw={nieuw}" in regel


def test_schaduw_zet_een_onbekend_id_niet_letterlijk_in_het_log(stand, caplog, monkeypatch):
    """Een ID dat de catalogus niet kent, kan vrije tekst van het model zijn (#475): alleen lengte en hash."""
    stand("schaduw")
    monkeypatch.setattr(bron_ids, "_nieuw_bron_id", lambda dataset_id: "iets anders")
    with caplog.at_level(logging.WARNING, logger="tools.bron_ids"):
        bron_ids.bron_id("mijn geheime vraag")
    assert "mijn geheime vraag" not in caplog.text and "iets anders" not in caplog.text
    assert "invoer=id_len=18 id_hash=" in caplog.text


def test_schaduw_breekt_de_chat_niet_als_het_contract_faalt(stand, caplog, monkeypatch):
    stand("schaduw")

    def kapot(_):
        raise RuntimeError("stuk")

    monkeypatch.setattr(bron_ids, "parse_bron_id", kapot)
    with caplog.at_level(logging.WARNING, logger="tools.bron_ids"):
        assert bron_ids.bron_id("duo:p01hoinges") == "p01hoinges"
    assert "nieuw=<RuntimeError>" in caplog.text


def test_een_sleutel_logt_alleen_haar_voorvoegsel(stand, caplog, monkeypatch):
    stand("schaduw")
    store.clear()
    monkeypatch.setattr(bron_ids, "bron_van_sleutel", lambda key: "anders")
    with caplog.at_level(logging.WARNING, logger="tools.bron_ids"):
        assert bron_ids.bron_van("rio:aangeboden-opleidingen:naam=Geheim") == "rio"
    assert "Geheim" not in caplog.text and "soort=sleutel" in caplog.text and "invoer=rio " in caplog.text


@pytest.mark.parametrize("waarde", ["", "AAN ", "ja"])
def test_een_onbekende_stand_telt_als_uit(stand, waarde, caplog, monkeypatch):
    monkeypatch.setattr(bron_ids, "_ongeldige_modus_gemeld", False)
    stand(waarde)
    with caplog.at_level(logging.ERROR, logger="tools.bron_ids"):
        assert bron_ids.modus() == "uit"
        assert bron_ids.modus() == "uit"
    assert caplog.text.count("BRON_ID_CONTRACT onbekend") == 1


def test_de_standaard_in_de_code_is_uit_en_test_en_playground_zetten_aan():
    from pathlib import Path

    import yaml

    assert 'os.getenv("BRON_ID_CONTRACT", "uit")' in Path(config.__file__).read_text(encoding="utf-8")
    root = Path(__file__).resolve().parent.parent
    for omgeving, verwacht in (("test", "aan"), ("playground", "aan"), ("production", None)):
        waarden = yaml.safe_load((root / "manifests" / omgeving / "values.yaml").read_text(encoding="utf-8"))
        env = {e["name"]: e.get("value") for e in waarden.get("env", [])}
        assert env.get("BRON_ID_CONTRACT") == verwacht, omgeving
