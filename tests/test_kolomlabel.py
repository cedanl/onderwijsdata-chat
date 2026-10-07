"""Leesbare as- en legendatitels: dezelfde regel als de tabelkop in de frontend (#222, #405)."""

import pytest

from tools.kolomlabel import kolomlabel
from tools.plot import create_plot


@pytest.mark.parametrize(
    ("kop", "label"),
    [
        # Zelfde gevallen als frontend/src/__tests__/kolomKop.test.js
        ("AANTAL_EERSTEJAARS_INGESCHREVENEN", "Aantal eerstejaars ingeschrevenen"),
        ("BRIN_NUMMER_ACTUEEL", "BRIN nummer actueel"),
        ("OPLEIDINGSVORM_BOL_BBL", "Opleidingsvorm BOL BBL"),
        ("CROHO_ONDERDEEL", "CROHO onderdeel"),
        # Een afgeleide labelkolom (#240) heet naar wat hij toont.
        ("STUDIEJAAR_LABEL", "Studiejaar"),
        # Een los woord in hoofdletters ook, vanaf vier letters (#418).
        ("OPLEIDINGSVORM", "Opleidingsvorm"),
        ("STUDIEJAAR", "Studiejaar"),
        # De labelkolom die get_cbs_data naast een CBS-dimensie zet (#163, #418).
        ("Perioden_label", "Perioden"),
    ],
)
def test_bronkolom_wordt_zinsnotatie(kop, label):
    assert kolomlabel(kop) == label


# Korte woorden in hoofdletters zijn meestal codes of afkortingen.
@pytest.mark.parametrize("kop", ["Aantal", "jaar", "WO", "BRIN", "CROHO", "VT", "Instroom per jaar"])
def test_andere_koppen_blijven_staan(kop):
    assert kolomlabel(kop) == kop


def test_titel_uit_de_bron_gaat_voor():
    titels = {"MboStudenten_1": "Mbo-studenten", "Perioden": "Studiejaar"}
    assert kolomlabel("MboStudenten_1", titels) == "Mbo-studenten"
    # Een labelkolom heet naar de titel van haar dimensie.
    assert kolomlabel("Perioden_label", titels) == "Studiejaar"
    assert kolomlabel("Onbekend_1", titels) == "Onbekend_1"


def test_grafiek_toont_leesbare_assen_en_legenda():
    rijen = [
        {"STUDIEJAAR_LABEL": "2022/23", "AANTAL_EERSTEJAARS_INGESCHREVENEN": 10, "OPLEIDINGSVORM_NAAM": "voltijd"},
        {"STUDIEJAAR_LABEL": "2023/24", "AANTAL_EERSTEJAARS_INGESCHREVENEN": 12, "OPLEIDINGSVORM_NAAM": "voltijd"},
    ]
    _, fig = create_plot(
        rijen, "bar", "STUDIEJAAR_LABEL", "AANTAL_EERSTEJAARS_INGESCHREVENEN", "T", color_by="OPLEIDINGSVORM_NAAM"
    )
    assert fig is not None
    assert fig.layout.xaxis.title.text == "Studiejaar"
    assert fig.layout.yaxis.title.text == "Aantal eerstejaars ingeschrevenen"
    assert fig.layout.legend.title.text == "Opleidingsvorm naam"
    # De CSV-export houdt de bronnamen (#217).
    assert fig.layout.meta["x"] == "STUDIEJAAR_LABEL"
