"""VO-aantallen 1-4 staan als 4 gepubliceerd: een som is een bovengrens (#406)."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import cbs, kleine_aantallen, scopeprofiel, store
from tools.duo import get_duo_data
from tools.query import query_data
from tools.store import KeyMeta

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_DF = pd.DataFrame(
    {
        "GEMEENTE": ["A", "A", "A", "B", "B"],
        "AANTAL LEERLINGEN": [4, 4, 100, 50, 60],
    }
)


@pytest.fixture(autouse=True)
def _geladen(zonder_scopegrens):
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


# --- vo-contextrecords (epic #554, #558): de regel geldt niet voor voprognoses en niet voor CBS ---
# voprognoses heeft geen publicatieregels en telt in fracties; de regel volgt alleen uit DUO-data met 4-cellen.

_PROGNOSES = pd.DataFrame(
    {
        "INSTELLINGSCODE": ["00AA", "00AA", "00AB", "00AB", "00AC"],
        "ONDERWIJSNIVEAU": ["HAVO_", "VWO_", "HAVO_", "VWO_", "PRO_"],
        "JAAR": [2030] * 5,
    }
)


@pytest.mark.parametrize(
    "aantallen",
    [[3.62, 4.18, 120.5, 0.97, 13195.76], [12, 7, 120, 9, 30]],
    ids=["fracties", "zonder-4-cellen"],
)
def test_voprognoses_krijgt_geen_bovengrens(aantallen):
    df = _PROGNOSES.assign(PROGNOSEAANTALLEN=aantallen)
    assert not kleine_aantallen.regel_geldt(df)

    store.clear()
    with patch("tools.duo._duo.load", return_value=df), patch("httpx.get", side_effect=AssertionError):
        geladen = json.loads(get_duo_data("voprognoses", 0))
    result = json.loads(
        query_data(geladen["data_key"], group_by=["ONDERWIJSNIVEAU"], aggregate={"PROGNOSEAANTALLEN": "sum"})
    )

    assert not store.meta(geladen["data_key"]).vier_regel
    assert not any("bovengrens" in n for n in result.get("databewerking", []))
    assert "Bovengrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])


@pytest.mark.parametrize("dataset", sorted(i for i in scopeprofiel.HO_CONTEXT if i.upper().endswith("NED")))
def test_een_cbs_key_van_een_contextrecord_krijgt_nooit_de_vier_noot(dataset):
    # Ook met 4-cellen en zonder 1-3 in een aantalkolom: de regel komt alleen uit get_duo_data.
    df = pd.DataFrame(
        {
            "Onderwijssoort": ["A1", "A2", "A3"],
            "Onderwijssoort_label": ["Havo", "Vwo", "Vmbo"],
            "Perioden": ["2024SJ00"] * 3,
            "AantalGediplomeerden_1": [4, 4, 100],
        }
    )
    assert kleine_aantallen.regel_geldt(df)
    store.clear()
    cbs.register_dimensions(dataset, ["Onderwijssoort", "Perioden"])
    try:
        store.put(f"cbs:{dataset}", df, KeyMeta(bron="cbs", dataset=dataset, periodekolom="Perioden"))
        result = json.loads(
            query_data(
                f"cbs:{dataset}",
                group_by=["Onderwijssoort", "Onderwijssoort_label", "Perioden"],
                aggregate={"AantalGediplomeerden_1": "sum"},
            )
        )
    finally:
        cbs.clear_dimensions()

    assert not any("1 t/m 4" in n or "bovengrens" in n for n in result.get("databewerking", []))
    assert "Bovengrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])
