"""Geen som over een percentage, verhouding of verschil; een gemiddelde is geen ondergrens (#866).

Bevroren payload: 85525NED, zes rijen Nederland 2013-2018, met Bevolking_1 ('x 1000') en k_3HboWo_4 ('%').
"""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import store
from tools.cbs import get_cbs_data
from tools.kpi import compute_kpi
from tools.optelbaar import somfout
from tools.query import query_data

_PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "cbs" / "85525NED_opleidingsniveau.json").read_text())
_PROCENT = "k_3HboWo_4"


def _geen_netwerk(*_args, **_kwargs):
    raise RuntimeError("geen netwerk in deze test")


@pytest.fixture
def cbs_key(zonder_scopegrens) -> str:
    with (
        patch("tools.cbs.data", return_value=_PAYLOAD["rows"]),
        patch("tools.cbs.definitions", return_value=_PAYLOAD["definitions"]),
        patch("tools.cbs.get", side_effect=_geen_netwerk),
    ):
        return json.loads(get_cbs_data("85525NED"))["data_key"]


def test_een_som_over_een_procentkolom_van_cbs_wordt_geweigerd_met_uitleg(cbs_key):
    fout = query_data(cbs_key, group_by=["Perioden"], aggregate={_PROCENT: "sum"})

    assert fout == somfout(cbs_key, _PROCENT)
    assert "eenheid is '%'" in fout and "gewogen gemiddelde" in fout and "'mean'" in fout


def test_een_gemiddelde_over_een_procentkolom_en_een_som_over_aantallen_mogen(cbs_key):
    gemiddeld = json.loads(query_data(cbs_key, group_by=["Perioden"], aggregate={_PROCENT: "mean"}))
    som = json.loads(query_data(cbs_key, group_by=["Perioden"], aggregate={"Bevolking_1": "sum"}))

    assert gemiddeld["rijen"][0][_PROCENT] == 26.7
    assert som["rijen"][0]["Bevolking_1"] == 12724000


def test_compute_kpi_weigert_dezelfde_som_en_rekent_het_gemiddelde(cbs_key):
    fout = json.loads(compute_kpi(cbs_key, _PROCENT, "sum", sort_column="Perioden"))["fout"]
    gemiddeld = json.loads(compute_kpi(cbs_key, _PROCENT, "mean", sort_column="Perioden"))

    assert fout == somfout(cbs_key, _PROCENT)
    assert gemiddeld["raw"] == pytest.approx(168.2 / 6)


@pytest.mark.parametrize("kolom", ["PERCENTAGE_GESLAAGD", "AANDEEL_VROUW", "SLAAG%"])
def test_een_duo_kolom_zonder_eenheid_valt_op_haar_naam(kolom):
    store.put(
        "duo:x:0", pd.DataFrame({"JAAR": [2023, 2023], kolom: [40.0, 60.0]}), store.KeyMeta(bron="duo", dataset="x")
    )

    fout = query_data("duo:x:0", group_by=["JAAR"], aggregate={kolom: "sum"})
    assert "kolomnaam noemt een percentage of aandeel" in fout
    assert json.loads(query_data("duo:x:0", group_by=["JAAR"], aggregate={kolom: "mean"}))["rijen"][0][kolom] == 50
    assert "kolomnaam" in json.loads(compute_kpi("duo:x:0", kolom, "sum"))["fout"]


def test_een_som_over_een_kolom_met_een_teken_wordt_geweigerd():
    store.put("duo:x:0", pd.DataFrame({"JAAR": [2023], "MUTATIE_AANTAL": [-3]}), store.KeyMeta(bron="duo", dataset="x"))

    fout = query_data("duo:x:0", group_by=["JAAR"], aggregate={"MUTATIE_AANTAL": "sum"})
    assert "'MUTATIE'" in fout and "verschil" in fout


@pytest.fixture
def met_min_een() -> str:
    store.put(
        "duo:p:0",
        pd.DataFrame({"GESLACHT": ["M", "M", "V"], "AANTAL": [10, -1, 30]}),
        store.KeyMeta(bron="duo", dataset="p"),
    )
    return "duo:p:0"


def test_een_gemiddelde_over_min_een_krijgt_de_gemiddelde_noot(met_min_een):
    result = json.loads(query_data(met_min_een, group_by=["GESLACHT"], aggregate={"AANTAL": "mean"}))

    noten = " ".join(result["databewerking"])
    assert "het gemiddelde is berekend zonder die cellen" in noten and "geen ondergrens" in noten
    assert "is daardoor een ondergrens" not in noten and "alleen dat totaal is een ondergrens" not in noten
    assert {r["GESLACHT"]: r.get("AANTAL (onderdrukte cellen)") for r in result["rijen"]} == {"M": 1, "V": None}
    assert "Ondergrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])


def test_een_som_over_min_een_blijft_een_ondergrens(met_min_een):
    result = json.loads(query_data(met_min_een, group_by=["GESLACHT"], aggregate={"AANTAL": "sum"}))

    noten = " ".join(result["databewerking"])
    assert "is daardoor een ondergrens" in noten and "alleen dat totaal is een ondergrens" in noten
    assert "Ondergrens" in telling_blok([json.dumps({"data_key": result["data_key"]})])
