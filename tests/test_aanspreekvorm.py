"""De app spreekt de gebruiker aan met je: in de verduidelijkingsvraag (#341, UX-10.2), het eindantwoord, het
rapport en de meldingen (#536, besluit #326)."""

import asyncio
import json

import pytest

from agent.aanspreekcontrole import overgebleven_u_vorm
from agent.aanspreekvorm import in_je_vorm, je_vorm, overgebleven_u_vormen
from agent.probleem import meldingen


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


@pytest.mark.parametrize(
    ("u", "je"),
    [
        # Testronde 13 okt, rapport 01, F-11: "u" naast "je" in één gesprek.
        ("Het getal dat u noemt, staat in de data.", "Het getal dat je noemt, staat in de data."),
        # Na een lijstteken, kop of citaatteken begint de zin ook.
        ("- U kunt ook alle jaren kiezen.", "- Je kunt ook alle jaren kiezen."),
        ("1) U kunt ook alle jaren kiezen.", "1) Je kunt ook alle jaren kiezen."),
        ("> **U kunt** ook alle jaren kiezen.", "> **Je kunt** ook alle jaren kiezen."),
        ("**Let op:** u kunt ook alle jaren kiezen.", "**Let op:** je kunt ook alle jaren kiezen."),
        ("Jullie instelling had 3.303 studenten.", "Je instelling had 3.303 studenten."),
        ("Bij jullie opleidingen en jullie eigen school.", "Bij je opleidingen en je eigen school."),
        ("Er waren 3.303 studenten.\nWilt u de trend zien?", "Er waren 3.303 studenten.\nWil je de trend zien?"),
    ],
)
def test_lopende_tekst_in_de_je_vorm(u, je):
    assert in_je_vorm(u) == je


def test_een_onzekere_zin_blokkeert_de_andere_zinnen_niet():
    """Liever 'u' dan kapot Nederlands, maar per zin: de rest van de tekst gaat wel om."""
    tekst = "U kunt ook alle jaren kiezen. Verlangt u een uitsplitsing? Het getal dat u noemt, staat in de data."
    assert in_je_vorm(tekst) == (
        "Je kunt ook alle jaren kiezen. Verlangt u een uitsplitsing? Het getal dat je noemt, staat in de data."
    )


def test_een_onzekere_zin_houdt_ook_zijn_jullie():
    tekst = "Verlangt u een uitsplitsing voor jullie instelling?"
    assert in_je_vorm(tekst) == tekst


@pytest.mark.parametrize(
    "tekst",
    [
        "Gebruik `als u kiest` niet.",
        "```\nU kunt hier niets.\n```",
        "Zie [wat u kunt doen](https://www.duo.nl/u/zakelijk).",
        "Kijk op https://example.nl/u/kunt voor meer.",
        '<span title="U kunt kiezen">x</span>',
        "[1]: /pad?u=1",
        # Geen u-vorm: woorden met een u erin, Engels, een afkorting.
        "Uitstroom of uitval per uur.",
        "In the U.S. you can choose.",
        "Je kunt ook alle jaren kiezen.",
    ],
)
def test_code_links_html_en_tekst_zonder_u_vorm_blijven_gelijk(tekst):
    assert in_je_vorm(tekst) == tekst


def test_beschermde_stukken_staan_na_de_omzetting_op_hun_plek():
    tekst = "Als u `query_data` gebruikt, ziet u niets. Klik op [de bron](https://x.nl) als u wilt."
    assert in_je_vorm(tekst) == (
        "Als u `query_data` gebruikt, ziet u niets. Klik op [de bron](https://x.nl) als je wilt."
    )


def test_omzetten_is_idempotent():
    tekst = "Het getal dat u noemt, staat in de data. Jullie instelling had 3.303 studenten."
    assert in_je_vorm(in_je_vorm(tekst)) == in_je_vorm(tekst)


@pytest.mark.parametrize(
    "tekst",
    [
        "Het getal dat je noemt, staat in de data.",
        "In the U.S. there were 3,303 students.",
        "Data van de U.S. Census en de a.u.b.-knop.",
        "Uitstroom of uitval per uur, ook bij de U-bocht.",
        "Gebruik `u` als variabele, zie https://example.nl/u.",
        "```\nVerlangt u een uitsplitsing?\n```",
    ],
)
def test_geen_overgebleven_u_vorm(tekst):
    assert overgebleven_u_vormen(tekst) == []


def test_overgebleven_u_vorm_en_jullie_worden_gevonden_per_zin():
    tekst = "Er waren 3.303 studenten. Zoals u ziet, daalt het. Uw instelling groeit.\n- Jullie team telt mee."
    assert overgebleven_u_vormen(tekst) == [
        "Zoals u ziet, daalt het.",
        "Uw instelling groeit.",
        "- Jullie team telt mee.",
    ]


def test_overgebleven_u_vorm_is_een_zacht_probleem_met_de_zin_voor_het_model():
    [probleem] = overgebleven_u_vorm("Er waren 3.303 studenten. Zoals u ziet, daalt het.")
    assert not probleem.hard
    # De gebruiker ziet de melding, het model de zin om te herschrijven.
    assert probleem.melding == "Een zin spreekt je aan met u of jullie in plaats van met je."
    assert "Zoals u ziet, daalt het." in probleem and "je/jij" in probleem
    assert meldingen([probleem]) == [probleem.melding]


def test_de_controle_ziet_alleen_wat_de_omzetting_niet_kon():
    assert overgebleven_u_vorm("Het getal dat u noemt, staat in de data. Jullie instelling groeit.") == []
    assert overgebleven_u_vorm("Er waren 3.303 studenten.") == []


def test_een_engels_antwoord_heeft_geen_u_vorm():
    assert overgebleven_u_vorm("Did you mean U?", "en") == []
