"""Een KPI over de hele selectie terwijl de beurt er een filter op maakte (#319).

Harness-vergelijking §4.3: het model filterde op de instelling, maar rekende de KPI
over de ongefilterde key. +463 in plaats van -1.985, alleen te zien aan
`bron.aantal_waarden: 3893`.
"""

import json

import pandas as pd

from agent.kpi_scope import kpi_naast_filter
from agent.probleem import meldingen
from tools import store
from tools.store import KeyMeta

_HEEL = "duo:p01hoinges:0"
_FILTER = "duo:p01hoinges:0:abc123"


def _laad():
    store.put(_HEEL, pd.DataFrame({"N": range(3893)}), KeyMeta(bron="duo", dataset="p01hoinges", resource=0))
    store.derive(_HEEL, _FILTER, pd.DataFrame({"N": [10, 8]}), stap='filters {"INSTELLINGSNAAM": "HU"}')


def _kpi(key: str, value: str = "+463") -> str:
    return json.dumps({"label": "Groei", "value": value, "bron": {"data_key": key, "aantal_waarden": 3893}})


def _geladen(key: str) -> str:
    return json.dumps({"data_key": key})


def test_kpi_over_de_hele_selectie_naast_een_filter_is_een_probleem():
    _laad()
    [probleem] = kpi_naast_filter("De groei was +463.", [_geladen(_HEEL), _geladen(_FILTER), _kpi(_HEEL)])
    assert "+463" in probleem and _FILTER in probleem
    assert "3893" in meldingen([probleem])[0]


def test_kpi_over_de_gefilterde_selectie_is_goed():
    _laad()
    assert kpi_naast_filter("De groei was +463.", [_geladen(_FILTER), _kpi(_FILTER)]) == []


def test_zonder_filter_in_de_beurt_is_de_hele_selectie_bedoeld():
    _laad()
    assert kpi_naast_filter("De groei was +463.", [_geladen(_HEEL), _kpi(_HEEL)]) == []


def test_kpi_die_de_tekst_niet_noemt_wordt_niet_gemeld():
    _laad()
    assert kpi_naast_filter("Het aantal steeg.", [_geladen(_FILTER), _kpi(_HEEL)]) == []


def test_filter_op_een_andere_bron_telt_niet():
    _laad()
    ander = "cbs:85423NED"
    store.put(ander, pd.DataFrame({"N": [1]}), KeyMeta(bron="cbs", dataset="85423NED"))
    assert kpi_naast_filter("De groei was +463.", [_geladen(_FILTER), _kpi(ander)]) == []
