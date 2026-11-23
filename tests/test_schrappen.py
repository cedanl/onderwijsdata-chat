"""Alleen de zinnen met een ongedekt getal vervallen; de rest blijft, of het antwoord wordt ingehouden (#619)."""

import json

import pytest

from agent.binding import segmenten_met_scheiding
from agent.controles import antwoordcontrole, maak_getalcontrole
from agent.loop import LoopResult
from agent.probleem import Probleem, hard, harde
from agent.schrappen import GESCHRAPT, zonder_ongedekte_zinnen

_DATA = [json.dumps({"data_key": "duo:p02:a", "rijen": [{"AANTAL": 5943}, {"AANTAL": 6100}]})]
_VRAAG = "Hoeveel eerstejaars?"


def _resultaat(tekst: str) -> LoopResult:
    getalcontrole = maak_getalcontrole([], [])
    problemen = antwoordcontrole(_VRAAG, [], [], [], [], getalcontrole)(tekst, _DATA)
    return LoopResult(text=tekst, steps=[("query_data", _DATA[0])], problems=problemen)


def _schrap(tekst: str) -> LoopResult:
    getalcontrole = maak_getalcontrole([], [])
    return zonder_ongedekte_zinnen(
        _resultaat(tekst), antwoordcontrole(_VRAAG, [], [], [], [], getalcontrole), getalcontrole
    )


@pytest.mark.parametrize(
    "tekst",
    ["Een zin. Nog een zin.\nEen regel\n\n| a | b |\n|---|---|\n| 1 | 2 |", "Zonder scheiding aan het eind", ""],
)
def test_de_delen_zijn_samen_weer_de_hele_tekst(tekst):
    assert "".join(zin + scheiding for zin, scheiding in segmenten_met_scheiding(tekst)) == tekst


def test_een_zin_met_een_ongedekt_getal_vervalt_en_de_rest_blijft():
    tekst = (
        "In 2024 waren er 5.943 eerstejaars.\n\n"
        "Dat is 70.812 minder dan een jaar eerder. Het verschil zit vooral bij het hbo.\n\n"
        "Bron: DUO."
    )

    resultaat = _schrap(tekst)

    assert resultaat.text == (
        "In 2024 waren er 5.943 eerstejaars.\n\nHet verschil zit vooral bij het hbo.\n\nBron: DUO."
    )
    assert not harde(resultaat.problems)
    assert resultaat.problems[-1] == GESCHRAPT
    assert getattr(resultaat.problems[-1], "controle", None) == "zinnen_schrappen"


def test_een_tabelrij_met_een_ongedekt_getal_vervalt_met_zijn_regel():
    tekst = (
        "Er zijn 5.943 eerstejaars en 6.100 in het jaar erna. Meer detail:\n\n"
        "| jaar | aantal |\n|---|---|\n| 2024 | 5.943 |\n| 2025 | 7.777 |\n| 2026 | 6.100 |"
    )

    resultaat = _schrap(tekst)

    assert "7.777" not in resultaat.text
    assert "| 2024 | 5.943 |\n| 2026 | 6.100 |" in resultaat.text


def test_de_melding_noemt_de_weggelaten_tabelrij_met_haar_eerste_cel():
    """#1099: bij een jaartabel viel stil het nieuwste jaar weg, met de melding over "zinnen"."""
    tekst = (
        "Er zijn 5.943 eerstejaars en 6.100 in het jaar erna. Meer detail:\n\n"
        "| jaar | aantal |\n|---|---|\n| 2024 | 5.943 |\n| 2025/26 | 7.777 |\n| 2026 | 6.100 |\n| 2027 | 5.943 |"
    )

    resultaat = _schrap(tekst)

    assert resultaat.problems[-1].melding == (
        "Tabelrijen met een getal dat niet in de opgehaalde data staat, zijn weggelaten (rij: 2025/26). "
        "Stel de vraag opnieuw, of preciezer, voor die cijfers."
    )
    assert resultaat.problems[-1] != GESCHRAPT
    assert getattr(resultaat.problems[-1], "controle", None) == "zinnen_schrappen"


def test_de_melding_noemt_zinnen_en_tabelrijen_als_beide_wegvallen():
    tekst = (
        "In 2024 waren er 5.943 eerstejaars. Dat is 70.812 minder dan een jaar eerder. Het verschil zit bij het hbo.\n\n"
        "| jaar | aantal |\n|---|---|\n| 2024 | 5.943 |\n| 2025 | 7.777 |\n| 2026 | 6.100 |\n| 2027 | 5.943 |"
    )

    resultaat = _schrap(tekst)

    assert resultaat.problems[-1].melding.startswith("Zinnen en tabelrijen met een getal")
    assert "(rij: 2025)" in resultaat.problems[-1].melding


def test_de_melding_noemt_hoogstens_vijf_rijen_en_telt_de_rest():
    fout = "".join(f"| {1990 + n} | 7.{n:03d} |\n" for n in range(7))
    goed = "".join(f"| {2010 + n} | 5.943 |\n" for n in range(8))
    tekst = f"Er zijn 5.943 eerstejaars in 2024.\n\n| jaar | aantal |\n|---|---|\n{fout}{goed}"

    resultaat = _schrap(tekst)

    assert "(rij: 1990, 1991, 1992, 1993, 1994 en 2 andere)" in resultaat.problems[-1].melding


def test_een_tabel_die_meer_rijen_verliest_dan_ze_houdt_houdt_het_antwoord_in():
    """C1 (#976): elf van twaalf rijen vielen weg onder een conclusie "bij 12 hogescholen". Een restant van een tabel
    spreekt de rest van het antwoord tegen; dan inhouden, met de meldingen."""
    tekst = (
        "Bij vier hogescholen daalde het aantal ingeschrevenen. Een sterk verband met het oordeel is er niet.\n\n"
        "| hogeschool | 2021 | 2025 |\n|---|---|---|\n"
        "| A | 5.943 | 6.100 |\n| B | 7.777 | 6.100 |\n| C | 8.888 | 5.943 |\n| D | 9.999 | 5.943 |\n\n"
        "### Wat valt op\nDe verschillen zijn klein. Het oordeel komt uit 2026. De aantallen zijn alle vormen samen. "
        "De koppeling is op BRIN. Twee hogescholen ontbreken. Kleine aantallen spelen geen rol."
    )

    resultaat = _schrap(tekst)

    assert harde(resultaat.problems)
    assert resultaat.text == tekst


def test_een_antwoord_dat_bijna_helemaal_uit_ongedekte_zinnen_bestaat_blijft_ingehouden():
    tekst = "In 2024 waren er 6.340 eerstejaars. Dat is 11.111 meer dan in 2023."

    resultaat = _schrap(tekst)

    assert harde(resultaat.problems)
    assert resultaat.text == tekst


def test_een_antwoord_zonder_andere_zin_blijft_ingehouden():
    resultaat = _schrap("Toch 6.340.")

    assert harde(resultaat.problems)
    assert resultaat.text == "Toch 6.340."


def test_een_ander_hard_probleem_schrapt_niets():
    tekst = "In 2024 waren er 5.943 eerstejaars. Dat is 70.812 minder. Een derde zin zonder getal. Nog een zin."
    resultaat = _resultaat(tekst)
    resultaat.problems = [*resultaat.problems, *hard([Probleem("Een ander feit klopt niet.")])]
    getalcontrole = maak_getalcontrole([], [])

    na = zonder_ongedekte_zinnen(resultaat, antwoordcontrole(_VRAAG, [], [], [], [], getalcontrole), getalcontrole)

    assert na is resultaat


def test_een_antwoord_zonder_hard_probleem_blijft_zoals_het_was():
    resultaat = _resultaat("In 2024 waren er 5.943 eerstejaars.")

    assert not resultaat.problems
    getalcontrole = maak_getalcontrole([], [])
    assert (
        zonder_ongedekte_zinnen(resultaat, antwoordcontrole(_VRAAG, [], [], [], [], getalcontrole), getalcontrole)
        is resultaat
    )


def test_blijft_de_rest_hard_door_een_ander_probleem_dan_blijft_het_inhouden():
    tekst = "In 2024 waren er 5.943 eerstejaars. Dat is 70.812 minder. Een derde zin zonder getal. Nog een zin."
    getalcontrole = maak_getalcontrole([], [])

    def check(text, tool_results):
        return hard([Probleem("Ook de rest klopt niet.")])

    resultaat = _resultaat(tekst)
    na = zonder_ongedekte_zinnen(resultaat, check, getalcontrole)

    assert na is resultaat


_UITVAL = (
    "Vorig jaar (2024/'25) stopte **15,4%** van de eerstejaars met de opleiding: ruim 16.700 studenten.\n\n"
    "Dat is iets meer dan een jaar eerder (14,9%).\n\n"
    "Bron: CBS, Hoger onderwijs; eerstejaarsstudenten, vooropleiding en opleidingsfase (85422NED)."
)


def test_blijft_na_het_schrappen_alleen_een_bronregel_over_dan_houdt_het_antwoord_in():
    """#1107: van het antwoord bleef alleen een Bron-regel (met een tabel die de data niet heeft) en de melding."""
    resultaat = _schrap(_UITVAL)

    assert harde(resultaat.problems)
    assert resultaat.text == _UITVAL


def test_een_bronregel_met_puntkomma_telt_als_een_segment():
    """#1107: bij de puntkomma splitste de bronregel in drie stukken, die als inhoud meetelden: drie van de zeven
    segmenten leken weg te vallen, terwijl het er drie van de vijf zijn."""
    tekst = (
        "In 2024 waren er 70.812 eerstejaars. Dat is 11.111 meer dan in 2023. Het waren er 22.222 in 2022. "
        "Het verschil zit vooral bij het hbo.\n\n"
        "Bron: DUO, Inschrijvingen; hoger onderwijs; per instelling (p02)."
    )

    resultaat = _schrap(tekst)

    assert harde(resultaat.problems)
    assert resultaat.text == tekst


@pytest.mark.parametrize(
    "rest",
    [
        "## Uitval\n\nBron: CBS.",
        "**Bronnen**\n- CBS, tabel 85422NED\n- DUO, ingeschrevenen",
        "### Bronnen\n\n- CBS, tabel 85422NED\n- DUO, ingeschrevenen",
        "Bronnen:\n- CBS, tabel 85422NED",
    ],
)
def test_kopjes_en_bronnen_zijn_geen_inhoud(rest):
    tekst = f"In 2024 waren er 70.812 eerstejaars.\n\n{rest}"

    resultaat = _schrap(tekst)

    assert harde(resultaat.problems)
    assert resultaat.text == tekst


def test_een_inhoudszin_naast_de_geschrapte_zin_houdt_het_schrappen_bij_een_bronregel():
    tekst = (
        "In 2024 waren er 5.943 eerstejaars. Dat is 70.812 minder dan een jaar eerder.\n"
        "Het verschil zit vooral bij het hbo.\n\n"
        "Bron: DUO; Inschrijvingen (p02)."
    )

    resultaat = _schrap(tekst)

    assert "70.812" not in resultaat.text
    assert "Het verschil zit vooral bij het hbo." in resultaat.text
    assert resultaat.problems[-1] == GESCHRAPT
