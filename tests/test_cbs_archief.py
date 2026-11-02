"""Een gearchiveerde CBS-tabel zegt overal dat CBS hem niet meer bijwerkt (#865).

Van de CBS-tabellen in het profiel is ongeveer twee derde gearchiveerd. `_archief` stond alleen in de ruwe zoekhit;
in de Bronnen, de bronregel van het rapport en de CSV-header stond zo'n tabel er precies zo bij als een lopende.
Hier de echte catalogus: 71796ned is gearchiveerd met als laatste periode 2016/'17, 85423NED loopt.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.bronvermelding import bronnen_van
from agent.figuurbron import figuurbron
from tools import exportnoten, store
from tools.catalog import archief, bron_titel, search_catalog
from tools.cbs import get_cbs_data
from tools.store import KeyMeta

_ARCHIEF, _LOPEND = "71796ned", "85423NED"
_ETIKET = "gearchiveerd, laatste periode 2016/'17"


def _laad_in_store(dataset: str) -> str:
    key = f"cbs:{dataset}"
    store.put(key, pd.DataFrame({"Perioden": ["2016SJ00"], "Totaal": [1]}), KeyMeta(bron="cbs", dataset=dataset))
    return key


def test_de_titel_van_een_gearchiveerde_tabel_draagt_het_etiket():
    assert bron_titel(_ARCHIEF).endswith(f", {_ETIKET}")
    assert bron_titel(f"cbs:{_ARCHIEF.upper()}") == bron_titel(_ARCHIEF)  # elke spelling van het ID
    assert "gearchiveerd" not in bron_titel(_LOPEND)


def test_zonder_bekende_perioden_alleen_gearchiveerd():
    # 80466ned staat in het archief, maar de catalogus kent zijn perioden niet: dan geen gok.
    assert bron_titel("80466ned").endswith(", gearchiveerd")
    assert archief("80466ned") == {"gearchiveerd": True}


@pytest.mark.parametrize(("dataset", "gearchiveerd"), [(_ARCHIEF, True), (_LOPEND, False)])
def test_bronnen_rapportregel_en_export(dataset, gearchiveerd):
    key = _laad_in_store(dataset)
    [bron] = bronnen_van([("get_cbs_data", json.dumps({"data_key": key}))])
    figuur = figuurbron(key)
    assert figuur is not None
    [bronregel] = [r for r in exportnoten.herkomstregels(key) if r.startswith("bron: ")]

    for tekst in (bron, figuur["tekst"], bronregel):
        assert (_ETIKET in tekst) is gearchiveerd, tekst


@pytest.mark.usefixtures("zonder_scopegrens")
@pytest.mark.parametrize(("dataset", "verwacht"), [(_ARCHIEF, {"laatste_periode": "2016/'17"}), (_LOPEND, None)])
def test_get_cbs_data_meldt_het_archief(dataset, verwacht):
    defs = {"Perioden": {"type": "TimeDimension"}, "Totaal_1": {"type": "Topic"}}
    with (
        patch("tools.cbs.data", return_value=[{"Perioden": "2016SJ00", "Totaal_1": 1}]),
        patch("tools.cbs.definitions", return_value=defs),
    ):
        resultaat = json.loads(get_cbs_data(dataset))

    if verwacht is None:
        assert "gearchiveerd" not in resultaat and "laatste_periode" not in resultaat
    else:
        assert resultaat["gearchiveerd"] is True
        assert resultaat["laatste_periode"] == verwacht["laatste_periode"]
        assert resultaat["catalogus_titel"].endswith(_ETIKET)


def test_de_zoekhit_draagt_het_etiket():
    kandidaten = json.loads(search_catalog("mbo deelnemers woonregio leerweg 1990-2016", source="cbs"))["kandidaten"]
    hit = next(k for k in kandidaten if k["dataset_id"] == _ARCHIEF)
    assert hit["archief"] == _ETIKET
    assert all("archief" not in k for k in kandidaten if not k.get("_archief"))
