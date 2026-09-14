"""Tests voor compute_kpi — de tool die voorkomt dat de LLM zelf KPI's berekent."""

import json

import pandas as pd
import pytest

from tools import store
from tools.kpi import compute_kpi

# Werkelijke VU-voltijdreeks: 2021/22 t/m 2025/26.
_REEKS = pd.DataFrame(
    {
        "STUDIEJAAR": [2021, 2022, 2023, 2024, 2025],
        "AANTAL": [30730, 30973, 31198, 30815, 30083],
    }
)


@pytest.fixture(autouse=True)
def _data():
    store.put("duo:kpi:test", _REEKS)


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("last", "30.083"),
        ("first", "30.730"),
        ("min", "30.083"),
        ("max", "31.198"),
        ("delta", "-647"),
        ("pct_change", "-2,1%"),
        ("index", "97,9"),
    ],
)
def test_metrics_geven_nederlandse_notatie(metric, value):
    result = json.loads(compute_kpi("duo:kpi:test", "AANTAL", metric, sort_column="STUDIEJAAR", label="Voltijd"))
    assert result["value"] == value


def test_trend_en_richting_alleen_bij_veranderingsmaten():
    delta = json.loads(compute_kpi("duo:kpi:test", "AANTAL", "delta", sort_column="STUDIEJAAR", label="L"))
    assert delta["trend"] == "-647"
    assert delta["trendDirection"] == "down"

    last = json.loads(compute_kpi("duo:kpi:test", "AANTAL", "last", sort_column="STUDIEJAAR", label="L"))
    assert last["trend"] is None
    assert last["trendDirection"] is None


def test_stijging_krijgt_expliciet_plusteken():
    store.put("duo:kpi:groei", pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [100, 150]}))
    result = json.loads(compute_kpi("duo:kpi:groei", "AANTAL", "pct_change", sort_column="JAAR", label="L"))
    assert result["value"] == "+50,0%"
    assert result["trendDirection"] == "up"


def test_bron_legt_herkomst_vast():
    result = json.loads(compute_kpi("duo:kpi:test", "AANTAL", "sum", label="Totaal"))
    assert result["bron"] == {
        "data_key": "duo:kpi:test",
        "kolom": "AANTAL",
        "metric": "sum",
        "sort_column": None,
        "aantal_waarden": 5,
    }


def test_sort_column_bepaalt_wat_laatste_is():
    omgekeerd = _REEKS.iloc[::-1].reset_index(drop=True)
    store.put("duo:kpi:omgekeerd", omgekeerd)

    gesorteerd = json.loads(compute_kpi("duo:kpi:omgekeerd", "AANTAL", "last", sort_column="STUDIEJAAR", label="L"))
    ongesorteerd = json.loads(compute_kpi("duo:kpi:omgekeerd", "AANTAL", "last", label="L"))

    assert gesorteerd["value"] == "30.083"
    assert ongesorteerd["value"] == "30.730"


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"data_key": "bestaat:niet", "value_column": "AANTAL", "metric": "last"}, "Geen data gevonden"),
        ({"data_key": "duo:kpi:test", "value_column": "ONBEKEND", "metric": "last"}, "niet gevonden"),
        ({"data_key": "duo:kpi:test", "value_column": "AANTAL", "metric": "mediaan"}, "Onbekende metric"),
        ({"data_key": "duo:kpi:test", "value_column": "STUDIEJAAR", "metric": "last", "sort_column": "X"}, "Sorteerkolom"),
    ],
)
def test_foutpaden_geven_uitlegbare_melding(kwargs, fragment):
    result = json.loads(compute_kpi(**kwargs))
    assert fragment in result["fout"]


def test_deling_door_nul_wordt_geweigerd():
    store.put("duo:kpi:nul", pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [0, 50]}))
    result = json.loads(compute_kpi("duo:kpi:nul", "AANTAL", "pct_change", sort_column="JAAR", label="L"))
    assert "eerste waarde" in result["fout"]


def test_kolom_zonder_numerieke_waarden():
    store.put("duo:kpi:tekst", pd.DataFrame({"NAAM": ["a", "b"]}))
    result = json.loads(compute_kpi("duo:kpi:tekst", "NAAM", "sum", label="L"))
    assert "geen numerieke waarden" in result["fout"]
