from tools.snippet import generate


def test_query_data_with_filters_and_aggregation():
    snippet = generate("query_data", {
        "data_key": "duo:p02ho1ejrs:Eerstejaarsingeschrevenen wo",
        "filters": {"INSTELLINGSNAAM_ACTUEEL": "VU Amsterdam", "TYPE_HOGER_ONDERWIJS": "bachelor"},
        "group_by": ["STUDIEJAAR"],
        "aggregate": {"AANTAL": "sum"},
    })
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert 'df[df["INSTELLINGSNAAM_ACTUEEL"] == \'VU Amsterdam\']' in snippet
    assert "groupby" in snippet
    assert "print(df)" in snippet


def test_query_data_minimal():
    snippet = generate("query_data", {"data_key": "duo:abc:resource"})
    assert 'duo.load("abc"' in snippet
    assert "groupby" not in snippet


def test_query_data_with_columns():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "columns": ["A", "B"],
    })
    assert "['A', 'B']" in snippet


def test_query_data_cbs_key():
    snippet = generate("query_data", {"data_key": "cbs:83753NED:abc123"})
    assert "store.get" in snippet
    assert "cbs:83753NED:abc123" in snippet


def test_query_data_filter_operators():
    snippet = generate("query_data", {
        "data_key": "duo:x:y",
        "filters": {"JAAR__gte": 2020, "REGIO__in": ["Noord", "Zuid"]},
    })
    assert ">=" in snippet
    assert "isin" in snippet


def test_run_analysis_returns_code():
    code = "result = df.sum()"
    snippet = generate("run_analysis", {"code": code})
    assert snippet == code


def test_get_duo_data():
    snippet = generate("get_duo_data", {"dataset_id": "p02ho1ejrs", "resource": "Eerstejaarsingeschrevenen wo"})
    assert 'duo.load("p02ho1ejrs"' in snippet
    assert "Eerstejaarsingeschrevenen wo" in snippet


def test_get_cbs_data_with_filters():
    snippet = generate("get_cbs_data", {
        "dataset_id": "83753NED",
        "filters": {"$filter": "Perioden eq '2023JJ00'"},
    })
    assert 'data("83753NED"' in snippet
    assert "Perioden" in snippet


def test_unknown_tool_returns_none():
    assert generate("create_plot", {"data": []}) is None
    assert generate("search_catalog", {"query": "test"}) is None
