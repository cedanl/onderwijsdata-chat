import json
from unittest.mock import patch

import httpx

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


def test_nested_links_do_not_break_schema():
    # Echte RIO-responses bevatten een geneste HAL-dict per rij.
    rows = [
        {"code": "30TX", "_links": {"self": {"href": "https://rio/30TX"}}},
        {"code": "25DW", "_links": {"self": {"href": "https://rio/25DW"}}},
    ]
    with patch("tools.rio.fetch", return_value=rows), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = get_rio_data("erkenningen", {"volledigeNaam": "Aeres Hogeschool"})
    parsed = json.loads(result)
    links = next(k for k in parsed["kolommen"] if k["kolom"] == "_links")
    assert links["voorbeelden"][0].startswith("{'self'")


def test_empty_result_returns_message():
    with patch("tools.rio.fetch", return_value=[]):
        result = get_rio_data("organisatorische-eenheden")
    assert "Geen resultaten" in result


def test_fetch_exception_returns_error_string():
    with patch("tools.rio.fetch", side_effect=Exception("timeout")):
        result = get_rio_data("x")
    assert "Fout" in result
    assert "timeout" in result


def test_fetch_uses_single_page():
    # Volledige paginatie is zinloos werk: get_rio_data houdt alleen de eerste
    # RIO_PAGE_SIZE-rijen (zie #159; RIO-API gaf 400 op pagina 356).
    captured = {}

    def fake_fetch(resource, **params):
        captured["params"] = params
        return [{"code": str(i)} for i in range(120)]

    with patch("tools.rio.fetch", side_effect=fake_fetch), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        result = get_rio_data("erkenningen", {"volledigeNaam": "Aeres Hogeschool"})

    assert captured["params"]["page"] == 0
    parsed = json.loads(result)
    # Maximaal RIO_PAGE_SIZE rijen in het dataset-antwoord.
    assert parsed["totaal_rijen"] <= 50


def test_http_status_error_returns_explicit_fallback():
    request = httpx.Request("GET", "https://lod.onderwijsregistratie.nl/api/rio/v2/x")
    response = httpx.Response(400, request=request)
    error = httpx.HTTPStatusError("Client error", request=request, response=response)

    with patch("tools.rio.fetch", side_effect=error):
        result = get_rio_data("x", {"volledigeNaam": "Foo"})

    assert "HTTP 400" in result
    assert "x" in result
    assert "Fout bij ophalen" in result