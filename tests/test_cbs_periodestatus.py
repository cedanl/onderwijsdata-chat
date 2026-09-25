"""CBS-periodestatus komt uit Perioden.Status, niet uit een vuistregel (#180).

Live-audit 6: get_cbs_dimension('Perioden') gaf alleen code → titel. De modellen
raadden de status ("nieuwste jaar is voorlopig"), hardcodeerden hem in run_analysis
of kregen hem fout in het rapport (2024/25 'Voorlopig' of 'Nader voorlopig'; officieel
Definitief).
"""

import json
from unittest.mock import patch

from tools.cbs import get_cbs_data, get_cbs_dimension
from tools.query import query_data

_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "Ingeschrevenen_1": {"type": "Topic"},
}
_ROWS = [
    {"Onderwijssoort": "A025294", "Perioden": "2024SJ00", "Ingeschrevenen_1": 378490},
    {"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "Ingeschrevenen_1": 367960},
]
_PERIODEN = [
    {"Key": "2024SJ00", "Title": "2024/'25", "Description": "", "Status": "Definitief"},
    {"Key": "2025SJ00", "Title": "2025/'26", "Description": "Voorlopige cijfers", "Status": "Voorlopig"},
]


def _load(perioden=_PERIODEN):
    side_effect = perioden if isinstance(perioden, Exception) else None
    with patch("tools.cbs.data", return_value=_ROWS), \
         patch("tools.cbs.definitions", return_value=_DEFS), \
         patch("tools.cbs.get", return_value=perioden, side_effect=side_effect), \
         patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[]):
        return json.loads(get_cbs_data("85423NED", {"$filter": "Onderwijssoort eq 'A025294'"}))


def test_get_cbs_data_voegt_periodestatus_uit_de_bron_toe():
    result = _load()

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "Periodestatus")
    assert "Perioden.Status" in kolom["definitie"]
    rijen = json.loads(query_data(result["data_key"]))["rijen"]
    assert {r["Perioden"]: r["Periodestatus"] for r in rijen} == {
        "2024SJ00": "Definitief", "2025SJ00": "Voorlopig",
    }


def test_zonder_bronstatus_geen_geraden_status():
    result = _load(perioden=Exception("404"))

    assert "Periodestatus" not in [k["kolom"] for k in result["kolommen"]]


def test_get_cbs_dimension_geeft_status_bij_perioden():
    with patch("tools.cbs.get", return_value=_PERIODEN):
        waarden = json.loads(get_cbs_dimension("85423NED", "Perioden"))

    assert waarden["2024SJ00"] == {"titel": "2024/'25", "status": "Definitief"}
    assert waarden["2025SJ00"] == {"titel": "2025/'26", "status": "Voorlopig"}


def test_get_cbs_dimension_zonder_status_blijft_code_naar_titel():
    rows = [{"Key": "A025294 ", "Title": "Hbo ", "Description": ""}]
    with patch("tools.cbs.get", return_value=rows):
        waarden = json.loads(get_cbs_dimension("85423NED", "Onderwijssoort"))

    assert waarden == {"A025294": "Hbo"}


def test_toolbeschrijving_wijst_naar_periodestatus():
    from tools.schemas import TOOL_GET_CBS_DIMENSION, TOOL_SCHEMAS

    [schema] = [s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_CBS_DIMENSION]
    assert "status" in schema["function"]["description"].lower()
