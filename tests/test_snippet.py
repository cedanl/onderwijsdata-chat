from tools.snippet import generate


def test_query_data_with_filters_and_aggregation():
    snippet = generate("query_data", {
        "data_key": "duo:p02ho1ejrs:Eerstejaarsingeschrevenen wo",
        "filters": {"INSTELLINGSNAAM_ACTUEEL": "VU Amsterdam", "TYPE_HOGER_ONDERWIJS": "bachelor"},
        "group_by": ["STUDIEJAAR"],
        "aggregate": {"AANTAL": "sum"},
    })
    assert snippet is not None
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert 'df[df["INSTELLINGSNAAM_ACTUEEL"] == \'VU Amsterdam\']' in snippet
    assert "groupby" in snippet
    assert "print(df)" in snippet


def test_query_data_minimal():
    snippet = generate("query_data", {"data_key": "duo:abc:resource"})
    assert snippet is not None
    assert 'duo.load("abc"' in snippet
    assert "groupby" not in snippet


def test_query_data_with_columns():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "columns": ["A", "B"],
    })
    assert snippet is not None
    assert "['A', 'B']" in snippet


def test_query_data_cbs_key():
    snippet = generate("query_data", {"data_key": "cbs:83753NED:abc123"})
    assert snippet is not None
    assert "store.get" in snippet
    assert "cbs:83753NED:abc123" in snippet


def test_query_data_filter_operators():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "filters": {"JAAR__gte": 2020, "REGIO__in": ["Noord", "Zuid"]},
    })
    assert snippet is not None
    assert ">=" in snippet
    assert "isin" in snippet


def test_query_data_filter_plain_key_list():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "filters": {"SECTOR": ["Techniek", "Zorg"]},
    })
    assert snippet is not None
    assert "isin" in snippet
    assert "SECTOR" in snippet


def test_run_analysis_returns_code():
    code = "result = df.sum()"
    snippet = generate("run_analysis", {"code": code})
    assert snippet is not None
    assert snippet == code


def test_get_duo_data():
    snippet = generate("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": "Eerstejaarsingeschrevenen wo"})
    assert snippet is not None
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert "Eerstejaarsingeschrevenen wo" in snippet


def test_get_cbs_data_with_filters():
    snippet = generate("get_cbs_data", {
        "dataset_id": "83753NED",
        "filters": {"$filter": "Perioden eq '2023JJ00'"},
    })
    assert snippet is not None
    assert 'data("83753NED"' in snippet
    assert "Perioden" in snippet


def test_create_plot_with_data_key():
    snippet = generate("create_plot", {
        "data_key": "duo:p02ho1ejrs:resource:result",
        "chart_type": "line",
        "x": "STUDIEJAAR",
        "y": "AANTAL",
        "title": "Test grafiek",
    })
    assert snippet is not None
    assert "px.line" in snippet
    assert "store.get" in snippet
    assert "STUDIEJAAR" in snippet
    # Geen gehardcode data-waarden
    assert "[{" not in snippet


def test_create_plot_with_inline_data_fallback():
    snippet = generate("create_plot", {
        "data": [{"JAAR": 2021, "AANTAL": 100}],
        "chart_type": "bar",
        "x": "JAAR",
        "y": "AANTAL",
        "title": "Test",
    })
    assert snippet is not None
    assert "px.bar" in snippet
    assert "2021" in snippet


def test_create_plot_with_color_by():
    snippet = generate("create_plot", {
        "data_key": "duo:x:y:result",
        "chart_type": "bar",
        "x": "X", "y": "Y", "title": "t",
        "color_by": "G",
    })
    assert snippet is not None
    assert 'color="G"' in snippet


def test_create_choropleth_with_data_key():
    snippet = generate("create_choropleth_map", {
        "data_key": "cbs:83753NED:result",
        "location_col": "RegioS",
        "value_col": "Waarde",
        "title": "Kaart",
    })
    assert snippet is not None
    assert "store.get" in snippet
    assert "choropleth_map" in snippet
    assert "RegioS" in snippet


def test_create_choropleth_with_inline_data():
    snippet = generate("create_choropleth_map", {
        "data": [{"RegioS": "PV20", "Waarde": 100}],
        "location_col": "RegioS",
        "value_col": "Waarde",
        "title": "Kaart",
    })
    assert snippet is not None
    assert "PV20" in snippet
    assert "DataFrame" in snippet


def test_unknown_tool_returns_none():
    assert generate("search_catalog", {"query": "test"}) is None
