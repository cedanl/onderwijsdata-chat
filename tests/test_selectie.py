"""Past de selectie waarop een antwoord rust bij het gevraagde schooljaar? (#187)

Live-audit 7a: gevraagd naar HU-deeltijd 2025/26 selecteerde Sonnet STUDIEJAAR=2024,
gaf 7.418 en schreef dat 2025/26 niet beschikbaar was. Het juiste getal is 7.408.
De getalcontrole ziet dat niet: 7.418 staat in de tooluitvoer.
"""
import json

import pandas as pd
import pytest

from agent.selectie import ontbrekende_schooljaren
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
