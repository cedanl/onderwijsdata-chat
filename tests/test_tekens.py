"""Modeltekst bereikt de gebruiker met gewone tekens (#326)."""

import asyncio
import json
from types import SimpleNamespace

from agent.getalnotatie import nl_notatie
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


def test_grondingscontrole_leest_een_decimale_punt_en_de_komma_die_ervan_komt_gelijk():
    """Besluit #326: 6.4 wordt 6,4 en 1234.5 wordt 1.234,5; de controle vindt na de omzetting hetzelfde."""
    data = [json.dumps({"rijen": [{"AANDEEL": 6.4, "GEMIDDELD": 6447.25, "AANTAL": 3303}]})]
    ruw = "Een aandeel van 6.4% bij 3303 eerstejaars, gemiddeld 6\u202f447.25 punten."
    getoond = nl_notatie(normaliseer(ruw))
    assert getoond == "Een aandeel van 6,4% bij 3.303 eerstejaars, gemiddeld 6.447,25 punten."
    assert unverified(ruw, data, []) == unverified(normaliseer(ruw), data, []) == unverified(getoond, data, []) == []


def test_grondingscontrole_vindt_een_ongedekt_getal_met_decimale_punt_ook_na_de_omzetting():
    data = [json.dumps({"rijen": [{"AANTAL": 3303}]})]
    ruw = "Gemiddeld 6340.5 eerstejaars."
    getoond = nl_notatie(normaliseer(ruw))
    assert getoond == "Gemiddeld 6.340,5 eerstejaars."
    assert [_geheel(n) for n in unverified(ruw, data, [])] == [_geheel(n) for n in unverified(getoond, data, [])]
    assert unverified(getoond, data, []) == ["6.340,5"]


def _geheel(getal: str) -> str:
    return getal.split(",")[0].replace(".", "")


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
