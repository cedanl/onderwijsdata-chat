"""Een lege CBS-cel ('.', in OData null) is een onderdrukte cel, net als DUO -1 (#862).

Bevroren payload: 85701NED, entreeopleiding 2023/'24, vier gemeenten; GM0738 en GM0366 zijn leeg.
Een selectie met zo'n cel krijgt de ondergrens in de tool-output, het Telling-blok en de CSV-kop;
een volledig gevulde selectie niet.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from core.sentinels import CBS_BETEKENIS, lege_cellen
from tools import cbs, duo, store
from tools.cbs import get_cbs_data
from tools.exportnoten import herkomstregels
from tools.query import query_data

pytestmark = pytest.mark.usefixtures("zonder_scopegrens")

_PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "cbs" / "85701NED_entree_2023.json").read_text())
_KOLOM = "LeerlingenStudenten_1"


def _geen_dimensierijen(*_args, **_kwargs):
    raise RuntimeError("geen netwerk in deze test")


@pytest.fixture
def key() -> str:
    with (
        patch("tools.cbs.data", return_value=_PAYLOAD["rows"]),
        patch("tools.cbs.definitions", return_value=_PAYLOAD["definitions"]),
        patch("tools.cbs.get", side_effect=_geen_dimensierijen),
    ):
        return json.loads(get_cbs_data("85701NED"))["data_key"]


def _selectie(key: str, gemeenten: list[str]) -> dict:
    return json.loads(query_data(key, filters={"Regiokenmerken": gemeenten}))


def test_de_geladen_tabel_legt_haar_lege_cellen_vast(key):
    assert duo.count_cells(duo.sentinel_cells(key)) == {_KOLOM: 6}


def test_een_selectie_met_lege_cellen_meldt_ze_per_jaar(key):
    result = _selectie(key, ["GM1680", "GM0738"])

    noten = " ".join(result["databewerking"])
    assert "Onderdrukte cellen ('.')" in noten and "2023/24: 3" in noten
    assert "-1" not in noten


def test_een_deels_lege_selectie_is_een_ondergrens_in_telling_en_csv(key):
    afgeleid = _selectie(key, ["GM1680", "GM0738"])["data_key"]

    blok = telling_blok([json.dumps({"data_key": afgeleid})])
    assert "Ondergrens" in blok and "85701NED" in blok and "lege cellen ('.')" in blok and CBS_BETEKENIS in blok
    assert "cellen met -1" not in blok
    csv = " ".join(herkomstregels(afgeleid))
    assert f"3 lege CBS-cellen ('.') in '{_KOLOM}'" in csv and "ondergrens" in csv


def test_een_volledig_gevulde_selectie_is_geen_ondergrens(key):
    result = _selectie(key, ["GM1680", "GM0358"])

    assert "databewerking" not in result
    assert "Ondergrens" not in telling_blok([json.dumps({"data_key": result["data_key"]})])
    assert not any("ondergrens" in regel for regel in herkomstregels(result["data_key"]))


def test_een_groepstotaal_over_cbs_krijgt_de_cbs_woorden():
    # Rechtstreeks in de store: de dimensiecontrole laat bij een echte CBS-tabel geen som over een open
    # dimensie toe, dus hier heeft één groep twee rijen zonder tweede dimensie.
    store.put(
        "cbs:TEST",
        pd.DataFrame({"Groep": ["a", "a", "b"], "Aantal": [10.0, None, 30.0]}),
        store.KeyMeta(bron="cbs", dataset="TEST"),
    )
    cbs.register_dimensions("TEST", ["Groep"])
    result = json.loads(query_data("cbs:TEST", group_by=["Groep"], aggregate={"Aantal": "sum"}))

    rijen = {r["Groep"]: r for r in result["rijen"]}
    assert rijen["a"]["Aantal"] == 10 and rijen["a"]["Aantal (onderdrukte cellen)"] == 1
    assert "Aantal (onderdrukte cellen)" not in rijen["b"]
    noten = " ".join(result["databewerking"])
    assert "1 lege CBS-cellen ('.') in 'Aantal' uitgesloten" in noten and "ondergrens" in noten
    assert "onderdrukte cellen ('.')" in noten


def test_lege_cellen_slaat_tekst_en_kolommen_met_een_teken_over():
    df = pd.DataFrame({"Code": ["a", None], "Mutatie_1": [None, 3.0], "Aantal_2": [1.0, None]})

    assert duo.count_cells(lege_cellen(df)) == {"Aantal_2": 1}


def test_een_afgeleide_cbs_key_erft_geen_lege_groepstotalen_als_broncellen():
    store.put("cbs:TEST", pd.DataFrame({"Aantal": [1.0]}), store.KeyMeta(bron="cbs", dataset="TEST"))
    store.derive("cbs:TEST", "cbs:TEST:som", pd.DataFrame({"Aantal": [None]}))

    assert duo.sentinel_cells("cbs:TEST:som") is None
