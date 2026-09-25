"""Schooljaren: van de vraag naar de broncode en terug, in code in plaats van door het model (#187)."""
import pandas as pd
import pytest

from tools import periode


@pytest.mark.parametrize("tekst", [
    "Hoeveel deeltijdstudenten had de HU in 2025/26?",
    "studiejaar 2025-2026",
    "in 2025/'26",
    "schooljaar 2025–26",
])
def test_eenduidige_schooljaren_uit_de_vraag(tekst):
    assert periode.gevraagde_schooljaren(tekst) == {2025}


def test_los_jaartal_is_dubbelzinnig_en_telt_niet():
    # "2025" kan 2024/25 of 2025/26 zijn: niet raden.
    assert periode.gevraagde_schooljaren("Hoeveel studenten in 2025?") == set()


def test_geen_schooljaar_als_de_jaren_niet_aansluiten():
    assert periode.gevraagde_schooljaren("tussen 2021/2024") == set()


def test_meerdere_schooljaren():
    assert periode.gevraagde_schooljaren("van 2021/22 tot 2025/26") == {2021, 2025}


def test_label_en_broncode():
    assert periode.label(2025) == "2025/26"
    assert periode.label(2099) == "2099/00"
    assert periode.broncode("cbs", 2025) == "2025SJ00"
    assert periode.broncode("duo", 2025) == "STUDIEJAAR=2025"


def test_startjaar_per_bron():
    assert periode.startjaar("cbs", "2024SJ00") == 2024
    assert periode.startjaar("cbs", "2024JJ00") is None  # kalenderjaar, geen schooljaar
    assert periode.startjaar("duo", 2025) == 2025
    assert periode.startjaar("duo", "2025") == 2025


def test_dekking_van_een_selectie():
    df = pd.DataFrame({"STUDIEJAAR": [2024, 2021, 2024], "AANTAL": [1, 2, 3]})
    assert periode.dekking(df, "duo", "STUDIEJAAR") == (2021, 2024)
    assert periode.dekking(df.iloc[0:0], "duo", "STUDIEJAAR") == ()
    assert periode.dekking(df, "duo", None) is None
    assert periode.dekking(df[["AANTAL"]], "duo", "STUDIEJAAR") is None


def test_duo_periodekolom():
    assert periode.duo_periodekolom(["INSTELLINGSCODE", "STUDIEJAAR", "AANTAL"]) == "STUDIEJAAR"
    assert periode.duo_periodekolom(["JAAR", "AANTAL"]) == "JAAR"
    assert periode.duo_periodekolom(["AANTAL"]) is None
