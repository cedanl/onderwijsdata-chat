"""Een zelfcorrectie hoort in de redeneerkaart, niet in het eindantwoord (#412).

CH-05: het juiste antwoord over ROC Mondriaan bevatte "Mijn tussenzin 'zes vestigingen'
was onjuist." De gebruiker leest het eindantwoord; wat het model onderweg herzag, staat
bij de tussenstappen.
"""

import asyncio
import importlib
import json

import pytest

from agent.stream import StreamResult
from agent.zelfcorrectie import zonder_zelfcorrectie

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")


@pytest.mark.parametrize(
    "zin",
    [
        "Mijn tussenzin 'zes vestigingen' was onjuist.",
        "Mijn eerdere opmerking over 22 vestigingen is niet juist.",
        "Correctie: het zijn er 30.",
        "Ik heb me vergist in het aantal.",
        "Bij nader inzien gaat het om drie instellingen.",
        "Eerder noemde ik zes vestigingen.",
        "Mijn excuses voor de verwarring.",
    ],
)
def test_zelfcorrigerende_zin_gaat_uit_de_eindtekst(zin):
    tekst = f"ROC Mondriaan heeft 30 vestigingen. {zin} Bron: RIO, Erkenningen."

    schoon, weg = zonder_zelfcorrectie(tekst)

    assert schoon == "ROC Mondriaan heeft 30 vestigingen. Bron: RIO, Erkenningen."
    assert weg == [zin]


@pytest.mark.parametrize(
    "tekst",
    [
        "Het aantal van 475.460 studenten is juist.",
        "De aanname dat alle vestigingen in Den Haag liggen, was onjuist: 3 liggen in Delft.",
        "Er zijn correcties op de voorlopige cijfers van het CBS.",
        "Ik noem de 30 vestigingen hieronder.",
    ],
)
def test_gewone_zinnen_blijven_staan(tekst):
    assert zonder_zelfcorrectie(tekst) == (tekst, [])


def test_opmaak_blijft_heel_en_een_lege_regel_verdwijnt():
    tekst = (
        "**ROC Mondriaan**\n\n"
        "- 3 instellingen\n"
        "- 30 vestigingen\n\n"
        "Mijn tussenzin 'zes vestigingen' was onjuist.\n\n"
        "Bron: RIO."
    )

    schoon, weg = zonder_zelfcorrectie(tekst)

    assert schoon == "**ROC Mondriaan**\n\n- 3 instellingen\n- 30 vestigingen\n\nBron: RIO."
    assert weg == ["Mijn tussenzin 'zes vestigingen' was onjuist."]


def test_chat_zet_de_zelfcorrectie_in_de_redeneerkaart_en_niet_in_het_antwoord(monkeypatch):
    aanroep = {"id": "r", "name": "get_rio_instelling", "arguments": '{"naam": "ROC Mondriaan"}'}
    overzicht = json.dumps({"aantallen": {"erkenningen": 34, "instellingen": 3, "vestigingen": 30}})
    stappen = [
        StreamResult(text="ROC Mondriaan heeft zes vestigingen.", tool_calls=[aanroep]),
        StreamResult(text="ROC Mondriaan heeft 30 vestigingen. Mijn tussenzin was onjuist.", tool_calls=[]),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)

    async def fake_execute_tool(call, emit):
        return overzicht, None

    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    tekst = asyncio.run(
        run_module.run(
            [{"role": "user", "content": "Hoeveel vestigingen heeft ROC Mondriaan?"}],
            {},
            emit,
            asyncio.Event(),
            model="openai/gpt-4o",
        )
    )

    assert tekst == "ROC Mondriaan heeft 30 vestigingen."
    eind = events[-1]
    assert eind["type"] == "message_end" and eind["content"] == tekst
    assert eind["tussentekst"] == ["Mijn tussenzin was onjuist."]
