"""Een rapport mag niet iets anders beweren dan zijn eigen data en grafieken (#175),
en is geen lege schil (#189)."""

import json

import plotly.graph_objects as go
import plotly.io as pio

from agent.report import ReportSpec
from agent.report_checks import report_problems

_HU_RESULT = json.dumps({"rijen": [
    {"STUDIEJAAR": 2021 + i, "AANTAL": n} for i, n in enumerate([28355, 27904, 27441, 27135, 26370])
]})
_HU_FIGURE = pio.to_json(go.Figure(go.Scatter(x=[2021, 2022, 2023, 2024, 2025], y=[28355, 27904, 27441, 27135, 26370])))


_VOLLEDIG = {
    "beantwoordt": ["Voltijdstudenten HU per studiejaar"],
    "conclusie": "Het aantal daalde van 28.355 in 2021 naar 26.370 in 2025.",
}


def _spec(**velden) -> ReportSpec:
    return ReportSpec(
        title="Instroom HU", onderzoeksvraag="Hoeveel voltijdstudenten heeft de HU?", **{**_VOLLEDIG, **velden}
    )


def test_audit_tegenvoorbeeld_geen_rijen_naast_gevulde_grafiek():
    # Live-audit 5, letterlijk: de grafiek toonde vijf HU-waarden, de tekst zei dat er geen waren.
    spec = _spec(conclusie="p01hoinges bevat geen rijen met INSTELLINGSCODE_ACTUEEL = 25DW.")

    [probleem] = report_problems(spec, [_HU_FIGURE], [_HU_RESULT])

    assert "geen rijen" in probleem


def test_consistent_rapport_heeft_geen_problemen():
    spec = _spec(conclusie="Het aantal daalde van 28.355 in 2021 naar 26.370 in 2025.")
    assert report_problems(spec, [_HU_FIGURE], [_HU_RESULT]) == []


def test_getal_dat_niet_uit_de_data_komt():
    # Live-audit 6: het Opus-rapport gaf 336.800 waar de data 378.490 had.
    spec = _spec(visualisaties=[{"titel": "Trend", "toelichting": "In 2024 waren het er 336.800.", "figure_json": _HU_FIGURE}])

    [probleem] = report_problems(spec, [_HU_FIGURE], [_HU_RESULT])

    assert "336.800" in probleem


def test_afwezigheid_in_beantwoordt_niet_is_toegestaan():
    # "Wat dit rapport niet beantwoordt" noemt legitiem wat de data niet bevat.
    spec = _spec(beantwoordt_niet=["De data bevat geen cijfers over uitval."])
    assert report_problems(spec, [_HU_FIGURE], [_HU_RESULT]) == []


def test_afwezigheid_zonder_gevulde_grafiek_is_geen_tegenspraak():
    spec = _spec(conclusie="Er zijn geen data voor deze instelling.")
    assert not any("wel waarden" in p for p in report_problems(spec, [], [_HU_RESULT]))


def test_lege_schil_is_onvolledig():
    # Live-audit 7b en 8: alleen onderzoeksvraag en bron, report_ready werd toch verstuurd.
    spec = _spec(beantwoordt=[], conclusie="")

    problemen = report_problems(spec, [], [_HU_RESULT])

    assert any("conclusie" in p for p in problemen)
    assert any("reikwijdte" in p for p in problemen)
    assert any("getal of grafiek" in p for p in problemen)


def test_reikwijdte_mag_ook_alleen_zeggen_wat_niet_beantwoord_wordt():
    spec = _spec(beantwoordt=[], beantwoordt_niet=["Uitval valt buiten dit rapport."])
    assert report_problems(spec, [_HU_FIGURE], [_HU_RESULT]) == []


def test_grafiek_zonder_getal_in_de_tekst_is_volledig():
    spec = _spec(
        conclusie="Het aantal voltijdstudenten daalde elk jaar.",
        visualisaties=[{"titel": "Trend", "toelichting": "", "figure_json": _HU_FIGURE}],
    )
    assert report_problems(spec, [_HU_FIGURE], [_HU_RESULT]) == []


def test_conclusie_zonder_getal_en_zonder_grafiek_is_onvolledig():
    spec = _spec(conclusie="Het aantal voltijdstudenten daalde elk jaar.")
    assert any("getal of grafiek" in p for p in report_problems(spec, [], [_HU_RESULT]))
