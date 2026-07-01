from unittest.mock import patch

from tools.cbs import get_cbs_data


def test_api_exception_returns_error_string():
    with patch("tools.cbs.data", side_effect=Exception("timeout")):
        result = get_cbs_data("85423NED")
    assert "Fout" in result
    assert "timeout" in result


def test_empty_result_returns_helpful_message():
    with patch("tools.cbs.data", return_value=[]):
        result = get_cbs_data("85423NED", filters={"$filter": "Geslacht eq 'X'"})
    assert "Geen rijen gevonden" in result
    assert "get_cbs_dimension" in result


def test_row_limit_applied():
    rows = [{"id": i} for i in range(300)]
    with patch("tools.cbs.data", return_value=rows):
        result = get_cbs_data("85423NED")
    import json
    parsed = json.loads(result)
    assert parsed["totaal_rijen"] == 200
    assert "data_key" in parsed


def test_truncation_hint_appended_when_limit_reached():
    rows = [{"id": i} for i in range(200)]
    with patch("tools.cbs.data", return_value=rows):
        result = get_cbs_data("85423NED")
    import json
    parsed = json.loads(result)
    assert "waarschuwing" in parsed
    assert "Afgekapt" in parsed["waarschuwing"]
