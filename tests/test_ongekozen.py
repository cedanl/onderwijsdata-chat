"""Een instelling die de gebruiker niet koos, hoort net zo min in het antwoord als een studie (#970, vervolg op #961).

agent/ongekozen.py keek alleen naar "Meer studies passen". get_studiekeuze geeft ook "Meer instellingen passen" met
dezelfde vaste zin (`studiekeuze.KIES_EERST`); haalde het model daarna zelf een van die instellingen op, dan zag geen
controle het. En na drie kaarten is clarify_scope niet meer in de toolset, terwijl melding en herkansing het model er
alleen naar verwezen: nu zeggen ze ook wat het dan doet (de keuze als vraag in het antwoord).

Zonder netwerk: het proefbestand van `onderwijsbronnen.skdb`, zoals tests/test_review08_modelgedrag.py.
"""

import importlib
import json
import re
from pathlib import Path

import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from agent.controles import antwoordcontrole
from agent.ongekozen import ongekozen_studies
from data import instellingen
from tools import studiekeuze
from tools.schemas import TOOL_CLARIFY_SCOPE

run = importlib.import_module("agent.run")
SYSTEM = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(instellingen, "instellingsprofiel", lambda naam: None)
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _keuzemelding() -> tuple[str, dict[str, str]]:
    """De melding bij "Proef" (twee instellingen, op woordbegin: #971) en haar opties (BRIN → naam)."""
    melding = studiekeuze.get_studiekeuze(instelling="Proef")
    assert melding.startswith("Meer instellingen passen")
    opties = {brin: naam.strip() for naam, brin in re.findall(r"([^:;]+?) \((\d{2}[A-Z]{2})\)", melding)}
    assert len(opties) >= 2
    return melding, opties


def _instellingsuitkomst(brin: str) -> str:
    return json.dumps(
        {
            "dataset": studiekeuze.DATASET,
            "weergave": "opleidingen",
            "selectie": {"weergave": "opleidingen", "instelling": brin},
            "rijen": [{"instelling": "x", "brin": brin}],
        }
    )


def test_een_instelling_die_de_gebruiker_niet_koos_geeft_een_probleem():
    melding, opties = _keuzemelding()
    brins = list(opties)[:2]

    (probleem,) = ongekozen_studies(
        "Welke opleidingen heeft de hogeschool?", [melding, *map(_instellingsuitkomst, brins)]
    )

    assert "meer instellingen" in probleem and all(b in probleem for b in brins)
    assert "BRIN-code" in probleem


@pytest.mark.parametrize("noemt", ["code", "naam"])
def test_een_instelling_die_de_vraag_noemt_is_gekozen(noemt):
    melding, opties = _keuzemelding()
    brin, naam = next(iter(opties.items()))
    vraag = f"Welke opleidingen heeft {brin if noemt == 'code' else naam.upper()}?"

    assert ongekozen_studies(vraag, [melding, _instellingsuitkomst(brin)]) == []


def test_zonder_keuzemelding_geen_probleem_over_instellingen():
    assert ongekozen_studies("Welke opleidingen heeft de hogeschool?", [_instellingsuitkomst("25DW")]) == []


def test_de_antwoordcontrole_ziet_de_ongekozen_instelling():
    melding, opties = _keuzemelding()
    brin = next(iter(opties))
    check = antwoordcontrole("Welke opleidingen heeft de hogeschool?", [], [], [], [])

    problemen = check("Er zijn veel opleidingen.", [melding, _instellingsuitkomst(brin)])

    assert any(brin in p and "meer instellingen" in p for p in problemen)


# --- na drie kaarten is clarify_scope weg ------------------------------------------------------------------------


def test_na_drie_kaarten_is_clarify_scope_weg():
    namen = {t["function"]["name"] for t in run.tools_for({"clarify_rondes": 3})}
    assert TOOL_CLARIFY_SCOPE not in namen


def test_melding_herkansing_en_prompt_zeggen_wat_het_model_zonder_clarify_scope_doet():
    """Anders stuurt de herkansing het model naar een tool die er niet is, en zegt de prompt "nooit als platte tekst"."""
    melding, opties = _keuzemelding()
    (probleem,) = ongekozen_studies("Welke opleidingen?", [melding, _instellingsuitkomst(next(iter(opties)))])

    for tekst in (studiekeuze.KIES_EERST, probleem):
        assert "clarify_scope er niet meer" in tekst and "als vraag met" in tekst and "in je antwoord" in tekst
    regel = next(r for r in SYSTEM.splitlines() if r.startswith("**Meer studies of instellingen:**"))
    assert "er niet meer" in regel and "als vraag met de opties in je antwoord" in regel
