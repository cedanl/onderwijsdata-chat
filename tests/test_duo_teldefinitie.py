"""DUO-teldefinitie en opleidingsvorm-codes komen uit DUO zelf (#172).

Live-audit 5: een model noemde DT 'duaal-tijd' (officieel: deeltijd) en
verwisselde p01 (personen) en p03 (inschrijvingen) zonder dat te melden.
"""

import json
from unittest.mock import patch

import pandas as pd

from tools import duo_meta
from tools.catalog import dataset_details
from tools.duo import get_duo_data

_P01_NOTES = """## Hoger Onderwijs
Het hoger beroepsonderwijs (hbo) en het wetenschappelijk onderwijs (wo) vormen samen het hoger onderwijs.

## Selecties
Ingeschrevenen: van alle inschrijvingen op de peildatum 1 oktober worden de
hoofdinschrijvingen bepaald en geteld als ingeschrevenen (natuurlijke personen).

## Periode
De bestanden worden één keer per jaar bijgewerkt.
"""


def test_selectie_sectie_takes_section_until_next_heading():
    tekst = duo_meta.selectie_sectie(_P01_NOTES)

    assert tekst.startswith("Ingeschrevenen: van alle inschrijvingen")
    assert "natuurlijke personen" in tekst
    assert "één keer per jaar" not in tekst


def test_selectie_sectie_accepts_heading_variants():
    # DUO gebruikt 'Selectie' (44×), 'Selecties' (4×) en 'Selectiecriteria' (1×).
    for kop in ("Selectie", "Selecties", "Selectiecriteria"):
        assert duo_meta.selectie_sectie(f"## {kop}\nTelt personen.\n") == "Telt personen."


def test_selectie_sectie_without_section_is_none():
    assert duo_meta.selectie_sectie("## Inleiding\nIets.\n") is None
    assert duo_meta.selectie_sectie("") is None


def test_selectie_sectie_caps_length_on_a_word_boundary():
    tekst = duo_meta.selectie_sectie("## Selectie\n" + "woord " * 1000)

    assert len(tekst) <= duo_meta._MAX_TEKENS + 2
    assert tekst.endswith(" …")


def test_teldefinitie_does_not_cache_failures():
    # Een tijdelijke CKAN-storing mag niet de rest van het proces 'geen definitie' geven.
    with patch("tools.duo_meta._fetch_notes", side_effect=Exception("timeout")):
        assert duo_meta.teldefinitie("p01hoinges") is None
    with patch("tools.duo_meta._fetch_notes", return_value=_P01_NOTES):
        assert "natuurlijke personen" in duo_meta.teldefinitie("p01hoinges")


def test_get_duo_data_includes_teldefinitie():
    df = pd.DataFrame({"OPLEIDINGSVORM": ["VT", "DT"], "AANTAL_INGESCHREVENEN": [10, 5]})
    with patch("tools.duo._duo.load", return_value=df), \
         patch("tools.duo_meta._fetch_notes", return_value=_P01_NOTES):
        result = json.loads(get_duo_data("p01hoinges", 3))

    assert "natuurlijke personen" in result["teldefinitie"]


def test_get_duo_data_defines_opleidingsvorm_codes():
    df = pd.DataFrame({"OPLEIDINGSVORM": ["VT", "DT"], "AANTAL_INGESCHREVENEN": [10, 5]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("p01hoinges", 3))

    kolom = next(k for k in result["kolommen"] if k["kolom"] == "OPLEIDINGSVORM")
    assert "DT = deeltijd" in kolom["definitie"]


def test_get_duo_data_without_teldefinitie_omits_field():
    df = pd.DataFrame({"AANTAL": [1]})
    with patch("tools.duo._duo.load", return_value=df):
        result = json.loads(get_duo_data("zonder-selectie", 0))

    assert "teldefinitie" not in result


def test_dataset_details_includes_teldefinitie_for_duo():
    entry = {"leverancier": "DUO", "_ckan_id": "p01hoinges", "bron": "Ingeschrevenen hoger onderwijs",
             "_resources": [{"naam": "hbo"}]}
    with patch("tools.catalog._cbs", return_value=[]), \
         patch("tools.catalog._rio_duo", return_value=[entry]), \
         patch("tools.duo_meta._fetch_notes", return_value=_P01_NOTES):
        result = json.loads(dataset_details("p01hoinges"))

    assert "natuurlijke personen" in result["teldefinitie"]
