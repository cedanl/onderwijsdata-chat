import json
from unittest.mock import patch

import pandas as pd

from tools.duo import get_duo_data
from tools.query import _apply_filters


def _make_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"jaar": [str(i) for i in range(n)], "waarde": range(n)})


def test_load_exception_returns_error_string():
    with (
        patch("tools.duo._duo.load", side_effect=Exception("niet gevonden")),
        patch("tools.duo._duo.catalog", return_value=[]),
    ):
        result = get_duo_data("bestaat-niet")
    assert "Fout" in result
    assert "bestaat-niet" in result


def test_load_exception_includes_similar_dataset_hint():
    match = {"_ckan_id": "bestaat-niet-v2", "title": "bestaat-niet dataset"}
    with (
        patch("tools.duo._duo.load", side_effect=Exception("404")),
        patch("tools.duo._duo.catalog", return_value=[match]),
    ):
        result = get_duo_data("bestaat-niet")
    assert "bestaat-niet-v2" in result


def test_successful_load_returns_schema_and_data_key():
    df = _make_df()
    with (
        patch("tools.duo._duo.load", return_value=df),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_duo_data("mbo-prognose:0")
    data = json.loads(result)
    assert "data_key" in data
    assert "kolommen" in data
    assert data["totaal_rijen"] == len(df)
    assert "catalogus_titel" in data
    assert "resource_titel" in data


def test_cache_hit_skips_second_load():
    df = _make_df()
    with (
        patch("tools.duo._duo.load", return_value=df) as mock_load,
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        get_duo_data("cached-dataset")
        get_duo_data("cached-dataset")
    assert mock_load.call_count == 1


def test_apply_filters_eq_with_list():
    df = pd.DataFrame({"SECTOR": ["Techniek", "Zorg", "Economie"], "AANTAL": [1, 2, 3]})
    result, err = _apply_filters(df, {"SECTOR": ["Techniek", "Zorg"]})
    assert err is None
    assert list(result["SECTOR"]) == ["Techniek", "Zorg"]


def test_apply_filters_eq_with_list_case_insensitive():
    df = pd.DataFrame({"SECTOR": ["Techniek", "Zorg", "Economie"], "AANTAL": [1, 2, 3]})
    result, err = _apply_filters(df, {"SECTOR": ["techniek", "ZORG"]})
    assert err is None
    assert len(result) == 2


def test_schema_contains_column_names_and_examples():
    df = pd.DataFrame({"Sector": ["Techniek", "Zorg"], "Jaar": ["2022", "2023"]})
    with (
        patch("tools.duo._duo.load", return_value=df),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_duo_data("schema-test")
    data = json.loads(result)
    kolommen = [k["kolom"] for k in data["kolommen"]]
    assert "Sector" in kolommen
    assert "Jaar" in kolommen


_DUO_ENTRIES = [
    {
        "leverancier": "DUO",
        "_ckan_id": "p02ho1ejrs",
        "bron": "Eerstejaars ingeschrevenen hoger onderwijs in het domein hoger onderwijs",
        "_resources": [
            {"naam": "Eerstejaarsingeschrevenen hoger beroepsonderwijs niveau opleiding in het domein hoger onderwijs"},
            {
                "naam": "Eerstejaarsingeschrevenen wetenschappelijk onderwijs niveau opleiding in het domein hoger onderwijs"
            },
        ],
    }
]


def test_successful_load_includes_catalog_titles_by_index():
    df = _make_df()
    with (
        patch("tools.duo._duo.load", return_value=df),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=_DUO_ENTRIES),
    ):
        result = get_duo_data("p02ho1ejrs", resource=0)
    data = json.loads(result)
    assert data["catalogus_titel"] == "Eerstejaars ingeschrevenen hoger onderwijs in het domein hoger onderwijs"
    assert (
        data["resource_titel"]
        == "Eerstejaarsingeschrevenen hoger beroepsonderwijs niveau opleiding in het domein hoger onderwijs"
    )


def test_successful_load_resolves_resource_by_name_substring():
    df = _make_df()
    with (
        patch("tools.duo._duo.resources", return_value=_DUO_ENTRIES[0]["_resources"]),
        patch("tools.duo._duo.load", return_value=df),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=_DUO_ENTRIES),
    ):
        result = get_duo_data("p02ho1ejrs", resource="wetenschappelijk")
    data = json.loads(result)
    assert (
        data["resource_titel"]
        == "Eerstejaarsingeschrevenen wetenschappelijk onderwijs niveau opleiding in het domein hoger onderwijs"
    )


# #21: één resource, één store-key, of het model hem op nummer of op naam noemt.
_RESOURCES = [{"naam": "Ingeschrevenen hbo"}, {"naam": "Ingeschrevenen wetenschappelijk onderwijs"}]


def _load_twice(first, second):
    with (
        patch("tools.duo._duo.resources", return_value=_RESOURCES),
        patch("tools.duo._duo.load", return_value=_make_df()) as load,
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        a = json.loads(get_duo_data("p01hoinges-t21", first))
        b = json.loads(get_duo_data("p01hoinges-t21", second))
    return a, b, load


def test_resource_op_naam_en_op_nummer_geeft_dezelfde_key():
    a, b, load = _load_twice(1, "wetenschappelijk")
    assert a["data_key"] == b["data_key"] == "duo:p01hoinges-t21:1"
    assert load.call_count == 1  # de tweede aanroep komt uit de store


def test_resource_als_cijferstring_is_een_nummer():
    a, b, load = _load_twice("1", 1)
    assert a["data_key"] == b["data_key"] == "duo:p01hoinges-t21:1"
    # riodata zoekt een str op naam: "1" zou een resource met een 1 in de naam pakken.
    assert load.call_args.args == ("p01hoinges-t21", 1)


def test_onbekende_resourcenaam_houdt_de_foutmelding_van_de_bron():
    with (
        patch("tools.duo._duo.resources", return_value=_RESOURCES),
        patch("tools.duo._duo.load", side_effect=ValueError("Geen resource met 'mbo'")),
        patch("tools.duo._duo.catalog", return_value=[]),
    ):
        result = get_duo_data("p01hoinges-t21b", "mbo")
    assert "Geen resource met 'mbo'" in result
