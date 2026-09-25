"""CBS-codes krijgen hun officiële label mee (#163).

Live-audit 4/6: een rapport las T001228 als voltijd (officieel: Totaal opleidingsvorm)
en A025297 als hbo (officieel: Wetenschappelijk onderwijs). Met het label naast de
code hoeft geen model een code te vertalen.
"""

import json
from unittest.mock import patch

import httpx

from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.duo import query_data

_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Opleidingsvorm": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "Ingeschrevenen_1": {"type": "Topic"},
}
_ROWS = [
    {"Onderwijssoort": "A025297", "Opleidingsvorm": "T001228", "Perioden": "2024SJ00", "Ingeschrevenen_1": 1},
]
_DIMENSIES = {
    "Onderwijssoort": [{"Key": "A025297", "Title": "Wetenschappelijk onderwijs"}],
    "Opleidingsvorm": [{"Key": "T001228", "Title": "Totaal opleidingsvorm"}],
    "Perioden": [{"Key": "2024SJ00", "Title": "2024/'25", "Status": "Definitief"}],
}


def _fake_get(dataset_id, endpoint, **params):
    if endpoint not in _DIMENSIES:
        request = httpx.Request("GET", f"https://opendata.cbs.nl/{dataset_id}/{endpoint}")
        raise httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
    return _DIMENSIES[endpoint]


def _load():
    with patch("tools.cbs.data", return_value=_ROWS), \
         patch("tools.cbs.definitions", return_value=_DEFS), \
         patch("tools.cbs.get", side_effect=_fake_get), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        return json.loads(get_cbs_data("85423NED", {"$filter": "x"}))


def test_elke_dimensie_krijgt_een_labelkolom():
    result = _load()

    [rij] = json.loads(query_data(result["data_key"]))["rijen"]
    assert rij["Onderwijssoort_label"] == "Wetenschappelijk onderwijs"
    assert rij["Opleidingsvorm_label"] == "Totaal opleidingsvorm"
    assert rij["Perioden_label"] == "2024/'25"
    assert rij["Periodestatus"] == "Definitief"


def test_labelkolom_heeft_een_definitie():
    kolommen = {k["kolom"]: k for k in _load()["kolommen"]}
    assert "Opleidingsvorm" in kolommen["Opleidingsvorm_label"]["definitie"]


def test_onbekende_dimensie_geeft_uitleg_met_beschikbare_dimensies():
    # Live-audit 6: get_cbs_dimension('Status') gaf een kale 404.
    with patch("tools.cbs.get", side_effect=_fake_get), \
         patch("tools.cbs.definitions", return_value=_DEFS):
        melding = get_cbs_dimension("85423NED", "Status")

    assert "Opleidingsvorm" in melding and "Perioden" in melding
    assert "Periodestatus" in melding
