"""De verduidelijkingsvraag spreekt de gebruiker aan met je, zoals de rest van de app (#341, UX-10.2)."""

import asyncio
import json

import pytest

from agent.aanspreekvorm import je_vorm


@pytest.mark.parametrize(
    ("u", "je"),
    [
        ("Welk schooljaar bedoelt u?", "Welk schooljaar bedoel je?"),
        ("Wilt u de cijfers per opleidingsvorm zien?", "Wil je de cijfers per opleidingsvorm zien?"),
        ("Heeft u een voorkeur?", "Heb je een voorkeur?"),
        ("Bent u op zoek naar mbo of hbo?", "Ben je op zoek naar mbo of hbo?"),
        ("Moet u de hele reeks hebben?", "Moet je de hele reeks hebben?"),
        ("U kunt ook alle jaren kiezen.", "Je kunt ook alle jaren kiezen."),
        ("Als u heeft gekozen, haal ik de data op.", "Als je hebt gekozen, haal ik de data op."),
        ("Gaat het om uw eigen instelling?", "Gaat het om je eigen instelling?"),
    ],
)
def test_u_vorm_wordt_je_vorm(u, je):
    assert je_vorm(u) == je


def test_tekst_in_de_je_vorm_blijft_gelijk():
    tekst = "Welk schooljaar bedoel je? Kies uit de lijst."
    assert je_vorm(tekst) == tekst


def test_onzekere_u_vorm_blijft_ongemoeid():
    """Liever 'u' dan kapot Nederlands: een werkwoord buiten de lijst wordt niet geraden."""
    tekst = "Verlangt u een uitsplitsing?"
    assert je_vorm(tekst) == tekst


def test_woorden_met_u_erin_blijven_staan():
    tekst = "Uitstroom of uitval per uur?"
    assert je_vorm(tekst) == tekst


def test_de_clarificatiekaart_toont_de_je_vorm():
    from agent.loop import ToolCall
    from agent.run import _handle_clarify_scope

    args = {
        "vraag": "Welk schooljaar bedoelt u?",
        "opties": [{"label": "Laatste jaar", "beschrijving": "Als u alleen het recentste jaar wilt"}, "Alle jaren"],
    }
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    call = ToolCall("c1", "clarify_scope", json.dumps(args), args)
    asyncio.run(_handle_clarify_scope(call, "", [], [], {}, emit))

    [kaart] = [e for e in events if e["type"] == "clarification"]
    assert kaart["vraag"] == "Welk schooljaar bedoel je?"
    assert kaart["opties"] == [
        {"label": "Laatste jaar", "beschrijving": "Als je alleen het recentste jaar wilt"},
        "Alle jaren",
    ]
