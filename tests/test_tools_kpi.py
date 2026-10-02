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
    store.put("duo:kpi:test", _REEKS, store.KeyMeta(bron="duo", dataset="kpi:test"))


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
    store.put("duo:kpi:groei", pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [100, 150]}),
              store.KeyMeta(bron="duo", dataset="kpi:groei"))
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
    store.put("duo:kpi:omgekeerd", omgekeerd, store.KeyMeta(bron="duo", dataset="kpi:omgekeerd"))

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
    store.put("duo:kpi:nul", pd.DataFrame({"JAAR": [2021, 2022], "AANTAL": [0, 50]}),
              store.KeyMeta(bron="duo", dataset="kpi:nul"))
    result = json.loads(compute_kpi("duo:kpi:nul", "AANTAL", "pct_change", sort_column="JAAR", label="L"))
    assert "eerste waarde" in result["fout"]


def test_kolom_zonder_numerieke_waarden():
    store.put("duo:kpi:tekst", pd.DataFrame({"NAAM": ["a", "b"]}),
              store.KeyMeta(bron="duo", dataset="kpi:tekst"))
    result = json.loads(compute_kpi("duo:kpi:tekst", "NAAM", "sum", label="L"))
    assert "geen numerieke waarden" in result["fout"]


def test_grootste_daling_is_de_grootste_stap_niet_de_eerste_die_opvalt():
    # #116: 28.355 → 27.904 → 27.441 → 27.135 → 26.370. Het antwoord noemde -463; de grootste is -765.
    store.put("duo:kpi:hu", pd.DataFrame({"STUDIEJAAR": [2021, 2022, 2023, 2024, 2025],
                                          "AANTAL": [28355, 27904, 27441, 27135, 26370]}),
              store.KeyMeta(bron="duo", dataset="kpi:hu"))

    result = json.loads(compute_kpi("duo:kpi:hu", "AANTAL", "max_drop", sort_column="STUDIEJAAR", label="Grootste daling"))

    assert result["value"] == "-765"
    assert result["raw"] == -765
    assert result["tussen"] == ["2024", "2025"]
    assert result["trendDirection"] == "down"


def test_grootste_stijging_en_sortering_op_kolom():
    store.put("duo:kpi:shuffled", pd.DataFrame({"JAAR": [2023, 2021, 2022], "N": [150, 100, 110]}),
              store.KeyMeta(bron="duo", dataset="kpi:shuffled"))

    result = json.loads(compute_kpi("duo:kpi:shuffled", "N", "max_rise", sort_column="JAAR", label="x"))

    assert result["value"] == "+40"
    assert result["tussen"] == ["2022", "2023"]


def test_zonder_daling_is_het_een_fout_geen_nul():
    result = json.loads(compute_kpi("duo:kpi:test", "AANTAL", "max_drop", sort_column="STUDIEJAAR", label="x"))
    assert result["tussen"] == ["2024", "2025"]  # 31.198 → 30.815 → 30.083: wel een daling

    store.put("duo:kpi:up", pd.DataFrame({"J": [1, 2], "N": [1, 2]}), store.KeyMeta(bron="duo", dataset="kpi:up"))
    assert "Geen daling" in json.loads(compute_kpi("duo:kpi:up", "N", "max_drop", sort_column="J", label="x"))["fout"]



# --- #235: de periode hoort bij het resultaat, zodat het antwoord haar niet zelf hoeft te benoemen ---

@pytest.mark.parametrize("metric", ["first", "last", "sum", "mean", "delta", "pct_change", "index"])
def test_kpi_noemt_de_periode_waarover_hij_rekent(metric):
    result = json.loads(compute_kpi("duo:kpi:test", "AANTAL", metric, sort_column="STUDIEJAAR"))
    assert result["periode"] == {"van": "2021/22", "tot": "2025/26"}


def test_cbs_schooljaren_krijgen_hun_label():
    # Audit 10: +29.040 was 2019/20 → 2025/26, het antwoord schreef 2024/25.
    store.put("cbs:wo:test", pd.DataFrame({"Perioden": [f"{j}SJ00" for j in range(2019, 2026)],
                                           "N": [305000, 310000, 315000, 320000, 325000, 330000, 334040]}),
              store.KeyMeta(bron="cbs", dataset="wo:test"))
    result = json.loads(compute_kpi("cbs:wo:test", "N", "delta", sort_column="Perioden"))
    assert result["periode"] == {"van": "2019/20", "tot": "2025/26"}


def test_rijen_zonder_waarde_tellen_niet_mee_in_de_periode():
    store.put("duo:kpi:gat", pd.DataFrame({"STUDIEJAAR": [2020, 2021, 2022], "AANTAL": [None, 10, 12]}),
              store.KeyMeta(bron="duo", dataset="kpi:gat"))
    result = json.loads(compute_kpi("duo:kpi:gat", "AANTAL", "delta", sort_column="STUDIEJAAR"))
    assert result["periode"] == {"van": "2021/22", "tot": "2022/23"}


def test_grootste_daling_noemt_de_periode_van_de_stap():
    result = json.loads(compute_kpi("duo:kpi:test", "AANTAL", "max_drop", sort_column="STUDIEJAAR"))
    assert result["periode"] == {"van": "2024/25", "tot": "2025/26"}


def test_kalenderjaren_blijven_zoals_de_bron_ze_noemt():
    store.put("cbs:kj:test", pd.DataFrame({"Perioden": ["2023JJ00", "2024JJ00"], "N": [1, 2]}),
              store.KeyMeta(bron="cbs", dataset="kj:test"))
    result = json.loads(compute_kpi("cbs:kj:test", "N", "delta", sort_column="Perioden"))
    assert result["periode"] == {"van": "2023JJ00", "tot": "2024JJ00"}


def test_zonder_sorteerkolom_geen_periode():
    assert "periode" not in json.loads(compute_kpi("duo:kpi:test", "AANTAL", "delta"))


def test_grootste_daling_bij_herhaalde_indexlabels():
    # Een samengevoegd frame (concat) heeft index 0, 1, 0, 1; een labelopzoeking gaf een Series.
    df = pd.concat([pd.DataFrame({"J": [2020, 2021], "N": [10, 5]}), pd.DataFrame({"J": [2022, 2023], "N": [8, 1]})])
    store.put("duo:kpi:concat", df, store.KeyMeta(bron="duo", dataset="kpi:concat"))

    result = json.loads(compute_kpi("duo:kpi:concat", "N", "max_drop", sort_column="J", label="x"))

    assert result["raw"] == -7
    assert result["tussen"] == ["2022", "2023"]
