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
