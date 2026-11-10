"""Een rapport staat op zichzelf: geen verwijzing naar het gesprek, geen figuur die er niet in staat (#994).

Rapport 0573ff89 (demo, test, 10-11) had één staafgrafiek; de toelichting zei "De Sankey-visualisatie uit het gesprek
toont dezelfde gegevens als stroomdiagram."
"""

import json
import logging

import plotly.graph_objects as go
import plotly.io as pio
import pytest

from agent.figuurverwijzing import SOORTEN, figuursoorten, gesprek_als_vindplaats, verkeerde_figuurverwijzing
from agent.probleem import controlenamen, harde
from agent.report import RapportGeweigerd
from agent.report_checks import report_problems
from agent.stream import StreamResult
from tests.test_report_checks import _HU_FIGURE, _HU_RESULT, _PLOT, _rapportrun, _spec

_ZIN_0573FF89 = "De Sankey-visualisatie uit het gesprek toont dezelfde gegevens als stroomdiagram."

_BAR = pio.to_json(go.Figure(go.Bar(x=["Zorg", "Techniek"], y=[412, 120])))
_LIGGEND = pio.to_json(go.Figure(go.Bar(x=[412, 120], y=["Zorg", "Techniek"], orientation="h")))
_SANKEY = pio.to_json(
    go.Figure(go.Sankey(node={"label": ["Mbo", "Hbo"]}, link={"source": [0], "target": [1], "value": [412]}))
)
_LIJN = pio.to_json(go.Figure(go.Scatter(x=[2021, 2022], y=[412, 420], mode="lines+markers")))
_PUNTEN = pio.to_json(go.Figure(go.Scatter(x=[1, 2], y=[412, 420], mode="markers")))
_TAART = pio.to_json(go.Figure(go.Pie(labels=["Zorg", "Techniek"], values=[412, 120])))
_CHOROPLETH = pio.to_json(go.Figure(go.Choropleth(locations=["PV20"], z=[412])))
_CHOROPLETHMAP = pio.to_json(go.Figure(go.Choroplethmap(locations=["PV20"], z=[412])))


def _met_toelichting(toelichting: str, figuur: str):
    return _spec(visualisaties=[{"titel": "Doorstroom", "toelichting": toelichting, "figure_json": figuur}])


def test_de_zin_uit_het_rapport_naast_een_staafgrafiek_is_hard():
    problemen = report_problems(_met_toelichting(_ZIN_0573FF89, _BAR), [_BAR], [_HU_RESULT])

    assert {"verkeerde_figuurverwijzing", "gesprek_als_vindplaats"} <= set(controlenamen(problemen))
    figuur = [p for p in problemen if getattr(p, "controle", None) == "verkeerde_figuurverwijzing"]
    assert figuur and harde(figuur) == figuur
    assert "sankey-diagram" in figuur[0] and "Sankey-visualisatie" in figuur[0]


def test_dezelfde_zin_naast_een_sankey_noemt_geen_verkeerde_figuur():
    zonder_gesprek = "De Sankey-visualisatie toont dezelfde gegevens als stroomdiagram."

    assert report_problems(_met_toelichting(zonder_gesprek, _SANKEY), [_SANKEY], [_HU_RESULT]) == []
    # Met "uit het gesprek" blijft de verwijzing naar het gesprek hard, ook naast een sankey.
    problemen = report_problems(_met_toelichting(_ZIN_0573FF89, _SANKEY), [_SANKEY], [_HU_RESULT])
    assert controlenamen(problemen) == ["gesprek_als_vindplaats"] and harde(problemen) == problemen


@pytest.mark.parametrize(
    "tekst",
    [
        "Zoals in de chat getoond daalt het aantal.",
        "Eerder in het gesprek bleek dat het aantal daalt.",
        "De grafiek in het gesprek toont een daling.",
        "Voor de details: zie de chat.",
        "De cijfers uit de chat laten een daling zien.",
    ],
)
@pytest.mark.parametrize("figuur", [_BAR, _SANKEY, _HU_FIGURE])
def test_het_gesprek_als_vindplaats_is_hard_bij_elke_figuur(tekst, figuur):
    problemen = report_problems(_spec(beantwoordt=["Voltijdstudenten HU per studiejaar", tekst]), [figuur], [])

    gesprek = [p for p in problemen if getattr(p, "controle", None) == "gesprek_als_vindplaats"]
    assert gesprek and harde(gesprek) == gesprek
    assert "ziet het gesprek niet" in gesprek[0]


@pytest.mark.parametrize(
    "tekst",
    [
        "Een chatbot telt niet als bron.",
        "Het gesprek met de opleiding staat buiten dit rapport.",
        "Chatten is populair.",
    ],
)
def test_de_chat_als_onderwerp_is_geen_vindplaats(tekst):
    assert gesprek_als_vindplaats(tekst) == []


@pytest.mark.parametrize(
    ("woord", "soort"),
    [
        ("Het stroomdiagram toont de doorstroom.", "sankey"),
        ("De kaart toont de provincies.", "kaart"),
        ("Het taartdiagram toont de verdeling.", "taartdiagram"),
        ("Het spreidingsdiagram toont het verband.", "spreidingsdiagram"),
        ("De lijngrafiek toont de trend.", "lijngrafiek"),
        ("Het staafdiagram toont de sectoren.", "staafdiagram"),
        ("De staafgrafiek toont de sectoren.", "staafdiagram"),
        ("De heatmap toont de cellen.", "heatmap"),
        ("De treemap toont de verdeling.", "treemap"),
    ],
)
def test_elke_grafieksoort_zonder_figuur_is_een_probleem(woord, soort):
    andere = _SANKEY if soort != "sankey" else _BAR

    [probleem] = verkeerde_figuurverwijzing(woord, [andere])

    assert SOORTEN[soort].naam in probleem.melding


@pytest.mark.parametrize(
    ("tekst", "figuur"),
    [
        ("Het staafdiagram toont de sectoren.", _BAR),
        ("De staafgrafiek toont de sectoren.", _LIGGEND),
        ("De kaart toont de provincies.", _CHOROPLETH),
        ("De kaart toont de provincies.", _CHOROPLETHMAP),
        ("De lijngrafiek toont de trend.", _LIJN),
        ("De lijngrafiek toont de trend.", _HU_FIGURE),
        ("Het spreidingsdiagram toont het verband.", _PUNTEN),
        ("Het taartdiagram toont de verdeling.", _TAART),
        ("Het Sankey-diagram toont de stromen.", _SANKEY),
        # Een uitdrukking, geen kaart.
        ("Dit rapport brengt de doorstroom in kaart.", _BAR),
    ],
)
def test_geen_valse_melding_bij_de_juiste_figuur(tekst, figuur):
    assert verkeerde_figuurverwijzing(tekst, [figuur]) == []


def test_de_soort_van_een_figuur_komt_uit_het_tracetype_en_de_mode():
    assert figuursoorten([_BAR, _LIGGEND]) == {"staafdiagram"}
    assert figuursoorten([_LIJN]) == {"lijngrafiek"}
    assert figuursoorten([_PUNTEN]) == {"spreidingsdiagram"}
    assert figuursoorten([_HU_FIGURE]) == {"lijngrafiek", "spreidingsdiagram"}
    assert figuursoorten([_CHOROPLETH, _CHOROPLETHMAP, _TAART, _SANKEY]) == {"kaart", "taartdiagram", "sankey"}


def test_beantwoordt_niet_mag_een_ontbrekende_kaart_noemen():
    spec = _spec(beantwoordt_niet=["Een kaart per gemeente: de data heeft geen gemeenten."])

    assert report_problems(spec, [_HU_FIGURE], [_HU_RESULT]) == []


# ── Na de herkansing nog steeds fout: het rapport wordt geweigerd (#994) ──

_VERWIJZING = json.dumps(
    {
        "onderzoeksvraag": "Hoeveel voltijdstudenten heeft de HU?",
        "beantwoordt": ["Voltijdstudenten HU per studiejaar"],
        "visualisaties": [{"titel": "Instroom", "toelichting": _ZIN_0573FF89}],
        "conclusie": "Het aantal daalde van 28.355 in 2021 naar 26.370 in 2025.",
    }
)
_HERSTELD = json.dumps(
    {**json.loads(_VERWIJZING), "visualisaties": [{"titel": "Instroom", "toelichting": "De lijn daalt."}]}
)


def test_een_verwijzing_die_na_de_herkansing_blijft_weigert_het_rapport(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    stappen = [
        StreamResult(text="", tool_calls=[_PLOT]),
        StreamResult(text=_VERWIJZING, tool_calls=[]),
        StreamResult(text=_VERWIJZING, tool_calls=[]),
    ]

    with pytest.raises(RapportGeweigerd):
        _rapportrun(monkeypatch, stappen)

    berichten = [r.getMessage() for r in caplog.records]
    assert "RAPPORT GEWEIGERD: controles=['gesprek_als_vindplaats', 'verkeerde_figuurverwijzing']" in berichten


def test_een_verwijzing_die_de_herkansing_herstelt_geeft_het_rapport(monkeypatch):
    stappen = [
        StreamResult(text="", tool_calls=[_PLOT]),
        StreamResult(text=_VERWIJZING, tool_calls=[]),
        StreamResult(text=_HERSTELD, tool_calls=[]),
    ]

    spec = _rapportrun(monkeypatch, stappen)

    assert spec.visualisaties[0]["toelichting"] == "De lijn daalt."
