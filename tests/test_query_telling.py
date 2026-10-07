"""Tellen op tekst-, UUID- en numerieke-tekstkolommen geeft geen 0 (#411).

CH-04: count op AANGEBODEN_OPLEIDINGCODE gaf per groep 0, omdat elke
aggregatiekolom eerst numeriek werd gemaakt.
"""

import json

import pandas as pd
import pytest

from tools import store
from tools.query import _apply_aggregation, query_data

_DF = pd.DataFrame(
    {
        "VORM": ["BOL", "BOL", "BOL", "BBL", "BBL"],
        "CODE": ["a1b2c3d4-0000-4000-8000-000000000001", "a1b2c3d4-0000-4000-8000-000000000002", None, "x", "x"],
        "NAAM": ["Kok", "Kapper", "Kok", pd.NA, "Lasser"],
        "TEKSTGETAL": ["12", "8", None, "3", "3"],
        "AANTAL": [10.0, 20.0, pd.NA, 5.0, 7.0],
    }
)


def _per_vorm(agg: pd.DataFrame, kolom: str) -> dict:
    return dict(zip(agg["VORM"], agg[kolom], strict=True))


@pytest.mark.parametrize(
    ("kolom", "fn", "verwacht"),
    [
        ("CODE", "count", {"BOL": 2, "BBL": 2}),
        ("NAAM", "count", {"BOL": 3, "BBL": 1}),
        ("CODE", "nunique", {"BOL": 2, "BBL": 1}),
        ("NAAM", "size", {"BOL": 3, "BBL": 2}),
        ("TEKSTGETAL", "count", {"BOL": 2, "BBL": 2}),
        ("TEKSTGETAL", "sum", {"BOL": 20.0, "BBL": 6.0}),
        ("AANTAL", "count", {"BOL": 2, "BBL": 2}),
        ("AANTAL", "sum", {"BOL": 30.0, "BBL": 12.0}),
    ],
)
def test_telling_gebruikt_de_oorspronkelijke_waarden(kolom, fn, verwacht):
    agg = _apply_aggregation(_DF, group_by=["VORM"], aggregate={kolom: fn})
    assert _per_vorm(agg, kolom) == verwacht


@pytest.mark.usefixtures("zonder_scopegrens")
def test_query_data_telt_een_tekstkolom():
    store.put("duo:mbo_aanbod:1", _DF.copy(), store.KeyMeta(bron="duo", dataset="mbo_aanbod", resource=1))
    uit = json.loads(query_data("duo:mbo_aanbod:1", group_by=["VORM"], aggregate={"CODE": "count"}))
    assert {rij["VORM"]: rij["CODE"] for rij in uit["rijen"]} == {"BOL": 2, "BBL": 2}
