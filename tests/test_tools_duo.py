import json
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.duo import get_duo_data


def _make_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"jaar": [str(i) for i in range(n)], "waarde": range(n)})


def test_load_exception_returns_error_string():
    with patch("tools.duo._duo.load", side_effect=Exception("niet gevonden")):
        with patch("tools.duo._duo.catalog", return_value=[]):
            result = get_duo_data("bestaat-niet")
    assert "Fout" in result
    assert "bestaat-niet" in result


def test_load_exception_includes_similar_dataset_hint():
    match = {"_ckan_id": "bestaat-niet-v2", "title": "bestaat-niet dataset"}
    with patch("tools.duo._duo.load", side_effect=Exception("404")):
        with patch("tools.duo._duo.catalog", return_value=[match]):
            result = get_duo_data("bestaat-niet")
    assert "bestaat-niet-v2" in result


def test_successful_load_returns_schema_and_data_key():
    df = _make_df()
    with patch("tools.duo._duo.load", return_value=df):
        result = get_duo_data("mbo-prognose:0")
    data = json.loads(result)
    assert "data_key" in data
    assert "kolommen" in data
    assert data["totaal_rijen"] == len(df)


def test_cache_hit_skips_second_load():
    df = _make_df()
    with patch("tools.duo._duo.load", return_value=df) as mock_load:
        get_duo_data("cached-dataset")
        get_duo_data("cached-dataset")
    assert mock_load.call_count == 1


def test_schema_contains_column_names_and_examples():
    df = pd.DataFrame({"Sector": ["Techniek", "Zorg"], "Jaar": ["2022", "2023"]})
    with patch("tools.duo._duo.load", return_value=df):
        result = get_duo_data("schema-test")
    data = json.loads(result)
    kolommen = [k["kolom"] for k in data["kolommen"]]
    assert "Sector" in kolommen
    assert "Jaar" in kolommen
