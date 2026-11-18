"""Een rapportfiguur blijft zoals de gebruiker haar in het gesprek zag (#993).

Tot #993 sneed de code een grafiek van het rapportmodel bij tot de periode in haar titel of in de vraag (#385). Het
rapport toont nu alleen figuren uit het gesprek (besluit 18-11): een periode in een titel snijdt niets meer weg.
"""

import json

import pandas as pd
import plotly.io as pio
import pytest

from agent.report import _parse_spec_from_response
from tools import store
from tools.plot import create_plot


def _figuur(rijen: list[dict], x: str = "STUDIEJAAR", color_by: str | None = None) -> str:
    store.put("test:385", pd.DataFrame(rijen))
    _, fig = create_plot(chart_type="line", x=x, y="AANTAL", title="Aantal", color_by=color_by, data_key="test:385")
    return pio.to_json(fig)


ELF_JAAR = [{"STUDIEJAAR": j, "AANTAL": 1000 + j} for j in range(2015, 2026)]


@pytest.mark.parametrize(
    ("titel", "vraag"),
    [
        ("Aantal mbo-studenten 2020/21-2024/25", "Hoeveel mbo-studenten de laatste vijf jaar?"),
        ("Studenten per schooljaar", "Hoeveel mbo-studenten van 2020/21 tot en met 2024/25?"),
        ("Per jaar", "Hoeveel mbo-studenten?"),
    ],
)
def test_een_periode_in_titel_of_vraag_snijdt_de_figuur_niet_bij(titel, vraag):
    figuur = _figuur(ELF_JAAR)
    spec = _parse_spec_from_response(
        json.dumps({"visualisaties": [{"titel": titel}], "conclusie": "..."}),
        figures_json=[figuur],
        context={"topic": vraag},
    )

    assert spec.visualisaties[0]["figure_json"] == figuur
