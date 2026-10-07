"""Het definitieblok van een rapport komt uitsluitend uit de bron (#329, #402, #422)."""

import json

import pandas as pd
import pytest

from agent.report import _parse_spec_from_response
from agent.report_definities import definities_uit_bron
from tools import store
from tools.store import KeyMeta

_TELLING = "Ingeschrevenen: personen, één keer geteld in het hele domein hoger onderwijs."
_KEY = "duo:p01hoinges:3:sel"
_VORMEN = {"begrip": "Opleidingsvorm", "definitie": "VT = voltijd, DT = deeltijd, DU = duaal"}


@pytest.fixture(autouse=True)
def _selectie():
    store.clear()
    store.put(
        _KEY,
        pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [27135]}),
        KeyMeta(bron="duo", dataset="p01hoinges", teldefinitie=_TELLING),
    )
    yield
    store.clear()


def _datasets() -> list[dict]:
    return [{"data_key": _KEY}]


def _spec(**velden):
    antwoord = json.dumps({"title": "Ingeschrevenen Universiteit Twente", "conclusie": "c", **velden})
    return _parse_spec_from_response(antwoord, [], {"datasets": _datasets(), "topic": "Twente"})


def test_teldefinitie_en_opleidingsvormen_komen_letterlijk_uit_de_bron():
    definities = definities_uit_bron(_datasets(), "Voltijd en deeltijd per jaar")

    assert definities == [{"begrip": "Telling (p01hoinges)", "definitie": _TELLING}, _VORMEN]


@pytest.mark.parametrize("tekst", ["per OPLEIDINGSVORM", "het aandeel DU", "Deeltijdstudenten", "duaal"])
def test_opleidingsvorm_als_het_rapport_erover_gaat(tekst):
    assert _VORMEN in definities_uit_bron(_datasets(), tekst)


@pytest.mark.parametrize("tekst", ["Ingeschrevenen per jaar", '{"dtick": 1, "dus": 2}'])
def test_geen_opleidingsvorm_als_het_rapport_er_niet_over_gaat(tekst):
    assert _VORMEN not in definities_uit_bron(_datasets(), tekst)


def test_twente_rapport_zonder_opleidingsvorm_toont_alleen_de_telling():
    """CH-15: naast de brondefinitie een modelbegrip 'Ingeschrevene' en een irrelevante opleidingsvorm."""
    spec = _spec(
        definities=[{"begrip": "Ingeschrevene", "definitie": "Student met een inschrijving"}],
        conclusie="Het aantal ingeschrevenen bij de Universiteit Twente daalde.",
    )

    assert spec.definities == [{"begrip": "Telling (p01hoinges)", "definitie": _TELLING}]


def test_het_model_schrijft_geen_definities_meer():
    kwaad = {"begrip": "Voltijd", "definitie": "per opleidingsvorm geteld"}
    eerstejaars = {"begrip": "Eerstejaars", "definitie": "Student die voor het eerst staat ingeschreven"}

    assert _spec(definities=[kwaad, eerstejaars]).definities == _spec().definities


def test_opleidingsvorm_in_een_grafiek_telt_mee():
    figuur = json.dumps({"data": [{"x": ["VT", "DT"], "y": [1, 2]}], "layout": {}})
    antwoord = json.dumps({"title": "Ingeschrevenen", "conclusie": "c"})
    spec = _parse_spec_from_response(antwoord, [figuur], {"datasets": _datasets(), "topic": "Twente"})

    assert _VORMEN in spec.definities


def test_zonder_metadata_geen_definities():
    store.clear()
    assert definities_uit_bron(_datasets(), "voltijd") == []
