"""Een afgebroken beurt laat geen open verzoek achter in het gesprek (#548, UX F01-nasleep).

Na een afgebroken UWV-analyse ging het antwoord op een vraag over mbo door op de UWV-vacatures
(twaalf keer "UWV vacatures opgehaald"). De history droeg de UWV-vraag zonder antwoord, gevolgd
door de nieuwe vraag: voor het model een verzoek dat nog openstond. Elke afgebroken beurt krijgt
nu een vaste markering als antwoord: op de server bij stop, tijdsgrens en fout, en via de browser
voor een antwoord dat met de verbinding wegviel.
"""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import patch

from agent.history import AFGEBROKEN, afgebroken_beurt
from routes import chat

run_module = importlib.import_module("agent.run")

_UWV = "Welke vacatures zijn er in Utrecht voor onze opleidingen?"
_MBO = "Hoeveel mbo-studenten had Nederland in 2024/25?"


def test_markering_met_en_zonder_tekst():
    assert afgebroken_beurt() == {"role": "assistant", "content": AFGEBROKEN}
    assert afgebroken_beurt("  ") == {"role": "assistant", "content": AFGEBROKEN}
    assert afgebroken_beurt("Ik haal de UWV-vacatures op. ") == {
        "role": "assistant",
        "content": f"Ik haal de UWV-vacatures op.\n\n{AFGEBROKEN}",
    }


async def _emit(_event):
    pass


def _na_beurt(monkeypatch, nep_run) -> dict:
    monkeypatch.setattr(chat, "agent_run", nep_run)
    session = chat._new_session()
    asyncio.run(chat._process_message(_UWV, session, _emit, None))
    return session


def test_stopknop_of_tijdsgrens_sluit_de_beurt_met_de_markering(monkeypatch):
    async def gestopt(messages, session, emit, stop_event, model=None):
        stop_event.set()
        return "Ik haal de UWV-vacatures op."

    session = _na_beurt(monkeypatch, gestopt)

    assert session["messages"] == [
        {"role": "user", "content": _UWV},
        {"role": "assistant", "content": f"Ik haal de UWV-vacatures op.\n\n{AFGEBROKEN}"},
    ]
    assert session["turns"] == []  # geen beurt voor rapport of dashboard


def test_een_fout_sluit_de_beurt_met_de_markering(monkeypatch):
    async def mislukt(messages, session, emit, stop_event, model=None):
        raise RuntimeError("rate limit")

    session = _na_beurt(monkeypatch, mislukt)

    assert session["messages"] == [{"role": "user", "content": _UWV}, afgebroken_beurt()]


def test_een_gewoon_antwoord_blijft_zonder_markering(monkeypatch):
    async def gewoon(messages, session, emit, stop_event, model=None):
        return "Er zijn 1.200 vacatures."

    session = _na_beurt(monkeypatch, gewoon)

    assert session["messages"][-1] == {"role": "assistant", "content": "Er zijn 1.200 vacatures."}
    assert len(session["turns"]) == 1


# ─── Via de browser: een antwoord dat met de verbinding wegviel ──────────────


def test_historie_uit_de_browser_zet_de_markering_terug():
    beurten = [
        {"role": "user", "content": _UWV},
        {"role": "assistant", "content": "Ik haal de UWV-vacatures op.", "afgebroken": True},
        {"role": "user", "content": _MBO},
    ]

    assert chat._parse_history(beurten) == [
        {"role": "user", "content": _UWV},
        {"role": "assistant", "content": f"Ik haal de UWV-vacatures op.\n\n{AFGEBROKEN}"},
        {"role": "user", "content": _MBO},
    ]


def test_afgebroken_zonder_tekst_blijft_een_beurt():
    """Zonder markering viel een leeg antwoord weg en stond de vraag ervóór weer open."""
    beurten = [{"role": "user", "content": _UWV}, {"role": "assistant", "content": "", "afgebroken": True}]

    assert chat._parse_history(beurten) == [{"role": "user", "content": _UWV}, afgebroken_beurt()]


def test_markering_alleen_voor_een_echt_afgebroken_antwoord():
    beurten = [
        {"role": "user", "content": _UWV, "afgebroken": True},
        {"role": "assistant", "content": "Klaar.", "afgebroken": "ja"},
        {"role": "assistant", "content": "", "afgebroken": False},
    ]

    assert chat._parse_history(beurten) == [
        {"role": "user", "content": _UWV},
        {"role": "assistant", "content": "Klaar."},
    ]


# ─── Wat het model ziet bij de volgende, andere vraag ────────────────────────


def test_de_volgende_vraag_komt_na_een_gesloten_beurt_bij_het_model():
    meegegeven: list[dict] = []

    async def nep_loop(history, **kwargs):
        meegegeven.extend(history)
        return SimpleNamespace(aborted="tools")

    messages = [
        {"role": "user", "content": _UWV},
        afgebroken_beurt("Ik haal de UWV-vacatures op."),
        {"role": "user", "content": _MBO},
    ]
    with patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(messages, session={}, emit=_emit))

    assert [m["role"] for m in meegegeven] == ["user", "assistant", "user"]
    assert meegegeven[1]["content"].endswith(AFGEBROKEN)
    assert meegegeven[2]["content"] == _MBO
