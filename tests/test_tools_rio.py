import json
from unittest.mock import patch

import httpx
import pytest

from core.config import RIO_PAGE_SIZE
from tools import fouten
from tools.rio import get_rio_data


def test_catalogus_titel_from_catalog():
    rows = [{"id": 1}]
    rio_entries = [
        {"leverancier": "RIO", "_rio_resource": "organisatorische-eenheden", "bron": "Organisatorische eenheden"},
    ]
    with (
        patch("tools.rio.fetch", return_value=rows),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=rio_entries),
    ):
        result = get_rio_data("organisatorische-eenheden")
    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "Organisatorische eenheden"


def test_catalogus_titel_falls_back_for_resource_without_entry():
    rows = [{"id": 1}]
    with (
        patch("tools.rio.fetch", return_value=rows),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_rio_data("opleidingen")
    parsed = json.loads(result)
    assert parsed["catalogus_titel"] == "opleidingen"


def test_nested_links_do_not_break_schema():
    # Echte RIO-responses bevatten een geneste HAL-dict per rij.
    rows = [
        {"code": "30TX", "_links": {"self": {"href": "https://rio/30TX"}}},
        {"code": "25DW", "_links": {"self": {"href": "https://rio/25DW"}}},
    ]
    with (
        patch("tools.rio.fetch", return_value=rows),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_rio_data("erkenningen", {"volledigeNaam": "Aeres Hogeschool"})
    parsed = json.loads(result)
    links = next(k for k in parsed["kolommen"] if k["kolom"] == "_links")
    assert links["voorbeelden"][0].startswith("{'self'")


def test_empty_result_returns_message():
    with patch("tools.rio.fetch", return_value=[]):
        result = get_rio_data("organisatorische-eenheden")
    assert "Geen resultaten" in result


def test_fetch_exception_returns_a_coded_error_without_the_raw_text():
    # De ruwe providertekst gaat naar het log, niet naar het model (#331).
    with patch("tools.rio.fetch", side_effect=Exception("timeout")):
        result = get_rio_data("erkenningen")
    assert fouten.code(result) == "bron_fout"
    assert "timeout" not in result


def test_fetch_uses_single_page():
    # Volledige paginatie is zinloos werk: get_rio_data houdt alleen de eerste
    # RIO_PAGE_SIZE-rijen (zie #159; RIO-API gaf 400 op pagina 356).
    captured = {}

    def fake_fetch(resource, **params):
        captured["params"] = params
        return [{"code": str(i)} for i in range(120)]

    with (
        patch("tools.rio.fetch", side_effect=fake_fetch),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        result = get_rio_data("erkenningen", {"volledigeNaam": "Aeres Hogeschool"})

    assert captured["params"]["page"] == 0
    parsed = json.loads(result)
    # Maximaal RIO_PAGE_SIZE rijen in het dataset-antwoord.
    assert parsed["opgehaalde_rijen"] == RIO_PAGE_SIZE


def test_page_size_from_filters_is_ignored():
    # Een grotere pageSize zou toch op RIO_PAGE_SIZE afgekapt worden (#170).
    captured = {}

    def fake_fetch(resource, **params):
        captured["params"] = params
        return [{"code": "1"}]

    with (
        patch("tools.rio.fetch", side_effect=fake_fetch),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        get_rio_data("erkenningen", {"pageSize": 1000})

    assert captured["params"]["pageSize"] == RIO_PAGE_SIZE


def _load(rows):
    with (
        patch("tools.rio.fetch", return_value=rows),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        return json.loads(get_rio_data("aangeboden-opleidingen"))


def test_full_page_warns_that_result_is_not_a_count():
    # RIO levert geen totaal; een volle pagina is een steekproef, geen telling (#170).
    parsed = _load([{"code": str(i)} for i in range(RIO_PAGE_SIZE)])
    assert "waarschuwing" in parsed
    assert "telling" in parsed["waarschuwing"]


def test_partial_page_has_no_warning():
    parsed = _load([{"code": "1"}, {"code": "2"}])
    assert "waarschuwing" not in parsed


def test_full_page_flags_more_rows_available():
    # Live-audit 6: GPT las "totaal_rijen: 50" als registertotaal, ondanks de
    # waarschuwing. Een boolean en een eerlijke veldnaam laten geen totaal zien (#177).
    parsed = _load([{"code": str(i)} for i in range(RIO_PAGE_SIZE)])
    assert parsed["meer_beschikbaar"] is True
    assert "totaal_rijen" not in parsed


def test_partial_page_has_nothing_more():
    parsed = _load([{"code": "1"}, {"code": "2"}])
    assert parsed["meer_beschikbaar"] is False
    assert parsed["opgehaalde_rijen"] == 2


def test_http_status_error_returns_explicit_fallback():
    request = httpx.Request("GET", "https://lod.onderwijsregistratie.nl/api/rio/v2/x")
    response = httpx.Response(400, request=request)
    error = httpx.HTTPStatusError("Client error", request=request, response=response)

    with patch("tools.rio.fetch", side_effect=error):
        result = get_rio_data("erkenningen", {"volledigeNaam": "Foo"})

    assert "HTTP 400" in result
    assert "erkenningen" in result
    assert fouten.code(result) == "bron_weigert"


def test_tool_description_sets_expectation_for_counts():
    # Het model moet vóóraf weten dat RIO geen totalen kan leveren (#170).
    from tools.schemas import TOOL_GET_RIO_DATA, TOOL_SCHEMAS

    tool = next(t["function"] for t in TOOL_SCHEMAS if t["function"]["name"] == TOOL_GET_RIO_DATA)
    assert str(RIO_PAGE_SIZE) in tool["description"]
    assert "totalen" in tool["description"]


def test_status_filter_op_cohorten_gaat_door_naar_rio():
    # #353: RIO accepteert status live (codes als "G"); de oude allowlist kende het niet.
    with patch("tools.rio.fetch", return_value=[{"id": 1, "status": "G"}]) as fetch:
        get_rio_data("aangeboden-opleiding-cohorten", filters={"status": "G"})
    assert fetch.call_args.kwargs["status"] == "G"


def test_onbekend_filter_blijft_geweigerd():
    with patch("tools.rio.fetch") as fetch:
        result = get_rio_data("aangeboden-opleiding-cohorten", filters={"onzin": "x"})
    fetch.assert_not_called()
    assert "Onbekend filter 'onzin'" in result
    assert "status" in result  # de geldige filters staan in de hint


@pytest.mark.parametrize(
    ("resource", "filters", "herstel"),
    [
        # Leesbare waarden gaven live HTTP 400 (#353): het contract noemt de codes.
        ("aangeboden-opleiding-cohorten", {"status": "OPEN"}, "Geldig: O, G"),
        ("opleidingen", {"opleidingseenheidtype": "HBO"}, "HOOPLEIDING"),
        ("erkenningen", {"datumGeldigOp": "2026-13-01"}, "YYYY-MM-DD"),
    ],
)
def test_ongeldige_waarde_wordt_geweigerd_met_de_geldige_waarden(resource, filters, herstel):
    with patch("tools.rio.fetch") as fetch:
        result = get_rio_data(resource, filters)
    fetch.assert_not_called()
    assert herstel in result


def test_geldige_enumwaarde_gaat_door():
    with patch("tools.rio.fetch", return_value=[{"id": 1}]) as fetch:
        get_rio_data("opleidingen", {"opleidingseenheidtype": "HOOPLEIDING"})
    assert fetch.call_args.kwargs["opleidingseenheidtype"] == "HOOPLEIDING"


def test_onbekende_resource_noemt_de_bedoelde():
    with patch("tools.rio.fetch") as fetch:
        result = get_rio_data("opleiding")
    fetch.assert_not_called()
    assert "Bedoelde je: opleidingen" in result


def test_getal_als_code_en_paging_als_tekst_worden_niet_geweigerd():
    # httpx stuurt 25295 als tekst; paging zet get_rio_data zelf.
    with patch("tools.rio.fetch", return_value=[{"id": 1}]) as fetch:
        get_rio_data("opleidingserkenningen", {"erkendeopleidingscode": 25295, "page": "3"})
    assert fetch.call_args.kwargs["erkendeopleidingscode"] == 25295
    assert fetch.call_args.kwargs["page"] == 0


def test_filters_komen_uit_het_riodata_contract():
    from tools.rio import rio_filters

    assert "status" in rio_filters("aangeboden-opleiding-cohorten")
    assert rio_filters("bestaat-niet") == []
