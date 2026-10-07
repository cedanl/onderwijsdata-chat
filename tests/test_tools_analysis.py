import json
from typing import Any

import pandas as pd

from tools import store
from tools.analysis import run_analysis


def _put(key: str, data: list[dict]) -> None:
    store.put(key, pd.DataFrame(data), store.KeyMeta(bron="test", dataset=key, volledig=True))


def test_simple_sum():
    _put("test:an", [{"JAAR": 2021, "N": 100}, {"JAAR": 2021, "N": 200}])
    result = run_analysis(
        code="result = {'totaal': int(df['N'].sum())}",
        data_key="test:an",
    )
    assert isinstance(result, str)
    assert json.loads(result)["resultaat"]["totaal"] == 300


def test_groupby_in_script():
    _put(
        "test:an",
        [
            {"JAAR": 2021, "N": 10},
            {"JAAR": 2021, "N": 20},
            {"JAAR": 2022, "N": 30},
        ],
    )
    result = run_analysis(
        code="result = df.groupby('JAAR')['N'].sum().reset_index().to_dict(orient='records')",
        data_key="test:an",
    )
    assert isinstance(result, str)
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
    assert json.loads(text)["resultaat"]["ok"] is True
    assert hasattr(fig, "to_json")


def test_dataframe_result_converted():
    _put("test:an", [{"A": 1}, {"A": 2}])
    result = run_analysis(
        code="result = df[['A']]",
        data_key="test:an",
    )
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert "data_key" in parsed
    assert len(parsed["rijen"]) == 2


def test_no_data_key_leaves_df_undefined_but_store_get_works():
    _put("test:an", [{"N": 1}, {"N": 2}])
    result = run_analysis(code="result = {'sum': int(store_get('test:an')['N'].sum())}")
    assert json.loads(result)["resultaat"]["sum"] == 3


def test_script_without_a_data_source_is_refused():
    # #11: a script that neither reads df nor store_get does not compute on data.
    result = run_analysis(code="result = {'sum': 1 + 2}")
    assert "leest geen data" in result
    assert "df" in result and "store_get" in result


def test_missing_data_key_returns_error():
    result = run_analysis(code="result = len(df)", data_key="bestaat:niet")
    assert isinstance(result, str)
    assert "niet gevonden" in result.lower() or "bestaat:niet" in result


def test_no_result_set_returns_error():
    _put("test:an", [{"A": 1}])
    result = run_analysis(code="x = df['A'].sum()", data_key="test:an")
    assert isinstance(result, str)
    assert "result" in result.lower()


def test_syntax_error_returns_traceback():
    result = run_analysis(code="result = !!!")
    assert isinstance(result, str)
    assert "SyntaxError" in result or "syntax" in result.lower()


def test_runtime_error_returns_traceback():
    result = run_analysis(code="result = 1 / 0 + len(df)")
    assert isinstance(result, str)
    assert "ZeroDivisionError" in result or "division" in result.lower()


def test_blocked_import():
    result = run_analysis(code="import os\nresult = 1")
    assert isinstance(result, str)
    assert "import" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_open():
    result = run_analysis(code="result = open('/etc/passwd').read()")
    assert isinstance(result, str)
    assert "open" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_exec():
    result = run_analysis(code="exec('x=1')\nresult = 1")
    assert isinstance(result, str)
    assert "exec" in result.lower() or "niet toegestaan" in result.lower()


def test_blocked_dunder_builtins():
    result = run_analysis(code="result = __builtins__")
    assert isinstance(result, str)
    assert "niet toegestaan" in result.lower() or "__builtins__" in result


def test_store_get_available():
    _put("test:a", [{"V": 1}])
    _put("test:b", [{"V": 2}])
    result = run_analysis(
        code="other = store_get('test:b')\nresult = {'v': int(other['V'].iloc[0])}",
    )
    assert isinstance(result, str)
    # .iloc[0] typt een getal: het resultaat staat naast de scriptconstanten (#410).
    assert json.loads(result) == {"gelezen": ["test:b"], "resultaat": {"v": 2}, "scriptconstanten": [0]}


def test_store_get_returns_a_copy_not_the_shared_object():
    # store_get staat in de namespace van modelgeschreven Python; een mutatie
    # daarop mag de gedeelde procesbrede cache niet raken (#209).
    _put("shared:key", [{"v": 42}])

    code = "df2 = store_get('shared:key')\ndf2.loc[0, 'v'] = 999999\nresult = {'ok': True}"
    run_analysis(code=code)

    assert store.get("shared:key")["v"].iloc[0] == 42


def test_blocked_hardcoded_data():
    """Reject scripts that contain ≥6 numeric literals (likely copy-pasted data)."""
    hardcoded = """result = [
        {'jaar': 2021, 'aantal': 30730, 'mannen': 15000, 'vrouwen': 15730},
        {'jaar': 2022, 'aantal': 31198, 'mannen': 15200, 'vrouwen': 15998},
    ]"""
    result = run_analysis(code=hardcoded)
    assert "hardcoded" in result.lower() or "overgetypte" in result.lower()


def test_figure_carries_the_plotted_rows_for_export():
    # #217: de CSV-export leest layout.meta.data; een run_analysis-figuur droeg die niet
    # en viel terug op de getekende traces (met binaire arrays als lege cellen).
    _put("test:an", [{"K": "Avans", "N": 24169}, {"K": "Fontys", "N": 24740}])
    _, fig = run_analysis(
        code="figure = px.bar(df, x='K', y='N')\nresult = {'ok': True}",
        data_key="test:an",
    )
    assert fig.layout.meta["data"] == [{"K": "Avans", "N": 24169}, {"K": "Fontys", "N": 24740}]


def test_figure_rows_split_grouped_traces_by_series():
    _put("test:an", [{"K": "a", "G": "VT", "N": 1}, {"K": "a", "G": "DT", "N": 2}])
    _, fig = run_analysis(
        code="figure = px.bar(df, x='K', y='N', color='G')\nresult = {'ok': True}",
        data_key="test:an",
    )
    assert fig.layout.meta["data"] == [{"reeks": "VT", "K": "a", "N": 1}, {"reeks": "DT", "K": "a", "N": 2}]


def test_broken_figure_gets_no_rows_so_the_export_refuses_it():
    _put("test:an", [{"K": "a", "N": 1}])
    _, fig = run_analysis(
        code="figure = go.Figure(go.Bar(x=['a', 'b'], y=[1]))\nresult = {'ok': len(df)}",
        data_key="test:an",
    )
    assert not (fig.layout.meta or {}).get("data")


def test_figure_rows_turn_nan_into_an_empty_value():
    _put("test:an", [{"K": "a", "N": 1.0}, {"K": "b", "N": float("nan")}])
    _, fig = run_analysis(
        code="figure = px.bar(df, x='K', y='N')\nresult = {'ok': True}",
        data_key="test:an",
    )
    assert fig.layout.meta["data"] == [{"K": "a", "N": 1.0}, {"K": "b", "N": None}]


def test_heatmap_rows_carry_the_values_from_z_not_the_labels():
    # Een correlatiematrix heeft even lange x en y; die als punten lezen gaf rijen als ('a', 'a').
    _put("test:an", [{"A": 1, "B": 3}, {"A": 2, "B": 1}, {"A": 3, "B": 2}])
    _, fig = run_analysis(code="figure = px.imshow(df.corr())\nresult = {'ok': True}", data_key="test:an")
    assert fig.layout.meta["data"] == [
        {"rij": "A", "kolom": "A", "waarde": 1.0},
        {"rij": "A", "kolom": "B", "waarde": -0.5},
        {"rij": "B", "kolom": "A", "waarde": -0.5},
        {"rij": "B", "kolom": "B", "waarde": 1.0},
    ]


def test_non_square_heatmap_gets_a_row_per_cell():
    _put("test:an", [{"A": 1}])
    _, fig = run_analysis(
        code="figure = go.Figure(go.Heatmap(z=[[1, 2, 3]], x=['p', 'q', 'r'], y=['s']))\nresult = {'ok': len(df)}",
        data_key="test:an",
    )
    assert [r["waarde"] for r in fig.layout.meta["data"]] == [1, 2, 3]
    assert fig.layout.meta["data"][2] == {"rij": "s", "kolom": "r", "waarde": 3}


# --- #201: bewijs en volledigheid horen bij alle gelezen keys ---


def _half(key: str = "test:half") -> None:
    store.put(key, pd.DataFrame({"N": range(50)}), store.KeyMeta(bron="rio", dataset="x", volledig=False))


def _json(uitkomst) -> Any:
    return json.loads(str(uitkomst))


def test_store_get_van_een_onvolledige_key_wordt_geweigerd():
    _half()
    assert run_analysis(code="result = len(store_get('test:half'))") == store.ONVOLLEDIG


def test_onvolledige_key_naast_een_volledige_data_key_wordt_geweigerd():
    _put("test:an", [{"N": 1}])
    _half()
    assert run_analysis(code="result = len(df) + len(store_get('test:half'))", data_key="test:an") == store.ONVOLLEDIG


def test_store_get_van_een_volledige_key_erft_de_metadata():
    _put("test:an", [{"JAAR": 2021, "N": 100}])
    parsed = _json(run_analysis(code="result = store_get('test:an')"))
    known = store.meta(parsed["data_key"])
    assert known is not None and known.afgeleid_van == "test:an"


def test_resultaat_zonder_gelezen_key_heeft_geen_bron():
    # Het script noemt store_get maar leest niets: het getal komt uit het model.
    assert _json(run_analysis(code="store_get\nresult = 987654")) == {"bron": None, "resultaat": 987654}


def test_resultaat_met_gelezen_key_heeft_een_bron():
    _put("test:an", [{"N": 100}])
    assert _json(run_analysis(code="result = int(store_get('test:an')['N'].sum())")) == {
        "gelezen": ["test:an"],
        "resultaat": 100,
    }
