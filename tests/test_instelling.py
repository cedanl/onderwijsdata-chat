"""Instellingen: welke noemt de vraag, en welke zitten in de data (#143).

Live-audit 2: de chat filterde op 30TX (Aeres Hogeschool) en noemde dat Hogeschool
Utrecht (25DW). De code kwam van het model; niets controleerde code en naam.
"""
import pandas as pd

from tools import instelling

_DF = pd.DataFrame({
    "INSTELLINGSCODE_ACTUEEL": ["25DW", "30TX", "25DW"],
    "INSTELLINGSNAAM_ACTUEEL": ["Hogeschool Utrecht", "Aeres Hogeschool", "Hogeschool Utrecht"],
    "AANTAL": [1, 2, 3],
})
_NAMEN = {"25DW": "Hogeschool Utrecht", "30TX": "Aeres Hogeschool", "21PL": "Universiteit Utrecht"}


def test_codekolom_herkent_ho_en_mbo():
    assert instelling.codekolom(["INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL"]) == "INSTELLINGSCODE_ACTUEEL"
    assert instelling.codekolom(["INSTELLINGSCODE", "INSTELLINGSNAAM"]) == "INSTELLINGSCODE"
    assert instelling.codekolom(["AANTAL"]) is None


def test_dekking_en_namen():
    assert instelling.dekking(_DF, "INSTELLINGSCODE_ACTUEEL") == ("25DW", "30TX")
    assert instelling.dekking(_DF.iloc[0:0], "INSTELLINGSCODE_ACTUEEL") == ()
    assert instelling.dekking(_DF[["AANTAL"]], "INSTELLINGSCODE_ACTUEEL") is None
    assert instelling.namen(_DF, "INSTELLINGSCODE_ACTUEEL") == {"25DW": "Hogeschool Utrecht", "30TX": "Aeres Hogeschool"}


def test_volledige_naam_in_de_vraag():
    vraag = "Hoe ontwikkelde de deelname bij Hogeschool Utrecht zich?"
    assert instelling.genoemde(vraag, _NAMEN) == {"25DW"}


def test_alias_in_de_vraag():
    assert instelling.genoemde("Hoeveel voltijdstudenten had de HU in 2021?", _NAMEN) == {"25DW"}


def test_alias_alleen_als_los_woord_in_hoofdletters():
    # "hu" in een ander woord of in kleine letters is geen instelling.
    assert instelling.genoemde("Hoe huur je een kamer? Schuur.", _NAMEN) == set()


def test_naam_die_in_een_langere_naam_zit_telt_niet_dubbel():
    assert instelling.genoemde("bij Universiteit Utrecht", _NAMEN) == {"21PL"}


def test_geen_instelling_in_de_vraag():
    assert instelling.genoemde("Hoeveel hbo-studenten landelijk?", _NAMEN) == set()
