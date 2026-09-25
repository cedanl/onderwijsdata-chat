"""CBS-tabellen bevatten totaalrijen naast hun onderdelen: optellen over een
niet-uitgesplitste dimensie telt dubbel (#162, Live-audit 4 en 5)."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from tools import cbs, store
from tools.cbs import get_cbs_data
from tools.query import query_data

_DS = "85423NED"
_KEY = f"cbs:{_DS}:abc12345"
_DIMS = ["Geslacht", "Onderwijssoort", "Opleidingsfase", "Opleidingsvorm", "Perioden"]

# Officiële 85423NED-rijen, hbo voltijd, geslacht totaal: totaal + bachelor + master.
_FASEN = {
    "2024SJ00": {"A045745": 378490, "A028670": 373260, "A028673": 5230},
    "2025SJ00": {"A045745": 367960, "A028670": 362670, "A028673": 5290},
}


@pytest.fixture
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
    store.put(_KEY, pd.DataFrame(rows))
    cbs.register_dimensions(_DS, _DIMS)


def test_sum_over_open_dimension_is_refused(hbo_voltijd):
    # De chatfout uit de audit: 756.980 = totaal + bachelor + master.
    result = query_data(
        _KEY, group_by=["Perioden"], aggregate={"TotaalIngeschrevenen_1": "sum"}
    )
    assert "756980" not in result
    assert "Opleidingsfase" in result
    assert "A045745" in result


def test_sum_with_every_other_dimension_pinned_is_allowed(hbo_voltijd):
    result = json.loads(
        query_data(
            _KEY,
            filters={"Opleidingsfase": "A045745"},
            group_by=["Perioden"],
            aggregate={"TotaalIngeschrevenen_1": "sum"},
        )
    )
    totals = {r["Perioden"]: r["TotaalIngeschrevenen_1"] for r in result["rijen"]}
    assert totals == {"2024SJ00": 378490, "2025SJ00": 367960}


def test_grouping_by_the_dimension_is_allowed(hbo_voltijd):
    # Uitsplitsen naar fase is legitiem: elke groep heeft één fase.
    result = json.loads(
        query_data(
            _KEY,
            group_by=["Perioden", "Opleidingsfase"],
            aggregate={"TotaalIngeschrevenen_1": "sum"},
        )
    )
    assert result["totaal_rijen"] == 6


def test_time_dimension_is_guarded_too(hbo_voltijd):
    # Jaren optellen is voor een standgegeven (ingeschrevenen) net zo fout.
    result = query_data(
        _KEY,
        filters={"Opleidingsfase": "A045745"},
        group_by=["Geslacht"],
        aggregate={"TotaalIngeschrevenen_1": "sum"},
    )
    assert "Perioden" in result
    assert not result.startswith("{")


def test_dropping_a_multivalued_dimension_via_columns_is_refused(hbo_voltijd):
    # Anders verdwijnt de fase uit een afgeleide key en telt een volgende
    # aggregatie alsnog dubbel, zonder dat de guard het kan zien.
    result = query_data(_KEY, columns=["Perioden", "TotaalIngeschrevenen_1"])
    assert "Opleidingsfase" in result
    assert not result.startswith("{")


def test_columns_keeping_distinguishing_dimensions_is_allowed(hbo_voltijd):
    result = json.loads(
        query_data(
            _KEY,
            filters={"Opleidingsfase": "A045745"},
            columns=["Perioden", "TotaalIngeschrevenen_1"],
        )
    )
    assert result["totaal_rijen"] == 2


def test_unknown_dataset_is_not_guarded():
    # Zonder geregistreerde dimensies (bijv. data van vóór een herstart) geen
    # valse weigering: de guard weet dan niet welke kolommen dimensies zijn.
    store.put("cbs:00000NED:x", pd.DataFrame({"Regio": ["A", "B"], "Aantal": [1, 2]}))
    result = json.loads(
        query_data("cbs:00000NED:x", columns=["Aantal"])
    )
    assert result["totaal_rijen"] == 2


def test_non_cbs_keys_are_not_guarded():
    store.put("duo:x:0", pd.DataFrame({"GROEP": ["A", "B"], "AANTAL": [1, 2]}))
    cbs.register_dimensions("x", ["GROEP"])
    result = json.loads(query_data("duo:x:0", columns=["AANTAL"]))
    assert result["totaal_rijen"] == 2


def test_get_cbs_data_registers_dimension_columns():
    rows = [{"ID": 0, "Geslacht": "T001038", "Perioden": "2024SJ00", "Totaal_1": 5}]
    defs = {
        "Geslacht": {"type": "Dimension"},
        "Perioden": {"type": "TimeDimension"},
        "Totaal_1": {"type": "Topic"},
    }
    with patch("tools.cbs.data", return_value=rows), \
         patch("tools.cbs.definitions", return_value=defs), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        get_cbs_data("99999NED")
    assert cbs.dimension_columns("cbs:99999NED:deadbeef") == ["Geslacht", "Perioden"]


def test_store_clear_forgets_dimensions():
    cbs.register_dimensions(_DS, _DIMS)
    store.clear()
    assert cbs.dimension_columns(_KEY) == []


def test_aggregate_without_group_by_does_not_crash(hbo_voltijd):
    # Een som over álles laat elke dimensie open: weigeren, niet crashen.
    result = query_data(_KEY, aggregate={"TotaalIngeschrevenen_1": "sum"})
    assert isinstance(result, str)
    assert not result.startswith("{")


def test_select_cannot_drop_dimension_columns():
    # Anders levert $select ononderscheidbare rijen op die de guard niet ziet.
    defs = {
        "Geslacht": {"type": "Dimension"},
        "Perioden": {"type": "TimeDimension"},
        "Totaal_1": {"type": "Topic"},
    }
    captured = {}

    def fake_data(dataset_id, **params):
        captured.update(params)
        return [{"Geslacht": "T001038", "Perioden": "2024SJ00", "Totaal_1": 5}]

    with patch("tools.cbs.data", side_effect=fake_data), \
         patch("tools.cbs.definitions", return_value=defs), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        get_cbs_data("99999NED", {"$select": "Perioden, Totaal_1"})

    assert captured["$select"].split(",") == ["Perioden", "Totaal_1", "Geslacht"]
