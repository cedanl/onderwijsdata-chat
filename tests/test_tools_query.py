import pandas as pd
import pytest

from tools import store
from tools.duo import query_data


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data))


def test_no_filters_returns_all_rows():
    _put("test:df", [{"A": "1"}, {"A": "2"}, {"A": "3"}])
    result = query_data("test:df")
    assert '"totaal_rijen":3' in result


def test_filter_exact_match():
    _put("test:df", [{"Leerweg": "Voltijd"}, {"Leerweg": "Deeltijd"}])
    result = query_data("test:df", filters={"Leerweg": "Voltijd"})
    assert '"totaal_rijen":1' in result
    assert "Voltijd" in result


def test_filter_case_insensitive():
    _put("test:df", [{"Sector": "Techniek"}, {"Sector": "Zorg"}])
    result = query_data("test:df", filters={"Sector": "techniek"})
    assert '"totaal_rijen":1' in result


def test_column_selection():
    _put("test:df", [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}])
    result = query_data("test:df", columns=["A"])
    assert '"A"' in result
    assert '"B"' not in result


def test_missing_column_returns_error():
    _put("test:df", [{"A": "1"}])
    result = query_data("test:df", columns=["Bestaat_niet"])
    assert "niet gevonden" in result.lower() or "Bestaat_niet" in result


def test_missing_filter_column_returns_error():
    _put("test:df", [{"A": "1"}])
    result = query_data("test:df", filters={"Bestaat_niet": "x"})
    assert "bestaat niet" in result.lower() or "Bestaat_niet" in result


def test_unknown_data_key_returns_error():
    result = query_data("bestaat:niet")
    assert "Geen data gevonden" in result


def test_adaptive_cap_adds_warning():
    # 100 kolommen × 200 rijen > 6000 cellen → cap + waarschuwing
    wide_rows = [{f"k{i}": str(i) for i in range(100)} for _ in range(200)]
    _put("test:wide", wide_rows)
    result = query_data("test:wide")
    assert "waarschuwing" in result.lower() or "rijen" in result


def test_max_rows_respected():
    # Adaptieve cap heeft een vloer van 50; gebruik max_rows > 50 om de limiet te testen.
    _put("test:df", [{"A": str(i)} for i in range(200)])
    result = query_data("test:df", max_rows=60)
    import json
    data = json.loads(result)
    assert len(data["rijen"]) == 60
