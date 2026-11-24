"""Een landelijke ROA-terugval staat als vaste regel onder het antwoord, uit code (#1100).

Voor Midden-Utrecht en "Mbo4 - zorg en dienstverlening" heeft ROA wel een prognose, maar de schoolverlatersinformatie
alleen landelijk. get_roa_benchmark zegt dat in `terugval`; of het in het antwoord kwam, hing van het model af. Nu zet
de app die zin zelf onder het antwoord, één keer, en noemt de bronregel per onderdeel de regio van zijn cijfers.
"""

import asyncio
import importlib
import json
from unittest.mock import patch

import pandas as pd
import pytest

from agent.bronvermelding import bronlinks_van, bronnen_van
from agent.loop import LoopResult
from agent.stream import StreamResult
from agent.terugval import KOP, met_terugval
from data import arbeidsmarkt
from tools import store
from tools.arbeidsmarkt import ROA_ID, get_roa_benchmark

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_SECTOR = "Mbo4 - zorg en dienstverlening"
_ITA = "ITA toekomstige arbeidsmarktsituatie in 2030"


def _roa_rij(regio, niveau, onderwerp, perc=None, typering=None, thema=arbeidsmarkt._ROA_SIS):
    return {
        "regionaam": regio,
        "thema": thema,
        "aggregatieniveau": arbeidsmarkt._ROA_SECTOR if " - " in niveau else arbeidsmarkt._ROA_NIVEAU,
        "detailniveau": niveau,
        "onderwerp": onderwerp,
        "perc": perc,
        "aantal": None,
        "typering": typering,
        "versie": "v20251218",
    }


# Regionaal heeft ROA alleen de prognose: de schoolverlatersinformatie is er alleen landelijk.
_ROA = pd.DataFrame(
    [
        _roa_rij("Nederland", _SECTOR, "werkloosheid", perc="3"),
        _roa_rij("Nederland", _SECTOR, _ITA, typering="redelijk", thema=arbeidsmarkt._ROA_PROGNOSE),
        _roa_rij("Midden-Utrecht", _SECTOR, _ITA, typering="goed", thema=arbeidsmarkt._ROA_PROGNOSE),
    ]
)
_TITELS = {ROA_ID: "AIS tot 2030"}
_ANTWOORD = "De arbeidsmarkt voor zorg en dienstverlening in Midden-Utrecht is goed tot 2030."


@pytest.fixture(autouse=True)
def bronnen():
    store.clear()
    with (
        patch.object(arbeidsmarkt, "_roa", return_value=_ROA),
        patch.object(arbeidsmarkt, "roa_sectoren", return_value=[_SECTOR]),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
        patch("agent.selectie.bron_titel", side_effect=lambda d, **_: _TITELS.get(d, d)),
    ):
        yield
    store.clear()


def _roa(regio: str | None = "Midden-Utrecht") -> str:
    return get_roa_benchmark(_SECTOR, regio=regio)


def _opgemaakt(antwoord: str, result: str) -> str:
    loop = LoopResult(text=antwoord, steps=[("get_roa_benchmark", result)])
    return run_module._antwoordtekst(loop, loop.text, [], [])


def test_de_tool_valt_terug_voor_de_schoolverlaters():
    uit = json.loads(_roa())
    assert uit["herkomst"] == {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "Midden-Utrecht"}
    assert "schoolverlaters_sis_2024" in uit["terugval"]


def test_de_terugvalzin_staat_onder_het_opgemaakte_antwoord():
    result = _roa()
    terugval = json.loads(result)["terugval"]

    tekst = _opgemaakt(_ANTWOORD, result)

    assert tekst.count(terugval) == 1
    assert tekst.startswith(_ANTWOORD)
    assert tekst.endswith(f"\n\n{KOP} {terugval}")


@pytest.mark.parametrize(
    "plek",
    [
        "{antwoord} {zin}",
        "{zin} {antwoord}",
        "{antwoord}\n\n{zin}",
        "{antwoord}\n\n- {zin}",
        "{antwoord}\n\n**Regio:** {zin}\n\nWil je ook de vacatures zien?",
    ],
)
def test_schreef_het_model_de_zin_al_dan_staat_hij_er_een_keer(plek):
    result = _roa()
    terugval = json.loads(result)["terugval"]

    tekst = _opgemaakt(plek.format(antwoord=_ANTWOORD, zin=terugval), result)

    assert tekst.count(terugval) == 1
    assert tekst.endswith(f"{KOP} {terugval}")
    assert _ANTWOORD in tekst
    assert "\n\n\n" not in tekst and "- \n" not in tekst
    if "vacatures" in plek:
        assert "Wil je ook de vacatures zien?" in tekst


def test_twee_keer_dezelfde_terugval_geeft_een_regel():
    result = _roa()
    tekst = met_terugval(_ANTWOORD, [result, result])
    assert tekst.count(json.loads(result)["terugval"]) == 1


def test_zonder_terugval_verandert_er_niets():
    result = _roa(regio=None)
    assert "terugval" not in json.loads(result)

    assert _opgemaakt(_ANTWOORD, result) == _ANTWOORD
    assert bronnen_van([("get_roa_benchmark", result)]) == ["ROA · AIS tot 2030, versie v20251218 (ais2030)"]


def test_een_antwoord_zonder_tekst_krijgt_geen_regel():
    assert met_terugval("", [_roa()]) == ""


def test_de_bronregel_noemt_per_onderdeel_de_regio():
    steps = [("get_roa_benchmark", _roa())]

    assert bronnen_van(steps) == [
        "ROA · AIS tot 2030, versie v20251218 (ais2030), schoolverlaters (SIS 2024): landelijk, "
        "prognose tot 2030: Midden-Utrecht"
    ]
    assert list(bronlinks_van(steps)) == bronnen_van(steps)


async def _niets(event: dict) -> None:
    return None


def test_een_beurt_met_get_roa_benchmark_toont_de_regel_in_het_antwoord(monkeypatch):
    """De hele beurt door `run`: het model roept de tool aan en schrijft een antwoord zonder de zin."""
    result = _roa()
    terugval = json.loads(result)["terugval"]
    aanroep = {
        "id": "r",
        "name": "get_roa_benchmark",
        "arguments": json.dumps({"sector": _SECTOR, "regio": "Midden-Utrecht"}),
    }
    stappen = [StreamResult(text="", tool_calls=[aanroep]), StreamResult(text=_ANTWOORD, tool_calls=[])]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return result, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings, eerder=(): None)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    vraag = f"Hoe is de arbeidsmarkt voor {_SECTOR} in Midden-Utrecht?"
    asyncio.run(run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o"))

    einde = next(e for e in reversed(events) if e["type"] == "message_end")
    assert einde["content"].count(terugval) == 1
    assert f"{KOP} {terugval}" in einde["content"]
    assert any("prognose tot 2030: Midden-Utrecht" in b for b in einde["bronnen"])
