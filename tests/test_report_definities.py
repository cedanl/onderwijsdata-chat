"""Het definitieblok van een rapport komt uit de bron, niet uit het model (#329)."""

import pandas as pd
import pytest

from agent.report import _parse_spec_from_response
from agent.report_definities import definities_uit_bron, samengevoegd
from tools import store
from tools.store import KeyMeta

_TELLING = "Ingeschrevenen: personen, één keer geteld in het hele domein hoger onderwijs."
_KEY = "duo:p01hoinges:3:sel"


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


def test_teldefinitie_en_opleidingsvormen_komen_letterlijk_uit_de_bron():
    definities = definities_uit_bron(_datasets())

    assert {"begrip": "Telling (p01hoinges)", "definitie": _TELLING} in definities
    assert {"begrip": "Opleidingsvorm", "definitie": "VT = voltijd, DT = deeltijd, DU = duaal"} in definities


def test_hetzelfde_blok_voor_dezelfde_selectie_ongeacht_wat_het_model_schrijft():
    kwaad = {"begrip": "Telling", "definitie": "Eén persoon telt één keer per opleidingsvorm."}
    uit_bron = definities_uit_bron(_datasets())

    assert samengevoegd(uit_bron, [kwaad]) == samengevoegd(uit_bron, []) == uit_bron


def test_getalvrij_begrip_van_het_model_blijft():
    eerstejaars = {"begrip": "Eerstejaars", "definitie": "Student die voor het eerst staat ingeschreven"}

    assert samengevoegd(definities_uit_bron(_datasets()), [eerstejaars])[-1] == eerstejaars


@pytest.mark.parametrize(
    "afbakening",
    [
        {"begrip": "Ingeschrevenen", "definitie": "WO-masters zijn buiten beschouwing gelaten."},
        {"begrip": "Studenten", "definitie": "Exclusief hbo-masters."},
        {"begrip": "Studenten", "definitie": "Inclusief de associate degree."},
        {"begrip": "Bachelors", "definitie": "Promovendi zijn niet meegenomen."},
        {"begrip": "Bachelors", "definitie": "Hbo-masters zijn uitgesloten."},
    ],
)
def test_wat_de_telling_afbakent_zegt_de_bron_en_niet_het_model(afbakening):
    """TU Delft (#402): model 'WO-masters buiten beschouwing', bron 'hbo-master uitgesloten'."""
    uit_bron = definities_uit_bron(_datasets())

    assert samengevoegd(uit_bron, [afbakening]) == uit_bron


def test_zonder_teldefinitie_mag_het_model_afbakenen():
    afbakening = {"begrip": "Studenten", "definitie": "Exclusief hbo-masters."}

    assert samengevoegd([], [afbakening]) == [afbakening]


def test_rapportspec_neemt_de_bronblok_over_en_niet_de_modelomschrijving():
    antwoord = (
        '{"title": "t", "definities": [{"begrip": "Voltijd", "definitie": "per opleidingsvorm geteld"}], '
        '"conclusie": "c"}'
    )
    spec = _parse_spec_from_response(antwoord, [], {"datasets": _datasets(), "topic": "Fontys"})

    assert spec.definities[0]["definitie"] == _TELLING
    assert all("per opleidingsvorm" not in d["definitie"] for d in spec.definities)


def test_zonder_metadata_blijft_alleen_het_modelblok():
    store.clear()
    assert definities_uit_bron(_datasets()) == []
