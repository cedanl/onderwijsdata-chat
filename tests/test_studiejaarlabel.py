"""DUO-studiejaren krijgen hun label in code (#115, UX-audit 2).

STUDIEJAAR 2021 is studiejaar 2021/2022, maar het antwoord labelde de reeks 2021 t/m 2025 als
2020/2021 … 2024/2025: het model rekende zelf om en schoof alles een jaar.
"""
import json
from unittest.mock import patch

import pandas as pd

from tools import periode, store
from tools.duo import get_duo_data
from tools.query import query_data

_DATA = pd.DataFrame({
    "STUDIEJAAR": [2021, 2021, 2022, 2025],
    "OPLEIDINGSVORM": ["VT", "DT", "VT", "VT"],
    "AANTAL": [10, 5, 20, 30],
})


def test_label_is_the_start_year_and_the_next():
    assert periode.studiejaar_label(2021) == "2021/2022"
    assert periode.studiejaar_label(2025) == "2025/2026"


def test_loaded_duo_data_carries_the_label_next_to_the_raw_year():
    store.clear()
    with patch("tools.duo._duo.load", return_value=_DATA.copy()), \
         patch("tools.duo._duo.column_definitions", return_value={}):
        result = json.loads(get_duo_data("p01hoinges", 3))

    kolommen = {k["kolom"]: k for k in result["kolommen"]}
    assert "STUDIEJAAR_LABEL" in kolommen
    assert "2021/2022" in kolommen["STUDIEJAAR_LABEL"]["voorbeelden"]
    assert "reken jaren niet zelf om" in kolommen["STUDIEJAAR_LABEL"]["definitie"]
    frame = store.get("duo:p01hoinges:3")
    assert frame.loc[frame["STUDIEJAAR"] == 2021, "STUDIEJAAR_LABEL"].unique().tolist() == ["2021/2022"]
    store.clear()


def test_data_without_studiejaar_is_left_alone():
    df = pd.DataFrame({"JAAR": [2021], "AANTAL": [1]})
    assert periode.met_studiejaarlabel(df).equals(df)


def test_grouping_by_year_keeps_the_label_with_the_total():
    store.clear()
    store.put("duo:x:1", periode.met_studiejaarlabel(_DATA), store.KeyMeta(bron="duo", dataset="x"))

    result = json.loads(query_data("duo:x:1", group_by=["STUDIEJAAR"], aggregate={"AANTAL": "sum"}))

    assert result["rijen"] == [
        {"STUDIEJAAR": 2021, "STUDIEJAAR_LABEL": "2021/2022", "AANTAL": 15},
        {"STUDIEJAAR": 2022, "STUDIEJAAR_LABEL": "2022/2023", "AANTAL": 20},
        {"STUDIEJAAR": 2025, "STUDIEJAAR_LABEL": "2025/2026", "AANTAL": 30},
    ]
    store.clear()
