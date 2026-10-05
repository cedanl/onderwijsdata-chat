"""CBS rondt de HO-tabellen af op tientallen: geen schijnexacte sommen en verschillen (#352).

TableInfos.Description van 85423NED en 85422NED: "De aantallen in de tabel zijn
afgerond op 10-tallen." Een delta als -51.220 of een som van afgeronde details
oogt dan exacter dan de bron. De regel komt uit de tabelbeschrijving en reist met
de data mee naar query, KPI, grafiek, export en het blok onder het antwoord.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import cbs_afronding, store
from tools.cbs import clear_dimensions, get_cbs_data, register_dimensions
from tools.kpi import compute_kpi
from tools.plot import create_plot
from tools.query import query_data
from tools.store import KeyMeta

_BESCHRIJVING = (
    "Cijfers over ingeschrevenen in het hoger onderwijs.\r\n\r\n"
    ". : het cijfer is onbekend, onvoldoende betrouwbaar of geheim\r\n"
    "De aantallen in de tabel zijn afgerond op 10-tallen."
)
_DEFS = {
    "Onderwijssoort": {"type": "Dimension"},
    "Perioden": {"type": "TimeDimension"},
    "TotaalIngeschrevenen_1": {"type": "Topic"},
}
_ROWS = [
    {"Onderwijssoort": "A025294", "Perioden": "2021SJ00", "TotaalIngeschrevenen_1": 344630},
    {"Onderwijssoort": "A025294", "Perioden": "2025SJ00", "TotaalIngeschrevenen_1": 335930},
]


@pytest.mark.parametrize(
    ("tekst", "eenheid"),
    [
        (_BESCHRIJVING, 10),
        ("De cijfers zijn afgerond op tientallen.", 10),
        ("Alle aantallen zijn afgerond op 100-tallen", 100),
        ("Voorlopige cijfers.", None),
        ("", None),
    ],
)
def test_afronding_uit_de_tabelbeschrijving(tekst, eenheid):
    assert cbs_afronding.uit_beschrijving(tekst) == eenheid


def _get(beschrijving):
    def get(dataset_id, endpoint, **params):
        if endpoint != "TableInfos":
            return []
        if isinstance(beschrijving, Exception):
            raise beschrijving
        return [{"Description": beschrijving}]

    return get


def _load(beschrijving=_BESCHRIJVING) -> dict:
    with (
        patch("tools.cbs.data", return_value=_ROWS),
        patch("tools.cbs.definitions", return_value=_DEFS),
        patch("tools.cbs.get", side_effect=_get(beschrijving)),
        patch("tools.catalog._cbs", return_value=[]),
        patch("tools.catalog._rio_duo", return_value=[]),
    ):
        return json.loads(get_cbs_data("85423NED"))


def test_get_cbs_data_legt_de_afronding_vast_en_noemt_hem():
    result = _load()
    known = store.meta(result["data_key"])
    assert known is not None and known.afronding == 10
    assert "10-tallen" in result["afronding"]


def test_tabel_zonder_afronding_krijgt_geen_noot():
    result = _load("Voorlopige cijfers.")
    known = store.meta(result["data_key"])
    assert known is not None and known.afronding is None
    assert "afronding" not in result
    assert "afronding_onbekend" not in result


def test_onbekende_beschrijving_is_niet_exact():
    result = _load(Exception("HTTP 503"))
    assert "afronding" not in result
    assert "niet als exact" in result["afronding_onbekend"]


_KEY = "cbs:85423NED"


@pytest.fixture
def _afgerond():
    # Een som op CBS-data vraagt bekende dimensies (#313).
    register_dimensions("85423NED", ["Onderwijssoort", "Perioden"])
    store.put(
        _KEY,
        pd.DataFrame(
            {
                "Onderwijssoort": ["A025294", "A025294"],
                "Perioden": ["2021SJ00", "2025SJ00"],
                "TotaalIngeschrevenen_1": [344630, 335930],
            }
        ),
        KeyMeta(bron="cbs", dataset="85423NED", periodekolom="Perioden", afronding=10),
    )
    yield
    clear_dimensions()


@pytest.mark.usefixtures("_afgerond")
def test_noot_volgt_de_selectie():
    store.derive(_KEY, f"{_KEY}:abc", pd.DataFrame({"TotaalIngeschrevenen_1": [335930]}))
    assert cbs_afronding.van_key(f"{_KEY}:abc") == cbs_afronding.noot(10)


@pytest.mark.usefixtures("_afgerond")
def test_query_data_meldt_de_afronding_bij_een_som():
    result = json.loads(query_data(_KEY, group_by=["Perioden"], aggregate={"TotaalIngeschrevenen_1": "sum"}))
    assert cbs_afronding.noot(10) in result["databewerking"]


@pytest.mark.usefixtures("_afgerond")
def test_kpi_meldt_de_afronding():
    result = json.loads(compute_kpi(_KEY, "TotaalIngeschrevenen_1", "delta", sort_column="Perioden"))
    assert result["value"] == "-8.700"
    assert result["afronding"] == cbs_afronding.noot(10)


def test_kpi_zonder_afronding_heeft_geen_noot():
    store.put(_KEY, pd.DataFrame({"N": [1, 2]}), KeyMeta(bron="cbs", dataset="85423NED"))
    assert "afronding" not in json.loads(compute_kpi(_KEY, "N", "delta"))


@pytest.mark.usefixtures("_afgerond")
def test_grafiek_en_export_noemen_de_afronding():
    _, fig = create_plot(chart_type="line", x="Perioden", y="TotaalIngeschrevenen_1", title="HO", data_key=_KEY)
    assert fig is not None
    assert "10-tallen" in fig.layout.title.subtitle.text
    assert f"afronding: {cbs_afronding.noot(10)}" in fig.layout.meta["herkomst"]


@pytest.mark.usefixtures("_afgerond")
def test_antwoord_krijgt_de_afronding_eronder():
    blok = telling_blok([json.dumps({"data_key": _KEY})])
    assert "85423NED" in blok and "10-tallen" in blok
