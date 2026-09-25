"""Past de selectie waarop een antwoord rust bij het gevraagde schooljaar? (#187)

Live-audit 7a: gevraagd naar HU-deeltijd 2025/26 selecteerde Sonnet STUDIEJAAR=2024,
gaf 7.418 en schreef dat 2025/26 niet beschikbaar was. Het juiste getal is 7.408.
De getalcontrole ziet dat niet: 7.418 staat in de tooluitvoer.
"""
import json

import pandas as pd
import pytest

from agent.selectie import ontbrekende_instellingen, ontbrekende_schooljaren
from tools import store
from tools.query import query_data
from tools.store import KeyMeta

_KEY = "duo:p01hoinges:3"


@pytest.fixture(autouse=True)
def _reeks():
    store.clear()
    df = pd.DataFrame({"STUDIEJAAR": [2024, 2025], "OPLEIDINGSVORM": ["DT", "DT"], "AANTAL": [7418, 7408]})
    store.put(_KEY, df, KeyMeta(bron="duo", dataset="p01hoinges", resource=3,
                                periodekolom="STUDIEJAAR", schooljaren=(2024, 2025)))
    yield
    store.clear()


def _selectie(**kwargs) -> str:
    return query_data(_KEY, **kwargs)


def test_verkeerd_jaar_geselecteerd_terwijl_het_gevraagde_er_is():
    problemen = ontbrekende_schooljaren("Hoeveel deeltijdstudenten had de HU in 2025/26?",
                                        [_selectie(filters={"STUDIEJAAR": 2024})])

    assert len(problemen) == 1
    assert "2025/26" in problemen[0] and "2024/25" in problemen[0] and "STUDIEJAAR=2025" in problemen[0]


def test_gevraagd_jaar_in_de_selectie_is_goed():
    assert ontbrekende_schooljaren("in 2025/26?", [_selectie(filters={"STUDIEJAAR": 2025})]) == []


def test_ook_na_aggregatie_zonder_periodekolom_telt_de_selectie():
    resultaat = _selectie(filters={"STUDIEJAAR": 2024}, group_by=["OPLEIDINGSVORM"], aggregate={"AANTAL": "sum"})
    assert ontbrekende_schooljaren("in 2025/26?", [resultaat]) != []


def test_jaar_dat_niet_in_de_data_staat_is_geen_selectiefout():
    # 2035/36 bestaat niet: dan mag het model zeggen dat het er niet is.
    assert ontbrekende_schooljaren("in 2035/36?", [_selectie(filters={"STUDIEJAAR": 2024})]) == []


def test_zonder_eenduidig_schooljaar_in_de_vraag_geen_controle():
    assert ontbrekende_schooljaren("Hoeveel in 2025?", [_selectie(filters={"STUDIEJAAR": 2024})]) == []


def test_alleen_de_laadstap_is_geen_selectie():
    laad = json.dumps({"data_key": _KEY, "preview": []})
    assert ontbrekende_schooljaren("in 2025/26?", [laad]) == []


def test_een_reeks_met_het_gevraagde_jaar_is_goed():
    assert ontbrekende_schooljaren("van 2024/25 tot 2025/26", [_selectie(filters={"STUDIEJAAR__gte": 2024})]) == []


# ── Instellingen (#143) ──

_HO = "duo:p01hoinges:3:inst"


@pytest.fixture
def _instellingen():
    df = pd.DataFrame({"INSTELLINGSCODE_ACTUEEL": ["25DW", "30TX"],
                       "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht", "Aeres Hogeschool"],
                       "AANTAL": [26370, 2880]})
    store.put(_HO, df, KeyMeta(bron="duo", dataset="p01hoinges", resource=3,
                               instellingskolom="INSTELLINGSCODE_ACTUEEL", instellingen=("25DW", "30TX")))


def test_andere_instelling_geselecteerd_dan_gevraagd(_instellingen):
    # Live-audit 2: gevraagd de HU, gefilterd op 30TX.
    resultaat = query_data(_HO, filters={"INSTELLINGSCODE_ACTUEEL": "30TX"})

    problemen = ontbrekende_instellingen("Hoe ontwikkelde de HU zich?", [resultaat])

    assert len(problemen) == 1
    assert "Hogeschool Utrecht (25DW)" in problemen[0] and "Aeres Hogeschool (30TX)" in problemen[0]
    assert "INSTELLINGSCODE_ACTUEEL=25DW" in problemen[0]


def test_gevraagde_instelling_in_de_selectie_is_goed(_instellingen):
    resultaat = query_data(_HO, filters={"INSTELLINGSCODE_ACTUEEL": "25DW"})
    assert ontbrekende_instellingen("bij Hogeschool Utrecht", [resultaat]) == []


def test_vergelijking_met_alle_instellingen_is_goed(_instellingen):
    resultaat = query_data(_HO, filters={"AANTAL__gte": 0})
    assert ontbrekende_instellingen("de HU vergeleken met Aeres Hogeschool", [resultaat]) == []


def test_instelling_die_niet_in_de_data_staat_is_geen_selectiefout(_instellingen):
    resultaat = query_data(_HO, filters={"INSTELLINGSCODE_ACTUEEL": "30TX"})
    assert ontbrekende_instellingen("bij de HvA", [resultaat]) == []
