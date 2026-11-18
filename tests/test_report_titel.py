"""De rapporttitel komt uit code: de vraag van de gebruiker, niet een titel van het model (#416, CH-09).

Vijf keer hetzelfde rapport gaf vijf titels. De vraag staat vast, dus de titel ook.
"""

import json

import pytest

from agent.report import ReportSpec, _parse_spec_from_response
from agent.report_checks import report_problems
from agent.report_titel import rapporttitel


@pytest.mark.parametrize(
    ("vraag", "titel"),
    [
        ("hoeveel eerstejaars had de HU in 2024/25?", "Hoeveel eerstejaars had de HU in 2024/25"),
        ("  instroom   per\njaar ?! ", "Instroom per jaar"),
        ("Welke opleidingen groeien:", "Welke opleidingen groeien"),
        ("Instroom mbo.", "Instroom mbo"),
    ],
)
def test_de_vraag_zonder_slotteken_met_hoofdletter(vraag, titel):
    assert rapporttitel(vraag, None) == titel


def test_lege_vraag_geeft_rapport():
    assert rapporttitel("", None) == "Rapport"
    assert rapporttitel("  ?\n", "Hogeschool Utrecht") == "Rapport"


def test_lange_vraag_breekt_op_een_woordgrens_af():
    vraag = (
        "Hoe ontwikkelde de instroom van eerstejaars in het hbo zich per sector en per provincie in de afgelopen jaren?"
    )
    titel = rapporttitel(vraag, None)

    assert len(titel) <= 80 and titel.endswith("…")
    assert vraag.startswith(titel.removesuffix("…"))
    assert vraag[len(titel) - 1] == " "  # niet midden in een woord


def test_een_woord_langer_dan_de_grens_wordt_afgekapt():
    titel = rapporttitel("x" * 100, None)
    assert len(titel) == 80 and titel.endswith("…")


_L05 = (
    "Ontwikkeling van het aantal eerstejaars hbo-studenten{} in de afgelopen vijf schooljaren per sector en provincie"
)
_FUNCTIEWOORDEN = set(
    "de het een in van voor op met bij naar en of over per aan om te tot uit door na onder tussen als dan die dat".split()
)


@pytest.mark.parametrize("komma", ["", ","])
def test_een_ingekorte_titel_eindigt_niet_op_een_los_functiewoord(komma):
    """De grens viel na "in de": de titel eindigt op het laatste inhoudswoord, zonder komma ervoor (#1023, L-05)."""
    titel = rapporttitel(_L05.format(komma), None, (2020, 2024))

    assert titel == "Ontwikkeling van het aantal eerstejaars hbo-studenten… (2020/21–2024/25)"
    assert len(titel) <= 80


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoe ontwikkelde de instroom van eerstejaars in het hbo zich per sector en per provincie in de afgelopen jaren?",
        _L05.format(""),
        "Instroom en uitval van eerstejaars in het hoger beroepsonderwijs, per en van het afgelopen schooljaar",
        "Instroom en uitval van eerstejaars in het wetenschappelijk onderwijs: tussen de afgelopen jaren",
    ],
)
def test_het_woord_voor_het_beletselteken_is_geen_functiewoord(vraag):
    titel = rapporttitel(vraag, None)

    assert len(titel) <= 80 and titel.endswith("…")
    assert titel.removesuffix("…").split()[-1].casefold() not in _FUNCTIEWOORDEN


def test_een_titel_van_alleen_functiewoorden_houdt_het_eerste_woord():
    assert rapporttitel("In de van het " + "x" * 100, None) == "In…"


def test_een_ingekorte_titel_die_op_een_inhoudswoord_eindigt_blijft_gelijk():
    vraag = "Aantal eerstejaars hbo-studenten per sector en provincie over de afgelopen vijf schooljaren, uitgesplitst"
    assert rapporttitel(vraag, None) == (
        "Aantal eerstejaars hbo-studenten per sector en provincie over de afgelopen vijf…"
    )


def test_instelling_komt_erbij_als_de_vraag_haar_niet_noemt():
    assert rapporttitel("Hoeveel eerstejaars?", "Hogeschool Utrecht") == "Hoeveel eerstejaars – Hogeschool Utrecht"
    assert rapporttitel("Eerstejaars van de hogeschool utrecht", "Hogeschool Utrecht") == (
        "Eerstejaars van de hogeschool utrecht"
    )
    assert rapporttitel("Hoeveel eerstejaars?", "  ") == "Hoeveel eerstejaars"


def test_vijf_modeltitels_geven_een_titel():
    context = {"topic": "hoeveel eerstejaars had de HU in 2024/25?", "instelling": "Hogeschool Utrecht"}
    titels = {
        _parse_spec_from_response(json.dumps({"title": t, "conclusie": "c"}), [], context).title
        for t in ["Instroom HU", "Eerstejaars HU 2024/25", "Rapport", "Instroom Hogeschool Utrecht", ""]
    }

    assert titels == {"Hoeveel eerstejaars had de HU in 2024/25 – Hogeschool Utrecht"}


def test_getallen_in_de_titel_zijn_geen_bewering():
    """De titel is de vraag van de gebruiker, net als de onderzoeksvraag: geen getal om te toetsen."""
    spec = ReportSpec(
        title="Groeide de instroom de laatste 5 jaar boven de 50.000",
        onderzoeksvraag="Groeide de instroom de laatste 5 jaar boven de 50.000?",
        beantwoordt=["Instroom per jaar"],
        conclusie="De instroom steeg van 41.200 naar 43.900.",
    )
    sources = [json.dumps({"rijen": [{"JAAR": 2020, "AANTAL": 41200}, {"JAAR": 2024, "AANTAL": 43900}]})]

    assert not [p for p in report_problems(spec, [], sources) if "niet in de opgehaalde data" in p]
