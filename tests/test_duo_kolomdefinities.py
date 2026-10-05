"""Kolomdefinities gelden per dataset (#371).

De lokale patches golden voor elke kolom met die naam: mbo_opleidingsaanbod
(OPLEIDINGSVORM = KLASSIKAAL, COACHING …) kreeg 'Opleidingsvorm hoger onderwijs:
VT/DT/DU', en de mbo-LEERWEG (BBL, BOLVT, EX) alleen 'BOL of BBL'. Deze tests lezen
de echte riodata-glossary: ze zijn het contract tussen de chat en de package.
"""

import json
from unittest.mock import patch

import pandas as pd
import pytest
from riodata import duo as _duo

from tools import periode
from tools.duo import column_definitions, get_duo_data


def test_mbo_aanbod_krijgt_geen_ho_opleidingsvorm():
    definitie = column_definitions(["OPLEIDINGSVORM"], "mbo_opleidingsaanbod")["OPLEIDINGSVORM"]

    assert "KLASSIKAAL" in definitie
    assert "hoger onderwijs" not in definitie


@pytest.mark.parametrize("dataset", ["p01hoinges", "p02ho1ejrs", "p03hoinschr", "p04hogdipl"])
def test_ho_datasets_houden_de_vt_dt_du_codes(dataset):
    assert "DT = deeltijd" in column_definitions(["OPLEIDINGSVORM"], dataset)["OPLEIDINGSVORM"]


def test_onbekende_dataset_krijgt_geen_opleidingsvorm():
    assert "OPLEIDINGSVORM" not in column_definitions(["OPLEIDINGSVORM"], "studentprognoses-mbo-per-instelling")


@pytest.mark.parametrize(
    "dataset",
    [
        "mbo-studenten-per-instelling",
        "mbo-studenten-per-sectorkamer-en-leerweg",
        "instromende-mbo-studenten",
        "gediplomeerde-mbo-studenten",
    ],
)
def test_mbo_leerweg_noemt_de_gepubliceerde_codes(dataset):
    definitie = column_definitions(["LEERWEG"], dataset)["LEERWEG"]

    for code in ("BBL", "BOLVT", "EX"):
        assert code in definitie


@pytest.mark.parametrize("dataset", ["p01hoinges", "p02ho1ejrs", "p03hoinschr"])
def test_studiejaar_is_het_startjaar(dataset):
    assert "Startjaar" in column_definitions(["STUDIEJAAR"], dataset)["STUDIEJAAR"]


def test_chat_en_package_geven_dezelfde_definitie():
    kolommen = ["STUDIEJAAR", "LEERWEG", "OPLEIDINGSVORM", "BRIN_NUMMER"]
    for dataset in ("p01hoinges", "mbo-studenten-per-instelling", "mbo_opleidingsaanbod"):
        upstream = _duo.column_definitions(kolommen, dataset)
        chat = column_definitions(kolommen, dataset)
        assert {k: chat[k] for k in upstream} == upstream


def test_studiejaarlabel_blijft_een_chatdefinitie():
    defs = column_definitions(["STUDIEJAAR", periode.STUDIEJAAR_LABEL], "p01hoinges")

    assert "reken jaren niet zelf om" in defs[periode.STUDIEJAAR_LABEL]


def test_get_duo_data_geeft_de_dataset_door():
    df = pd.DataFrame({"OPLEIDINGSVORM": ["KLASSIKAAL", "COACHING"], "AANTAL": [3, 4]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("mbo_opleidingsaanbod", 0))

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "OPLEIDINGSVORM")
    assert "KLASSIKAAL" in kolom["definitie"]
    assert "hoger onderwijs" not in kolom["definitie"]
