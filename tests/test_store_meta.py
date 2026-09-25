"""Wat het systeem van een data_key weet, reist mee naar wat eruit wordt afgeleid (#193).

Een afgekapte RIO-pagina blijft afgekapt, ook na query_data of run_analysis (#186);
dat kan alleen als de eigenschap aan de key hangt en niet aan een toolbericht.
"""
import json
from unittest.mock import patch

import pandas as pd
import pytest

from core.config import RIO_PAGE_SIZE
from tools import store
from tools.analysis import run_analysis
from tools.cbs import get_cbs_data
from tools.duo import get_duo_data
from tools.query import query_data
from tools.rio import get_rio_data
from tools.store import KeyMeta


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


def test_put_records_meta_and_without_meta_there_is_none():
    store.put("rio:x", pd.DataFrame({"a": [1]}), KeyMeta(bron="rio", dataset="x", volledig=False))
    store.put("los", pd.DataFrame({"a": [1]}))

    assert store.meta("rio:x") == KeyMeta(bron="rio", dataset="x", volledig=False)
    assert store.meta("los") is None


def test_derive_inherits_the_parent_meta_and_names_the_parent():
    store.put("rio:x", pd.DataFrame({"a": [1, 2]}), KeyMeta(bron="rio", dataset="x", volledig=False))

    store.derive("rio:x", "rio:x:q", pd.DataFrame({"a": [1]}))

    child = store.meta("rio:x:q")
    assert child.volledig is False and child.bron == "rio"
    assert child.afgeleid_van == "rio:x"


def test_derive_from_a_key_without_meta_gives_no_meta():
    store.put("los", pd.DataFrame({"a": [1]}))
    store.derive("los", "los:q", pd.DataFrame({"a": [1]}))
    assert store.meta("los:q") is None


def test_clear_wipes_the_meta():
    store.put("cbs:x", pd.DataFrame({"a": [1]}), KeyMeta(bron="cbs", dataset="x"))
    store.clear()
    assert store.meta("cbs:x") is None


def test_get_cbs_data_records_its_source():
    with patch("tools.cbs.data", return_value=[{"Geslacht": "T001038", "Waarde": "1"}]):
        key = json.loads(get_cbs_data("85423NED"))["data_key"]

    assert store.meta(key) == KeyMeta(bron="cbs", dataset="85423NED")


def test_get_duo_data_records_its_source_and_teldefinitie():
    df = pd.DataFrame({"OPLEIDINGSVORM": ["VT"], "AANTAL": [10]})
    with patch("tools.duo._duo.load", return_value=df), \
         patch("tools.duo.teldefinitie", return_value="natuurlijke personen"):
        key = json.loads(get_duo_data("p01hoinges", 3))["data_key"]

    assert store.meta(key) == KeyMeta(bron="duo", dataset="p01hoinges", resource=3, teldefinitie="natuurlijke personen")


def _rio(rows: int) -> str:
    with patch("tools.rio.fetch", return_value=[{"id": i} for i in range(rows)]), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        return json.loads(get_rio_data("erkenningen"))["data_key"]


def test_a_full_rio_page_is_recorded_as_incomplete():
    assert store.meta(_rio(RIO_PAGE_SIZE)).volledig is False
    store.clear()
    assert store.meta(_rio(3)).volledig is True


def test_query_data_on_an_incomplete_key_stays_incomplete():
    key = _rio(RIO_PAGE_SIZE)

    derived = json.loads(query_data(key, filters={"id__gte": 10}))["data_key"]

    assert derived != key
    assert store.meta(derived).volledig is False
    assert store.meta(derived).afgeleid_van == key


def test_run_analysis_on_an_incomplete_key_stays_incomplete():
    key = _rio(RIO_PAGE_SIZE)

    derived = json.loads(run_analysis("result = df.head(3)", data_key=key))["data_key"]

    assert store.meta(derived).volledig is False
    assert store.meta(derived).afgeleid_van == key
