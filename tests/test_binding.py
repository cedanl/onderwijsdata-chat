"""Staat een getal bij het jaar en de instelling van zijn eigen rij? (#197)

Live-audit 8, lokale reproductie: HU p01 VT 2024/25 = 27.135 en 2025/26 = 26.370.
De zin "2025/26 = 27.135" kwam door getal- en periodecontrole, omdat beide jaren
en beide getallen in dezelfde selectie stonden.
"""
import json

import pandas as pd
import pytest

from agent.binding import verkeerd_gebonden
from tools import store
from tools.store import KeyMeta

_KEY = "duo:p01hoinges:3:sel"


@pytest.fixture(autouse=True)
def _selectie():
    store.clear()
    df = pd.DataFrame({
        "STUDIEJAAR": [2024, 2025, 2024, 2025],
        "INSTELLINGSCODE_ACTUEEL": ["25DW", "25DW", "30TX", "30TX"],
        "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht"] * 2 + ["Aeres Hogeschool"] * 2,
        "AANTAL": [27135, 26370, 2991, 2880],
    })
    store.put(_KEY, df, KeyMeta(bron="duo", dataset="p01hoinges", periodekolom="STUDIEJAAR",
                                instellingskolom="INSTELLINGSCODE_ACTUEEL", afgeleid_van="duo:p01hoinges:3"))
    yield
    store.clear()


def _beurt() -> list[str]:
    return [json.dumps({"data_key": _KEY})]


def test_getal_van_een_ander_geselecteerd_jaar():
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 27.135 voltijdstudenten.", _beurt())
    assert "27.135" in probleem and "2024/25" in probleem and "2025/26" in probleem


def test_getal_bij_zijn_eigen_jaar_is_goed():
    assert verkeerd_gebonden("In 2025/26 waren het 26.370 voltijdstudenten.", _beurt()) == []


def test_verwisselde_rij_in_een_markdowntabel():
    tabel = "| Schooljaar | Aantal |\n|---|---|\n| 2024/25 | 27.135 |\n| 2025/26 | 27.135 |"
    [probleem] = verkeerd_gebonden(tabel, _beurt())
    assert "2025/26" in probleem


def test_getal_van_een_andere_geselecteerde_instelling():
    [probleem] = verkeerd_gebonden("Hogeschool Utrecht telde 2.880 voltijdstudenten.", _beurt())
    assert "Aeres Hogeschool" in probleem


def test_getal_zonder_jaar_of_instelling_in_de_zin_is_ongewijzigd():
    assert verkeerd_gebonden("Het waren er 27.135.", _beurt()) == []


def test_zin_met_twee_jaren_is_niet_eenduidig():
    tekst = "Van 27.135 in 2024/25 naar 26.370 in 2025/26."
    assert verkeerd_gebonden(tekst, _beurt()) == []


def test_getal_dat_niet_in_de_rijen_staat_is_niet_aan_deze_controle():
    # Een som of KPI: de getalcontrole beslist daarover, niet deze.
    assert verkeerd_gebonden("In 2025/26 samen 29.250.", _beurt()) == []


def test_cbs_label_zonder_periodecode():
    # Sinds #194 kan een selectie Perioden_label houden zonder Perioden.
    store.put("cbs:85423NED:x", pd.DataFrame({
        "Perioden_label": ["2024/'25", "2025/'26*"], "TotaalIngeschrevenen_1": [378490, 367960],
    }), KeyMeta(bron="cbs", dataset="85423NED", periodekolom="Perioden", afgeleid_van="cbs:85423NED"))
    [probleem] = verkeerd_gebonden("In 2025/26 waren het 378.490.", [json.dumps({"data_key": "cbs:85423NED:x"})])
    assert "2024/25" in probleem
