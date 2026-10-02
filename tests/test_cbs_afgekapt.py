"""Een afgekapte CBS-tabel is niet de hele bron: geen totaal en geen aggregatie (#5)."""

import json
from unittest.mock import patch

from tools import store
from tools.cbs import get_cbs_data
from tools.query import query_data


def _rows(n):
    def fake(dataset_id, **params):
        return [{"Studierichting": f"S{i % 14}", "Waarde": "1"} for i in range(n)]

    return fake


def test_afgekapte_tabel_is_onvolledig_en_heeft_geen_totaal(monkeypatch):
    monkeypatch.setattr("tools.cbs.CBS_ROW_LIMIT", 10)
    with patch("tools.cbs.data", side_effect=_rows(10)):
        result = json.loads(get_cbs_data("85421NED"))
    assert not store.volledig(result["data_key"])
    assert "totaal_rijen" not in result
    assert result["opgehaalde_rijen"] == 10 and result["volledig"] is False


def test_aggregatie_over_afgekapte_tabel_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr("tools.cbs.CBS_ROW_LIMIT", 10)
    with patch("tools.cbs.data", side_effect=_rows(10)):
        key = json.loads(get_cbs_data("85421NED"))["data_key"]
    assert query_data(key, aggregate={"Waarde": "sum"}) == store.ONVOLLEDIG


def test_eigen_top_die_vol_zit_is_ook_onvolledig():
    with patch("tools.cbs.data", side_effect=_rows(3)):
        result = json.loads(get_cbs_data("85421NED", {"$top": 3}))
    assert not store.volledig(result["data_key"])


def test_tabel_onder_de_grens_blijft_volledig(monkeypatch):
    monkeypatch.setattr("tools.cbs.CBS_ROW_LIMIT", 10)
    with patch("tools.cbs.data", side_effect=_rows(4)):
        result = json.loads(get_cbs_data("85421NED"))
    assert store.volledig(result["data_key"])
    assert result["totaal_rijen"] == 4
