"""Een onderzoeksvraag die de gebruiker vóór het genereren bevestigde, is titel en onderzoeksvraag van het rapport (#750).

Besluit #732: de hoofdvraag is de vraag zoals die in het gesprek groeide. De app stelt haar voor, de gebruiker past
haar zo nodig aan, en het rapport neemt haar over in plaats van de eerste vraag of een formulering van het model.
"""

import asyncio
import json

import pandas as pd
import pytest

from agent import report
from agent.loop import LoopResult
from agent.report_titel import TITEL_ZONDER_PERSOONSGEGEVENS, VRAAG_ZONDER_PERSOONSGEGEVENS, rapporttitel
from tools import store
from tools.store import KeyMeta

_KEY = "duo:p02ho1ejrs:5"
_EERSTE = "Hoe is de trend van instroom in B Computing Science, B Informatica en B Computer Science?"
_BEVESTIGD = (
    "Hoe ontwikkelt de instroom in de wo-bachelors B Computing Science, B Informatica en B Computer Science zich?"
)
_ANTWOORD = {
    "onderzoeksvraag": "Een formulering van het model",
    "beantwoordt": ["De instroom per jaar"],
    "beantwoordt_niet": ["De oorzaken"],
    "visualisaties": [],
    "conclusie": "De instroom daalt.",
}


@pytest.fixture
def sessie():
    store.put(
        _KEY,
        pd.DataFrame({"STUDIEJAAR": [2021, 2025], "AANTAL_EERSTEJAARS_INGESCHREVENEN": [457, 345]}),
        KeyMeta("duo", "p02ho1ejrs", resource=5),
    )
    return {
        "data_keys": [_KEY],
        "messages": [
            {"role": "user", "content": _EERSTE},
            {"role": "assistant", "content": "De instroom daalt."},
            {"role": "user", "content": "Ik wil het alleen zien voor universitaire bachelor's."},
        ],
    }


def _rapport(sessie, monkeypatch, onderzoeksvraag=None, antwoord=_ANTWOORD):
    gezien: dict = {}

    async def loop(messages, *, check, **_):
        gezien["prompt"] = messages[0]["content"]
        tekst = json.dumps(antwoord)
        gezien["problemen"] = check(tekst, [])
        return LoopResult(text=tekst)

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    spec = asyncio.run(report.generate(sessie, stil, onderzoeksvraag=onderzoeksvraag))
    return spec, gezien


def test_een_bevestigde_onderzoeksvraag_is_titel_en_onderzoeksvraag(sessie, monkeypatch):
    spec, gezien = _rapport(sessie, monkeypatch, _BEVESTIGD)

    assert spec.title == rapporttitel(_BEVESTIGD, None)
    assert spec.onderzoeksvraag == _BEVESTIGD
    assert f"Onderzoeksvraag, bevestigd door de gebruiker: {_BEVESTIGD}" in gezien["prompt"]


def test_zonder_bevestigde_vraag_blijft_de_eerste_vraag_het_onderwerp(sessie, monkeypatch):
    spec, gezien = _rapport(sessie, monkeypatch)

    assert spec.title == rapporttitel(_EERSTE, None)
    assert spec.onderzoeksvraag == "Een formulering van het model"
    assert f"Onderwerp (onderzoeksvraag): {_EERSTE}" in gezien["prompt"]


def test_een_bevestigde_vraag_met_persoonsgegevens_komt_niet_in_het_rapport(sessie, monkeypatch):
    spec, _ = _rapport(sessie, monkeypatch, "Instroom van de studenten van jan.jansen@example.nl")

    assert spec.title == TITEL_ZONDER_PERSOONSGEGEVENS
    assert spec.onderzoeksvraag == VRAAG_ZONDER_PERSOONSGEGEVENS


def test_een_getal_in_de_onderzoeksvraag_dekt_geen_getal_in_het_rapport(sessie, monkeypatch):
    """#211: wat de gebruiker zei is een bewering om te toetsen; ook als zij het als onderzoeksvraag bevestigde."""
    antwoord = {**_ANTWOORD, "conclusie": "De instroom was 12.345 eerstejaars."}

    _, gezien = _rapport(sessie, monkeypatch, "Klopt het dat de instroom 12345 eerstejaars was?", antwoord)

    assert any("12.345" in p for p in map(str, gezien["problemen"]))
