import json
from unittest.mock import patch

from tools import store
from tools.cbs import get_cbs_data


def _mock_data(dataset_id, **params):
    """Fake CBS API: retourneert rijen met de filter-waarde als label."""
    filter_val = params.get("$filter", "default")
    return [{"Geslacht": filter_val, "Waarde": "1"}]


def test_different_filters_get_different_store_keys():
    """Twee get_cbs_data-calls met verschillende $filter mogen elkaar niet overschrijven."""
    with patch("tools.cbs.data", side_effect=_mock_data):
        r1 = json.loads(get_cbs_data("85353NED", {"$filter": "trim(Geslacht) eq 'T001038'"}))
        r2 = json.loads(get_cbs_data("85353NED", {"$filter": "trim(Geslacht) eq 'T001039'"}))

    assert r1["data_key"] != r2["data_key"], "Store keys zijn gelijk — dataverwisseling mogelijk"

    df1 = store.get(r1["data_key"])
    df2 = store.get(r2["data_key"])
    assert df1 is not None
    assert df2 is not None
    assert df1["Geslacht"].iloc[0] != df2["Geslacht"].iloc[0], "Datastores bevatten dezelfde data"


def test_same_dataset_no_filter_gets_stable_key():
    """Zelfde dataset zonder filter → altijd dezelfde key (cache werkt)."""
    with patch("tools.cbs.data", side_effect=_mock_data):
        r1 = json.loads(get_cbs_data("85353NED"))
        r2 = json.loads(get_cbs_data("85353NED"))

    assert r1["data_key"] == r2["data_key"]


def test_spellingsvarianten_van_dezelfde_cbs_selectie_delen_een_key():
    """Dezelfde OData-selectie in een andere spatiëring of met de default $top is één key (#342)."""
    from core.config import CBS_ROW_LIMIT

    with patch("tools.cbs.data", side_effect=_mock_data):
        r1 = json.loads(get_cbs_data("85353NED", {"$filter": "Perioden  eq  '2024SJ00'"}))
        r2 = json.loads(get_cbs_data("85353NED", {"$filter": "Perioden eq '2024SJ00'", "$top": CBS_ROW_LIMIT}))

    assert r1["data_key"] == r2["data_key"]


def test_legacy_cbs_key_blijft_als_alias_werken():
    """Keys van vóór #342 (md5 over de ruwe filters) blijven dezelfde data geven."""
    import hashlib

    filters = {"$filter": "trim(Geslacht) eq 'T001038'"}
    with patch("tools.cbs.data", side_effect=_mock_data):
        r = json.loads(get_cbs_data("85353NED", filters))

    oud = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()[:8]
    assert store.get(f"cbs:85353NED:{oud}") is store.get(r["data_key"])
