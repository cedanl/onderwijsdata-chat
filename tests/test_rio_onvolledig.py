"""Een afgekapte RIO-pagina levert geen telling en geen 'niet gevonden' op (#186).

Live-audit 7a: GPT-OSS riep run_analysis(result = len(df)) aan op de eerste pagina
en antwoordde "landelijk 50 erkenningen"; bij Aeres probeerde het een onbekend
filter (HTTP 400), keek daarna in de ongefilterde eerste pagina en concludeerde
dat de code niet bestond.
"""
import json
from unittest.mock import patch

import httpx
import pytest

from core.config import RIO_PAGE_SIZE
from tools import store
from tools.analysis import run_analysis
from tools.kpi import compute_kpi
from tools.query import query_data
from tools.rio import get_rio_data

_ERKENNINGEN_FILTERS = ["erkenningtype", "volledigeNaam", "plaatsnaam", "datumGeldigOp"]
_CATALOG = [{"_rio_resource": "erkenningen", "bron": "Erkenningen", "filters": _ERKENNINGEN_FILTERS}]


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


def _get(rows: int, filters: dict | None = None, fetch=None):
    records = [{"code": f"{i:02d}XX", "volledigeNaam": f"Instelling {i}", "aantal": i} for i in range(rows)]
    with patch("tools.rio.fetch", fetch or (lambda *a, **k: records)), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=_CATALOG):
        return get_rio_data("erkenningen", filters)


def _page() -> str:
    return json.loads(_get(RIO_PAGE_SIZE))["data_key"]


def test_run_analysis_refuses_a_count_on_a_truncated_page():
    result = run_analysis("result = len(df)", data_key=_page())
    assert "afgekapt" in result
    assert "50" not in result


def test_run_analysis_still_returns_rows_with_a_warning():
    parsed = json.loads(run_analysis("result = df.head(2)", data_key=_page()))
    assert len(parsed["rijen"]) == 2
    assert "afgekapt" in parsed["waarschuwing"]


def test_query_data_refuses_aggregation_on_a_truncated_page():
    result = query_data(_page(), group_by=["volledigeNaam"], aggregate={"aantal": "count"})
    assert "afgekapt" in result and "geen" in result


def test_query_data_on_a_truncated_page_reports_fetched_rows_not_a_total():
    parsed = json.loads(query_data(_page(), filters={"aantal__gte": 40}))
    assert "totaal_rijen" not in parsed
    assert parsed["opgehaalde_rijen"] == 10
    assert parsed["volledig"] is False


def test_empty_result_on_a_truncated_page_is_not_absence():
    parsed = json.loads(query_data(_page(), filters={"volledigeNaam": "Aeres Hogeschool"}))
    assert parsed["opgehaalde_rijen"] == 0
    assert "niet in deze pagina" in parsed["melding"].lower()
    assert "volledigeNaam" in parsed["melding"]  # het serverfilter dat wél kan


def test_complete_data_keeps_its_total_and_aggregates():
    key = json.loads(_get(3))["data_key"]
    parsed = json.loads(query_data(key, group_by=["volledigeNaam"], aggregate={"aantal": "sum"}))
    assert parsed["totaal_rijen"] == 3


def test_compute_kpi_refuses_a_truncated_page():
    result = json.loads(compute_kpi(_page(), "aantal", "sum", label="Totaal"))
    assert "afgekapt" in result["fout"]


def test_unknown_rio_filter_names_the_allowed_ones_without_calling_rio():
    calls: list = []

    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return []

    result = _get(0, {"naam__contains": "Aeres"}, fetch)

    assert calls == []
    assert "naam__contains" in result
    assert all(f in result for f in _ERKENNINGEN_FILTERS)


def test_http_400_names_the_allowed_filters():
    def fetch(*args, **kwargs):
        request = httpx.Request("GET", "https://rio")
        raise httpx.HTTPStatusError("400", request=request, response=httpx.Response(400, request=request))

    result = _get(0, {"volledigeNaam": "Aeres Hogeschool"}, fetch)

    assert "HTTP 400" in result
    assert "volledigeNaam" in result and "plaatsnaam" in result
