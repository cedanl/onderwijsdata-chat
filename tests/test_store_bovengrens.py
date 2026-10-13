"""De datastore heeft een bovengrens (#13, besluit 06-10-2026).

`tools/store.py` hield elke geladen tabel voor altijd vast: zonder TTL of maximum groeide het
proces door tot een herstart. Boven STORE_MAX_MB gaan nu de langst niet gebruikte keys eruit,
met hun meta en sentinelcellen; een gesprek haalt zo'n key uit zijn recept terug (#472),
zoals na een herstart. Openbare brondata blijft gedeeld tussen sessies.
"""

import logging

import pandas as pd
import pytest

from agent.session_data import ontbrekende_data_keys, session_data_keys
from tools import duo, store
from tools.store import KeyMeta


def _tabel(n: int = 1000) -> pd.DataFrame:
    return pd.DataFrame({"AANTAL": range(n), "NAAM": ["x"] * n})


@pytest.fixture
def grens(monkeypatch):
    """Een bovengrens van tweeënhalve tabel: de derde put duwt de oudste eruit."""
    een = store._bytes(_tabel())
    monkeypatch.setattr(store, "_MAX_BYTES", int(2.5 * een))
    return een


def test_boven_de_grens_verdwijnt_de_langst_niet_gebruikte_key(grens):
    for key in ("cbs:a", "cbs:b", "cbs:c"):
        store.put(key, _tabel(), KeyMeta(bron="cbs", dataset=key))
    assert store.list_keys() == ["cbs:b", "cbs:c"]
    assert store.get("cbs:a") is None and store.meta("cbs:a") is None
    assert store.meta("cbs:c") is not None


def test_lezen_maakt_een_key_weer_de_jongste(grens):
    store.put("cbs:a", _tabel())
    store.put("cbs:b", _tabel())
    store.get("cbs:a")  # in gebruik: niet als eerste eruit
    store.put("cbs:c", _tabel())
    assert store.list_keys() == ["cbs:a", "cbs:c"]


def test_de_sentinelcellen_van_een_verwijderde_duo_key_gaan_mee(grens):
    store.put("duo:x:0", pd.DataFrame({"AANTAL": [-1] * 1000, "NAAM": ["x"] * 1000}))
    assert duo.sentinel_cells("duo:x:0") is not None
    store.put("cbs:b", _tabel())
    store.put("cbs:c", _tabel())
    assert store.get("duo:x:0") is None
    assert duo.sentinel_cells("duo:x:0") is None


def test_een_alias_telt_niet_dubbel_en_gaat_met_haar_key_mee(grens):
    store.put("cbs:a", _tabel(), KeyMeta(bron="cbs", dataset="a"))
    store.alias("cbs_a_oud", "cbs:a")
    assert store.gebruik()["keys"] == 2
    assert store._gebruik() == grens
    store.put("cbs:b", _tabel())
    store.put("cbs:c", _tabel())
    assert store.get("cbs_a_oud") is None and store.get("cbs:a") is None
    assert store.list_keys() == ["cbs:b", "cbs:c"]


def test_een_key_groter_dan_de_grens_blijft_en_wordt_gelogd(grens, caplog):
    store.put("cbs:klein", _tabel())
    with caplog.at_level(logging.WARNING, logger="tools.store"):
        store.put("cbs:groot", _tabel(10_000))
    assert store.list_keys() == ["cbs:groot"]
    assert any("boven de bovengrens" in r.getMessage() and "STORE_MAX_MB" in r.getMessage() for r in caplog.records)


def test_verwijderen_logt_key_en_omvang_zonder_inhoud(grens, caplog):
    with caplog.at_level(logging.INFO, logger="tools.store"):
        for key in ("cbs:a", "cbs:b", "cbs:c"):
            store.put(key, _tabel())
    [regel] = [r.getMessage() for r in caplog.records if "STORE verwijderd" in r.getMessage()]
    assert "cbs:a" in regel and "reden=bovengrens" in regel and "gebruik_mb=" in regel


def test_een_gesprek_ziet_een_verwijderde_key_als_ontbrekend(grens):
    session = {"data_keys": ["cbs:a", "cbs:c"]}
    for key in ("cbs:a", "cbs:b", "cbs:c"):
        store.put(key, _tabel())
    assert session_data_keys(session) == ["cbs:c"]
    assert ontbrekende_data_keys(session) == ["cbs:a"]


def test_clear_zet_de_telling_op_nul(grens):
    store.put("cbs:a", _tabel())
    store.clear()
    assert store.gebruik() == {"keys": 0, "mb": 0.0, "bovengrens_mb": store._MAX_BYTES // 2**20}


def test_de_standaardgrens_komt_uit_de_configuratie():
    from core.config import STORE_MAX_MB

    assert store._MAX_BYTES == STORE_MAX_MB * 2**20
    assert store.gebruik()["bovengrens_mb"] == STORE_MAX_MB
