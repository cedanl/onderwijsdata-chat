"""VO-aantallen 1-4 staan als 4 gepubliceerd: een som is een bovengrens (#406)."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import kleine_aantallen, store
from tools.duo import get_duo_data
from tools.query import query_data

_DF = pd.DataFrame(
    {
        "GEMEENTE": ["A", "A", "A", "B", "B"],
        "AANTAL LEERLINGEN": [4, 4, 100, 50, 60],
    }
)


@pytest.fixture(autouse=True)
def _geladen():
    store.clear()
    with patch("tools.duo._duo.load", return_value=_DF), patch("httpx.get", side_effect=AssertionError):
        json.loads(get_duo_data("01voins-v1", 0))
    yield
    store.clear()


def _som(**kwargs) -> dict:
    return json.loads(
        query_data(
            "duo:01voins-v1:0",
            group_by=["GEMEENTE"],
            aggregate={"AANTAL LEERLINGEN": "sum"},
            **kwargs,
        )
    )


def test_som_met_vier_cellen_geeft_een_bereik_in_het_toolresultaat():
    result = _som()
    rij_a, rij_b = result["rijen"]

    assert rij_a["AANTAL LEERLINGEN"] == 108
    assert rij_a["AANTAL LEERLINGEN (ondergrens bij 1-4 als 4)"] == 102
    assert "ondergrens" not in " ".join(rij_b)
    assert any("bovengrens" in n for n in result["databewerking"])


def test_telling_blok_meldt_een_bovengrens():
    result = _som()
    blok = telling_blok([json.dumps({"data_key": result["data_key"]})])

    assert "Bovengrens" in blok and "01voins-v1" in blok


def test_bestand_zonder_vier_cellen_blijft_ongewijzigd():
    store.clear()
    with patch("tools.duo._duo.load", return_value=_DF.assign(**{"AANTAL LEERLINGEN": [-1, 7, 9, 8, 6]})):
        json.loads(get_duo_data("p01hoinges", 0))
    result = json.loads(query_data("duo:p01hoinges:0", group_by=["GEMEENTE"], aggregate={"AANTAL LEERLINGEN": "sum"}))

    assert not any("bovengrens" in n for n in result["databewerking"])
    assert "Bovengrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])


def test_regel_geldt_alleen_zonder_1_tot_3():
    assert kleine_aantallen.regel_geldt(_DF)
    assert not kleine_aantallen.regel_geldt(_DF.assign(**{"AANTAL LEERLINGEN": [4, 2, 9, 8, 6]}))
