"""Het codeverzoek toont de code van de juiste stap, of zegt waarom er geen is (#969).

Gevonden bij de weekreview van 06-11 op 73b37981 (#959):

- de sessie onthield alleen een snippet: na een stap zonder snippet (collegegeld) gaf "geef de code" de snippet van
  een eerdere stap, alsof die bij het antwoord hoorde; in een heropend gesprek kwam er niets, terwijl de prompt code
  beloofde;
- de herkenning was te ruim: "CROHO code", "brin code", "code van de Universiteit Utrecht", "ISCED code" en
  "Python-cursussen" telden als codeverzoek;
- getallen in het toegevoegde codeblok kregen een citatie, omdat het blok vóór de citaties aan de tekst kwam.
"""

import asyncio
import importlib
import json

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from agent.codeverzoek import CODEKOP, GEEN_DATASTAP, is_codeverzoek
from agent.stream import StreamResult
from data import instellingen
from tools import studiekeuze
from tools.schemas import TOOL_GET_COLLEGEGELD, TOOL_GET_STUDIEKEUZE, TOOL_SEARCH_CATALOG

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


def _profiel(naam: str) -> dict | None:
    if " ".join(naam.split()).lower() in ("hogeschool utrecht", "hu"):
        return {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"}
    return None


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


# --- de herkenning ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is de CROHO code van Psychologie aan de UvA?",
        "Wat is de brin code van de Hogeschool Utrecht?",
        "Wat is de code van de Universiteit Utrecht",
        "Welke opleidingen vallen onder ISCED code 0613?",
        "Hoeveel studenten volgen Python-cursussen?",
        "Welke code hoort bij Psychologie?",
        "Wat is de code voor hbo-ICT?",
    ],
)
def test_een_vraag_naar_een_sleutel_of_onderwerp_is_geen_codeverzoek(vraag):
    assert not is_codeverzoek(vraag)


@pytest.mark.parametrize(
    "vraag",
    [
        "Geef de code",
        "Laat de code van deze stap zien",
        "Mag ik de Python-code?",
        "Kun je er een notebook van maken?",
        "Show me the code for this",
    ],
)
def test_een_verzoek_om_programmacode_blijft_een_codeverzoek(vraag):
    assert is_codeverzoek(vraag)


# --- de code van de juiste stap -----------------------------------------------------------------------------------

_HU_ICT = json.dumps({"weergave": "opleidingen", "instelling": "Hogeschool Utrecht", "opleiding": "30020"})
_COLLEGEGELD = "Het wettelijk collegegeld 2026-2027 is € 2.694 (DUO)."
_ZOEKEN = json.dumps({"status": "candidates", "kandidaten": [{"id": "duo:p01hoinges"}]})


def _dispatch(name, args):
    if name == TOOL_GET_STUDIEKEUZE:
        return studiekeuze.get_studiekeuze(**args), None
    if name == TOOL_GET_COLLEGEGELD:
        return _COLLEGEGELD, None
    if name == TOOL_SEARCH_CATALOG:
        return _ZOEKEN, None
    raise AssertionError(name)


def _stap(naam: str, arguments: str = "{}", tekst: str = "") -> list[StreamResult]:
    return [StreamResult(text="", tool_calls=[{"id": naam, "name": naam, "arguments": arguments}]), _tekst(tekst)]


def _tekst(tekst: str) -> StreamResult:
    return StreamResult(text=tekst or "Klaar.", tool_calls=[])


class _Gesprek:
    """Beurten met een nagebootst model op één sessie; de tools draaien via `_dispatch`, de snippet is echt."""

    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch
        self.session: dict = {}
        self.messages: list[dict] = []

    def beurt(self, vraag: str, stappen: list[StreamResult]) -> tuple[list[dict], dict]:
        async def fake_completion(*args, **kwargs):
            return object()

        async def fake_accumulate(stream, stop_event=None, emit=None):
            return stappen.pop(0)

        self.monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
        self.monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
        self.monkeypatch.setattr(loop_module, "dispatch", _dispatch)
        events: list[dict] = []

        async def emit(event):
            events.append(event)

        self.messages.append({"role": "user", "content": vraag})
        antwoord = asyncio.run(
            run_module.run(self.messages, self.session, emit, asyncio.Event(), model="openai/gpt-4o")
        )
        self.messages.append({"role": "assistant", "content": antwoord})
        return events, next(e for e in reversed(events) if e["type"] == "message_end")


def _snippet(events: list[dict]) -> str:
    return next(e["snippet"] for e in events if e["type"] == "tool_end" and e.get("snippet"))


def test_na_een_stap_zonder_snippet_geen_code_van_een_eerdere_stap(monkeypatch):
    """Collegegeld heeft geen snippet: het codeverzoek krijgt de vaste zin, niet de studiekeuzesnippet."""
    gesprek = _Gesprek(monkeypatch)
    events, _ = gesprek.beurt("Hoe tevreden zijn studenten ICT bij de HU?", _stap(TOOL_GET_STUDIEKEUZE, _HU_ICT))
    snippet = _snippet(events)
    gesprek.beurt("Wat is het collegegeld?", _stap(TOOL_GET_COLLEGEGELD, tekst="Dat is het wettelijk collegegeld."))
    _, slot = gesprek.beurt("Geef de code om dit zelf na te rekenen.", [_tekst("Zie hieronder.")])
    inhoud = slot["content"]
    assert snippet not in inhoud and "```python" not in inhoud
    assert CODEKOP in inhoud
    assert '"Collegegeld opgezocht", heeft geen code' in inhoud


def test_een_zoekstap_verandert_de_laatste_datastap_niet(monkeypatch):
    """De catalogus doorzoeken laadt geen data: de code blijft die van de studiekeuzestap."""
    gesprek = _Gesprek(monkeypatch)
    events, _ = gesprek.beurt("Hoe tevreden zijn studenten ICT bij de HU?", _stap(TOOL_GET_STUDIEKEUZE, _HU_ICT))
    snippet = _snippet(events)
    _, slot = gesprek.beurt("Geef de code", _stap(TOOL_SEARCH_CATALOG, json.dumps({"query": "ict"})))
    assert f"```python\n{snippet}\n```" in slot["content"]
    assert '"Studiekeuzedatabase geraadpleegd"' in slot["content"]


def test_een_heropend_gesprek_zonder_datastap_belooft_geen_code(monkeypatch):
    """Na heropenen is de sessie leeg: een vaste zin, geen leeg beloofd codeblok."""
    gesprek = _Gesprek(monkeypatch)
    _, slot = gesprek.beurt("Geef de code om dit zelf na te rekenen.", [_tekst("Zie hieronder.")])
    assert slot["content"].endswith(f"{CODEKOP}\n{GEEN_DATASTAP}")


def test_een_getal_in_het_codeblok_krijgt_geen_citatie(monkeypatch):
    """De citaties gaan over de antwoordtekst; de code eronder is geen bewering (30020 is de CROHO-code in de snippet)."""
    gesprek = _Gesprek(monkeypatch)
    events, slot = gesprek.beurt(
        "Geef de code om dit zelf na te rekenen.", _stap(TOOL_GET_STUDIEKEUZE, _HU_ICT, "De code staat hieronder.")
    )
    assert "30020" in _snippet(events) and "30020" in slot["content"]
    assert not any(c["getal"] in _snippet(events) for c in slot.get("citaties", []))
