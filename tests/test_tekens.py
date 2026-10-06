"""Modeltekst bereikt de gebruiker met gewone tekens (#326)."""

import asyncio
import json
from types import SimpleNamespace

from agent.grounding import unverified
from agent.stream import accumulate_stream
from agent.tekens import normaliseer, zonder_citaatkop


def _chunk(content):
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)])


async def _stream(*parts):
    for p in parts:
        yield _chunk(p)


def test_vaste_spaties_en_koppeltekens_worden_gewone_tekens():
    assert normaliseer("6\u202f447 bij Avans\u00a0Hogeschool, \u20115%") == "6 447 bij Avans Hogeschool, -5%"


def test_en_dash_en_minteken_worden_een_gewoon_minteken():
    """Audit 14 §3.7: '\u201341 558' bleef staan (U+2013); alleen U+2011 werd omgezet."""
    assert normaliseer("\u201341\u202f558 en \u22123,2%") == "-41 558 en -3,2%"


def test_grondingscontrole_herkent_een_negatief_getal_na_normalisatie():
    data = [json.dumps({"rijen": [{"VERSCHIL": -41558}]})]
    assert unverified(normaliseer("Een daling van \u201341\u202f558."), data, []) == []


def test_deltas_en_eindtekst_zijn_genormaliseerd():
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    result = asyncio.run(accumulate_stream(_stream("Er waren 6\u202f", "447 studenten, \u20112%."), emit=emit))
    assert result.text == "Er waren 6 447 studenten, -2%."
    assert "".join(e["content"] for e in events) == result.text


def test_grondingscontrole_herkent_het_getal_voor_en_na_normalisatie():
    data = [json.dumps({"rijen": [{"AANTAL": 6447}]})]
    ruw = "Avans had 6\u202f447 eerstejaars."
    assert unverified(ruw, data, []) == []
    assert unverified(normaliseer(ruw), data, []) == []


def test_openingscitaat_met_onderzoeksvraag_wordt_een_alinea():
    """#405: Opus begon met twee lege regels en '> **Onderzoeksvraag**'."""
    tekst = "\n\n> **Onderzoeksvraag**: hoeveel eerstejaars\n> had de HU?\n\nDe HU had 8.123 eerstejaars."
    assert (
        zonder_citaatkop(tekst)
        == "**Onderzoeksvraag**: hoeveel eerstejaars\nhad de HU?\n\nDe HU had 8.123 eerstejaars."
    )


def test_ander_citaat_blijft_staan():
    tekst = "> Bron: DUO\n\nTekst."
    assert zonder_citaatkop(tekst) == tekst
