"""Het label bij een CBS-getal klopt met de gekozen selectie (#401, audit 14 §3.2).

'Hoeveel studenten heeft Utrecht?' gaf 118.160 als 'ingeschreven personen (leerlingen +
studenten, alle onderwijssoorten)'. In de bron is dat A025279, 'Totaal (speciaal)
basisonderwijs'. Het getal stond in de tooluitvoer; alleen het label was fout.
"""

import json

import pandas as pd
import pytest

from agent.dimensielabels import selectie_regels, verkeerde_dimensielabels
from agent.telling import telling_blok
from tools import cbs, store
from tools.store import KeyMeta

_TABEL = pd.DataFrame(
    {
        "Onderwijssoort": ["T001038", "A025279", "A025280"],
        "Onderwijssoort_label": ["Totaal onderwijssoorten", "Totaal (speciaal) basisonderwijs", "Basisonderwijs"],
        "RegioS": ["PV26", "PV26", "PV26"],
        "RegioS_label": ["Utrecht (PV)", "Utrecht (PV)", "Utrecht (PV)"],
        "Perioden": ["2024JJ00"] * 3,
        "Leerlingen_1": [400000, 118160, 110000],
    }
)


def _beurt(*keys: str) -> list[str]:
    return [json.dumps({"data_key": k}) for k in keys]


@pytest.fixture(autouse=True)
def _cbs():
    store.clear()
    cbs.register_dimensions("85701NED", ["Onderwijssoort", "RegioS", "Perioden"])
    store.put("cbs:85701NED", _TABEL, KeyMeta(bron="cbs", dataset="85701NED", periodekolom="Perioden"))
    yield
    store.clear()
    cbs.clear_dimensions()


def _selectie(*codes: str) -> str:
    key = f"cbs:85701NED:{'-'.join(codes)}"
    store.derive("cbs:85701NED", key, _TABEL[_TABEL["Onderwijssoort"].isin(codes)])
    return key


def test_alle_onderwijssoorten_bij_alleen_basisonderwijs_is_een_probleem():
    tekst = "Utrecht telt 118.160 ingeschreven personen (leerlingen + studenten, alle onderwijssoorten)."
    problemen = verkeerde_dimensielabels(tekst, _beurt("cbs:85701NED", _selectie("A025279")))

    assert any("alle onderwijssoorten" in p and "Totaal (speciaal) basisonderwijs" in p for p in problemen)


def test_studenten_bij_een_selectie_van_basisonderwijs_is_een_probleem():
    problemen = verkeerde_dimensielabels("Utrecht heeft 118.160 studenten.", _beurt(_selectie("A025279")))

    assert any("studenten" in p and "leerlingen" in p for p in problemen)


def test_leerlingen_bij_basisonderwijs_is_in_orde():
    assert verkeerde_dimensielabels("Utrecht heeft 118.160 leerlingen.", _beurt(_selectie("A025279"))) == []


def test_alle_onderwijssoorten_bij_het_totaal_is_in_orde():
    tekst = "Utrecht telt 400.000 leerlingen en studenten in alle onderwijssoorten."
    assert verkeerde_dimensielabels(tekst, _beurt(_selectie("T001038"))) == []


def test_een_selectie_met_meerdere_onderwijssoorten_zwijgt():
    tekst = "Alle onderwijssoorten samen, uitgesplitst."
    assert verkeerde_dimensielabels(tekst, _beurt(_selectie("T001038", "A025279"))) == []


def test_zonder_cbs_data_zwijgt_de_controle():
    store.put("duo:p01hoinges:0", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    assert verkeerde_dimensielabels("Alle onderwijssoorten, 1 student.", _beurt("duo:p01hoinges:0")) == []


def test_selectieregel_noemt_de_gekozen_labels_en_niet_de_periode():
    [regel] = selectie_regels(_beurt("cbs:85701NED", _selectie("A025279")))

    assert "85701NED" in regel
    assert "Onderwijssoort: Totaal (speciaal) basisonderwijs" in regel
    assert "RegioS: Utrecht (PV)" in regel
    assert "Perioden" not in regel


def test_de_gekozen_labels_staan_in_het_telling_blok():
    assert "Totaal (speciaal) basisonderwijs" in telling_blok(_beurt(_selectie("A025279")))


def test_een_dimensie_met_veel_waarden_is_geen_selectie():
    [regel] = selectie_regels(_beurt("cbs:85701NED"))

    assert "Onderwijssoort" not in regel and "RegioS: Utrecht (PV)" in regel
