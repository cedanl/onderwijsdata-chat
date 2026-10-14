"""Een rapport mag niet iets anders beweren dan zijn eigen data en grafieken (#175),
en is geen lege schil (#189)."""

import asyncio
import importlib
import json
import logging
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest

from agent import report
from agent.probleem import Probleem, controlenamen, harde
from agent.report import RapportGeweigerd, ReportSpec
from agent.report_checks import report_problems
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

loop_module = importlib.import_module("agent.loop")

_HU_RESULT = json.dumps(
    {"rijen": [{"STUDIEJAAR": 2021 + i, "AANTAL": n} for i, n in enumerate([28355, 27904, 27441, 27135, 26370])]}
)
_HU_FIGURE = pio.to_json(go.Figure(go.Scatter(x=[2021, 2022, 2023, 2024, 2025], y=[28355, 27904, 27441, 27135, 26370])))


_VOLLEDIG: dict[str, Any] = {
    "title": "Instroom HU",
    "onderzoeksvraag": "Hoeveel voltijdstudenten heeft de HU?",
    "beantwoordt": ["Voltijdstudenten HU per studiejaar"],
    "conclusie": "Het aantal daalde van 28.355 in 2021 naar 26.370 in 2025.",
}


def _spec(**velden) -> ReportSpec:
    return ReportSpec(**{**_VOLLEDIG, **velden})


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
    spec = _spec(
        visualisaties=[{"titel": "Trend", "toelichting": "In 2024 waren het er 336.800.", "figure_json": _HU_FIGURE}]
    )

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


def test_verkeerde_opleidingsvorm_in_de_reikwijdte():
    # Live-audit 8 (#196): juiste p01-waarden, maar "Deeltijd (DU)" in de reikwijdte.
    store.clear()
    store.put("duo:p01hoinges:3", pd.DataFrame({"AANTAL": [26370]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    resultaat = json.dumps({"data_key": "duo:p01hoinges:3", **json.loads(_HU_RESULT)})
    spec = _spec(beantwoordt=["Deeltijd (DU) bij de HU, 2021–2025"])

    [probleem] = report_problems(spec, [_HU_FIGURE], [resultaat])
    store.clear()

    assert "duaal" in probleem


def test_resource_nummer_in_de_rapporttekst_wordt_afgewezen():
    # #329: "resource 3" zegt een lezer niets.
    spec = _spec(conclusie="Uit resource 3 blijkt een daling van 28.355 naar 26.370.")

    [probleem] = report_problems(spec, [_HU_FIGURE], [_HU_RESULT])

    assert "resource 3" in probleem


def test_rapport_met_tekstselectie_crasht_niet():
    """#392: het rapportpad draait dezelfde bindingscontrole; een selectie zonder getallen gaf een ValueError."""
    store.clear()
    key = "rio:onderwijsaanbieders:1:sel"
    store.put(key, pd.DataFrame({"naam": ["Hogeschool Utrecht"]}), KeyMeta(bron="rio", dataset="x", afgeleid_van=key))
    try:
        assert report_problems(_spec(), [_HU_FIGURE], [_HU_RESULT, json.dumps({"data_key": key})]) == []
    finally:
        store.clear()


def test_controle_die_faalt_vervangt_het_rapport_niet(monkeypatch, caplog):
    """Een fout in een controle wordt gelogd met een fout-ID; de andere controles gaan door (#392).

    Het rapport zegt dat het op dat punt niet gecontroleerd is, als zachte melding (#419).
    """

    def kapot(*_):
        raise ValueError("zip() argument 3 is shorter than arguments 1-2")

    monkeypatch.setattr("agent.report_checks.verkeerd_gebonden", kapot)
    spec = _spec(conclusie="p01hoinges bevat geen rijen met INSTELLINGSCODE_ACTUEEL = 25DW.")
    with caplog.at_level("DEBUG"):
        probleem, niet_gecontroleerd = report_problems(spec, [_HU_FIGURE], [_HU_RESULT])
    assert "geen rijen" in probleem
    assert isinstance(niet_gecontroleerd, Probleem)
    assert niet_gecontroleerd.niet_gecontroleerd and not niet_gecontroleerd.hard
    assert "Interne fout" in caplog.text and "kapot" in caplog.text
    # De fouttekst staat alleen op DEBUG (#502).
    assert "zip()" in caplog.text
    boven_debug = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert boven_debug and all(r.exc_info is None and "zip()" not in r.getMessage() for r in boven_debug)


# ── Elke rapportcontrole heeft een naam, voor het log en de afvuurfrequentie (CH-01) ──

_INLINE = ["ontbrekende_onderdelen", "ongedekte_getallen", "afwezigheid_naast_grafiek", "resource_verwijzing"]


def test_elk_rapportprobleem_noemt_zijn_controle():
    """Het log zei `controles=['None']` bij een rapportcontrole zonder naam: die herkansing was niet te tellen."""
    spec = _spec(conclusie="", beantwoordt=["Er zijn geen data over 336.800 studenten in p99xxxyyy; zie resource 3."])

    problemen = report_problems(spec, [_HU_FIGURE], [_HU_RESULT])

    assert all(isinstance(p, Probleem) and isinstance(p.controle, str) and p.controle for p in problemen)
    assert set(controlenamen(problemen)) == {*_INLINE, "onbekende_datasets"}


def test_een_falende_rapportcontrole_noemt_ook_haar_naam(monkeypatch):
    def verkeerd_gebonden(*_):
        raise ValueError("kapot")

    monkeypatch.setattr("agent.report_checks.verkeerd_gebonden", verkeerd_gebonden)

    [stuk] = report_problems(_spec(), [_HU_FIGURE], [_HU_RESULT])

    assert stuk.niet_gecontroleerd and stuk.controle == "verkeerd_gebonden"


@pytest.mark.parametrize(
    ("velden", "naam", "streng", "teksten"),
    [
        (
            {"beantwoordt": [], "conclusie": ""},
            "ontbrekende_onderdelen",
            True,
            [
                ("Het rapport heeft geen conclusie.",) * 2,
                ("Het rapport heeft geen reikwijdte (beantwoordt / beantwoordt_niet).",) * 2,
                ("Het rapport bevat geen getal of grafiek uit de data.",) * 2,
            ],
        ),
        (
            {"conclusie": "In 2024 waren het er 336.800 en 1.234.567."},
            "ongedekte_getallen",
            True,
            [("Deze getallen staan niet in de opgehaalde data: 336.800, 1.234.567.",) * 2],
        ),
        (
            {"conclusie": "p01hoinges bevat geen rijen met INSTELLINGSCODE_ACTUEEL = 25DW."},
            "afwezigheid_naast_grafiek",
            True,
            [("De tekst zegt 'bevat geen rijen', maar de grafiek in het rapport bevat wel waarden.",) * 2],
        ),
        (
            {"conclusie": "Uit resource 3 blijkt een daling van 28.355 naar 26.370."},
            "resource_verwijzing",
            False,
            [
                (
                    "De tekst verwijst naar 'resource 3', dat een lezer niets zegt. "
                    "Noem het bestand bij zijn titel of laat de verwijzing weg.",
                    "De tekst verwijst naar 'resource 3', dat een lezer niets zegt.",
                )
            ],
        ),
    ],
    ids=_INLINE,
)
def test_rapportcontrole_heeft_een_vaste_naam_en_dezelfde_hardheid_en_tekst(velden, naam, streng, teksten):
    figuren = [] if naam == "ontbrekende_onderdelen" else [_HU_FIGURE]

    problemen = report_problems(_spec(**velden), figuren, [_HU_RESULT])

    assert controlenamen(problemen) == [naam]
    assert harde(problemen) == (problemen if streng else [])
    assert [(str(p), p.melding) for p in problemen] == teksten


# ── Van toolloop tot log: de herkansing en de weigering noemen de controle (CH-01, #475) ──

_ONGEDEKT = json.dumps(
    {
        "onderzoeksvraag": "Hoeveel voltijdstudenten heeft de HU?",
        "beantwoordt": ["Voltijdstudenten HU per studiejaar"],
        "conclusie": "In 2024 waren het er 336.800.",
    }
)


def _rapport_met_ongedekt_getal(monkeypatch) -> None:
    stappen = [
        StreamResult(text="", tool_calls=[{"id": "q1", "name": "query_data", "arguments": '{"data_key": "k"}'}]),
        StreamResult(text=_ONGEDEKT, tool_calls=[]),
        StreamResult(text=_ONGEDEKT, tool_calls=[]),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def emit(event: dict) -> None:
        pass

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", lambda name, args: (_HU_RESULT, None))
    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "k"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")

    asyncio.run(report.generate({}, emit, model="openai/gpt-4o", stop_event=asyncio.Event()))


def test_herkansing_en_weigering_van_een_rapport_noemen_de_controle_en_geen_getal(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    with pytest.raises(RapportGeweigerd):
        _rapport_met_ongedekt_getal(monkeypatch)

    berichten = [r.getMessage() for r in caplog.records]
    [mislukt] = [b for b in berichten if b.startswith("CONTROLE MISLUKT")]
    [geweigerd] = [b for b in berichten if b.startswith("RAPPORT GEWEIGERD")]
    assert mislukt == "CONTROLE MISLUKT, herkansing: controles=['ongedekte_getallen']"
    assert geweigerd == "RAPPORT GEWEIGERD: controles=['ongedekte_getallen']"
    assert not any("None" in regel or "336" in regel for regel in (mislukt, geweigerd))
