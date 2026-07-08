import json

import pandas as pd
import pytest

from tools import store
from tools.analysis import run_analysis


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data))


def test_simple_sum():
    _put("test:an", [{"JAAR": 2021, "N": 100}, {"JAAR": 2021, "N": 200}])
    result = run_analysis(
        code="result = {'totaal': int(df['N'].sum())}",
        data_key="test:an",
    )
    assert json.loads(result)["totaal"] == 300


def test_groupby_in_script():
    _put("test:an", [
        {"JAAR": 2021, "N": 10},
        {"JAAR": 2021, "N": 20},
        {"JAAR": 2022, "N": 30},
    ])
    result = run_analysis(
        code="result = df.groupby('JAAR')['N'].sum().reset_index().to_dict(orient='records')",
        data_key="test:an",
    )
    parsed = json.loads(result)
    assert "data_key" in parsed
    rows = parsed["rijen"]
    sums = {r["JAAR"]: r["N"] for r in rows}
    assert sums[2021] == 30
    assert sums[2022] == 30


def test_returns_figure():
    _put("test:an", [{"X": 1, "Y": 2}, {"X": 3, "Y": 4}])
    result = run_analysis(
        code="figure = px.scatter(df, x='X', y='Y', title='test')\nresult = {'ok': True}",
        data_key="test:an",
    )
    assert isinstance(result, tuple)
    text, fig = result
    assert json.loads(text)["ok"] is True
    assert hasattr(fig, "to_json")


def test_dataframe_result_converted():
    _put("test:an", [{"A": 1}, {"A": 2}])
    result = run_analysis(
        code="result = df[['A']]",
        data_key="test:an",
    )
    parsed = json.loads(result)
    assert "data_key" in parsed
    assert len(parsed["rijen"]) == 2


def test_no_data_key_uses_empty_namespace():
    result = run_analysis(code="result = {'sum': 1 + 2}")
    assert json.loads(result)["sum"] == 3


def test_missing_data_key_returns_error():
    result = run_analysis(code="result = 1", data_key="bestaat:niet")
    assert "niet gevonden" in result.lower() or "bestaat:niet" in result


def test_no_result_set_returns_error():
    _put("test:an", [{"A": 1}])
    result = run_analysis(code="x = df['A'].sum()", data_key="test:an")
    assert "result" in result.lower()


def test_syntax_error_returns_traceback():
    result = run_analysis(code="result = !!!")
    assert "SyntaxError" in result or "syntax" in result.lower()


def test_runtime_error_returns_traceback():
    result = run_analysis(code="result = 1 / 0")
    assert "ZeroDivisionError" in result or "division" in result.lower()


def test_blocked_import():
    result = run_analysis(code="import os\nresult = 1")
    assert "import" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_open():
    result = run_analysis(code="result = open('/etc/passwd').read()")
    assert "open" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_exec():
    result = run_analysis(code="exec('x=1')\nresult = 1")
    assert "exec" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_dunder_builtins():
    result = run_analysis(code="result = __builtins__")
    assert "niet toegestaan" in result.lower() or "__builtins__" in result


def test_store_get_available():
    _put("test:a", [{"V": 1}])
    _put("test:b", [{"V": 2}])
    result = run_analysis(
        code="other = store_get('test:b')\nresult = {'v': int(other['V'].iloc[0])}",
    )
    assert json.loads(result)["v"] == 2
