import json
from unittest.mock import patch

from tools.rio import get_rio_data


def test_catalogus_titel_from_catalog():
    rows = [{"id": 1}]
    rio_entries = [
        {"leverancier": "RIO", "_rio_resource": "organisatorische-eenheden", "bron": "Organisatorische eenheden"},
    ]
    with patch("tools.rio.fetch", return_value=rows), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=rio_entries):
        result = get_rio_data("organisatorische-eenheden")
    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "Organisatorische eenheden"


def test_catalogus_titel_falls_back_for_resource_without_entry():
    rows = [{"id": 1}]
    with patch("tools.rio.fetch", return_value=rows), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = get_rio_data("opleiding")
    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "opleiding"


def test_empty_result_returns_message():
    with patch("tools.rio.fetch", return_value=[]):
        result = get_rio_data("organisatorische-eenheden")
    assert "Geen resultaten" in result


def test_fetch_exception_returns_error_string():
    with patch("tools.rio.fetch", side_effect=Exception("timeout")):
        result = get_rio_data("x")
    assert "Fout" in result
    assert "timeout" in result