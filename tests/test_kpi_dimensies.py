"""compute_kpi rekent niet over een open CBS-dimensie en niet over een dubbelzinnige reeks (#863).

Dezelfde dimensiecontrole als query_data (cbs.check_aggregation, #162): anders telt een KPI de totaalrij
("Opleidingsfase totaal") op bij de delen, en het dashboard toont dat getal letterlijk.
"""

import json

import pandas as pd
import pytest

from tools import cbs, store
from tools.kpi import compute_kpi
from tools.query import query_data

_DS = "85423NED"
_KEY = f"cbs:{_DS}:abc12345"
_DIMS = ["Geslacht", "Onderwijssoort", "Opleidingsfase", "Opleidingsvorm", "Perioden"]

# Officiële 85423NED-rijen, hbo voltijd, geslacht totaal: totaal + bachelor + master.
_FASEN = {
    "2024SJ00": {"A045745": 378490, "A028670": 373260, "A028673": 5230},
    "2025SJ00": {"A045745": 367960, "A028670": 362670, "A028673": 5290},
}


@pytest.fixture(autouse=True)
def hbo_voltijd():
    rows = [
        {
            "Geslacht": "T001038",
            "Onderwijssoort": "A025294",
            "Opleidingsfase": fase,
            "Opleidingsvorm": "A028666",
            "Perioden": periode,
            "TotaalIngeschrevenen_1": waarde,
        }
        for periode, fasen in _FASEN.items()
        for fase, waarde in fasen.items()
    ]
    store.put(_KEY, pd.DataFrame(rows), store.KeyMeta(bron="cbs", dataset=_DS))
    cbs.register_dimensions(_DS, _DIMS)


def _fout(uitkomst: str) -> str:
    return json.loads(uitkomst)["fout"]


@pytest.mark.parametrize("metric", ["sum", "mean", "max", "last", "delta"])
def test_kpi_over_een_open_dimensie_geeft_dezelfde_fout_als_query_data(metric):
    fout = _fout(compute_kpi(_KEY, "TotaalIngeschrevenen_1", metric, sort_column="Perioden"))

    verwacht = query_data(_KEY, group_by=["Perioden"], aggregate={"TotaalIngeschrevenen_1": "sum"})
    assert fout == verwacht
    assert "Opleidingsfase" in fout and "756980" not in fout


def test_na_groeperen_via_query_data_rekent_de_kpi():
    afgeleid = json.loads(
        query_data(
            _KEY,
            filters={"Opleidingsfase": "A045745"},
            group_by=["Perioden"],
            aggregate={"TotaalIngeschrevenen_1": "sum"},
        )
    )["data_key"]

    result = json.loads(compute_kpi(afgeleid, "TotaalIngeschrevenen_1", "last", sort_column="Perioden"))
    assert result["raw"] == 367960


def test_zonder_sorteerkolom_moet_elke_dimensie_vastliggen():
    fout = _fout(compute_kpi(_KEY, "TotaalIngeschrevenen_1", "sum"))

    assert "Perioden" in fout and "Opleidingsfase" in fout


def test_cbs_met_onbekende_dimensies_rekent_niet():
    store.put("cbs:ONBEKEND", pd.DataFrame({"Aantal": [1, 2]}), store.KeyMeta(bron="cbs", dataset="ONBEKEND"))

    assert "dimensies onbekend" in _fout(compute_kpi("cbs:ONBEKEND", "Aantal", "sum"))


@pytest.fixture
def per_instelling():
    """DUO kent geen dimensieregistratie: twee instellingen per jaar maken een reeks dubbelzinnig."""
    df = pd.DataFrame(
        {
            "STUDIEJAAR": [2023, 2023, 2024, 2024],
            "INSTELLING": ["21PL", "21PM", "21PL", "21PM"],
            "AANTAL": [10, 20, 12, 21],
        }
    )
    store.put("duo:x:0", df, store.KeyMeta(bron="duo", dataset="x"))
    return "duo:x:0"


@pytest.mark.parametrize("metric", ["last", "first", "delta", "pct_change", "index", "max_rise"])
def test_een_reeks_met_meer_rijen_per_periode_wordt_geweigerd(per_instelling, metric):
    fout = _fout(compute_kpi(per_instelling, "AANTAL", metric, sort_column="STUDIEJAAR"))

    assert "meer dan één rij per periode" in fout and "group_by" in fout and "STUDIEJAAR" in fout


@pytest.mark.parametrize(("metric", "raw"), [("sum", 63), ("max", 21)])
def test_een_som_of_maximum_over_meer_rijen_per_periode_mag(per_instelling, metric, raw):
    # Optellen over instellingen is geen dubbeltelling: DUO heeft geen totaalrijen.
    assert json.loads(compute_kpi(per_instelling, "AANTAL", metric, sort_column="STUDIEJAAR"))["raw"] == raw
