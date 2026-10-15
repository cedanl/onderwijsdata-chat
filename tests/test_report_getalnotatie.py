"""De conclusie van een rapport schrijft getallen zoals tekst en grafiek: 248.930, niet 248930 (BEV-10).

Dezelfde functie als het chatantwoord (`agent.getalnotatie.nl_notatie`, #236, #445), met dezelfde
taalregel: een Engelse conclusie houdt de notatie van het model (#326).
"""

import json

import plotly.graph_objects as go
import plotly.io as pio
import pytest

from agent.report import _parse_spec_from_response
from agent.report_checks import report_problems

_RESULT = json.dumps({"rijen": [{"STUDIEJAAR": 2022, "AANTAL": 248930}, {"STUDIEJAAR": 2023, "AANTAL": 230450}]})
_FIGURE = pio.to_json(go.Figure(go.Bar(x=[2022, 2023], y=[248930, 230450])))


def _conclusie(conclusie: str) -> str:
    antwoord = json.dumps({"onderzoeksvraag": "Hoeveel studenten?", "beantwoordt": ["Aantal"], "conclusie": conclusie})
    return _parse_spec_from_response(antwoord, [_FIGURE], {"topic": "Hoeveel studenten?"}).conclusie


@pytest.mark.parametrize(
    "geschreven",
    [
        "Het aantal studenten daalde van 248930 in 2022 naar 230450 in 2023.",
        "Het aantal studenten daalde van 248 930 in 2022 naar 230 450 in 2023.",
    ],
)
def test_conclusie_krijgt_duizendtalpunten(geschreven):
    assert _conclusie(geschreven) == "Het aantal studenten daalde van 248.930 in 2022 naar 230.450 in 2023."


def test_jaren_codes_en_decimalen_volgen_nl_notatie():
    conclusie = _conclusie(
        "In 2023 telde dataset 85423NED voor CROHO 34479 in totaal 12345 studenten, gemiddeld 6.4 per groep."
    )
    assert conclusie == (
        "In 2023 telde dataset 85423NED voor CROHO 34479 in totaal 12.345 studenten, gemiddeld 6,4 per groep."
    )


def test_engelse_conclusie_blijft_zoals_het_model_haar_schreef():
    engels = "The number of students fell from 248930 in 2022 to 230450 in 2023, which is a clear decline."
    assert _conclusie(engels) == engels


def test_grondingscontrole_leest_de_omgezette_conclusie():
    antwoord = json.dumps(
        {
            "onderzoeksvraag": "Hoeveel studenten?",
            "beantwoordt": ["Aantal studenten per jaar"],
            "conclusie": "Het aantal studenten daalde van 248930 in 2022 naar 230450 in 2023.",
        }
    )
    spec = _parse_spec_from_response(antwoord, [_FIGURE], {"topic": "Hoeveel studenten?"})
    assert "248.930" in spec.conclusie
    assert report_problems(spec, [_FIGURE], [_RESULT]) == []
