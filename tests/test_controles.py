"""De antwoordcontrole krijgt wat ze van het gesprek moet weten als parameter, niet uit de sessie (#694)."""

import ast
import inspect
import json

from agent import controles
from agent.controles import antwoordcontrole

_VRAAG = "Hoeveel eerstejaars?"
_DATA = [json.dumps({"data_key": "duo:p02:a", "rijen": [{"JAAR": 2023, "AANTAL": 5943}]})]


def _problemen(tekst: str, clarify_keuzes: list[str] | None = None) -> list[str]:
    return antwoordcontrole(_VRAAG, [], [], clarify_keuzes or [], [])(tekst, _DATA)


def test_een_gekozen_jaar_dat_het_antwoord_niet_noemt_wordt_gemeld():
    problemen = _problemen("Het zijn er 5943 in 2018.", clarify_keuzes=["2023"])

    assert any("Gekozen was '2023'" in p for p in problemen), problemen


def test_zonder_gekozen_opties_is_er_geen_keuzeprobleem():
    assert not any("Gekozen was" in p for p in _problemen("Het zijn er 5943 in 2018."))


def test_een_ongedekt_getal_wordt_nog_steeds_gemeld():
    assert any("1234" in p or "1.234" in p for p in _problemen("Het zijn er 1234."))


def test_de_controlemodule_kent_geen_sessie_en_geen_emit():
    """Wat de controle nodig heeft, staat in de signatuur; dat houdt haar zonder transport te testen."""
    namen = {n.id for n in ast.walk(ast.parse(inspect.getsource(controles))) if isinstance(n, ast.Name)} | {
        n.arg for n in ast.walk(ast.parse(inspect.getsource(controles))) if isinstance(n, ast.arg)
    }

    assert not namen & {"session", "emit"}
