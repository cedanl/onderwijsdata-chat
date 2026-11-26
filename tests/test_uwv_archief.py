"""get_uwv_vacatures is een archief (#1226, besluit #1221): UWV maakt Open Match niet meer.

Elk resultaat van de tool begint met het veld `archief`: de peildatum (16-05-2023, uit de data) en de melding dat UWV
deze reeks niet meer maakt, met de verwijzing naar de actuele bron (get_vacatures, CBS 83599NED). Ook de meldingen
zonder cijfers (onbekende provincie, gemeente of sector) beginnen ermee. De melding komt uit code, niet uit het model
(zoals #1219). De tooltoelichting en de systeemprompt sturen het model eerst naar get_vacatures.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core import actualiteit
from data import arbeidsmarkt
from tools.arbeidsmarkt import get_uwv_vacatures
from tools.schemas import TOOL_GET_UWV_VACATURES, TOOL_GET_VACATURES, TOOL_SCHEMAS

_UWV = pd.DataFrame(
    {
        "PEILDATUM": ["16-05-2023"] * 2,
        "PROVINCIE": ["Utrecht", "Utrecht"],
        "GEMEENTE": ["Utrecht", "Amersfoort"],
        "BEROEPENCLUSTER": ["Zorg en welzijn", "ICT"],
        "AANTAL": [900, 200],
    }
)
_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def uwv(monkeypatch):
    monkeypatch.setattr(actualiteit, "nu", lambda: datetime(2026, 11, 25, tzinfo=UTC))
    with (
        patch.object(arbeidsmarkt, "_uwv", return_value=_UWV),
        patch("tools.arbeidsmarkt.scope_blokkade", return_value=None),
    ):
        yield


def test_het_resultaat_begint_met_het_archief():
    uit = json.loads(get_uwv_vacatures("Utrecht"))

    assert next(iter(uit)) == "archief"
    archief = uit["archief"]
    assert archief["peildatum"] == "16-05-2023"
    assert "UWV maakt deze reeks niet meer" in archief["melding"]
    assert "get_vacatures" in archief["melding"] and "83599NED" in archief["melding"]
    assert uit["totaal_vacatures"] == 1100  # de cijfers blijven


def test_ook_met_gemeente_en_sector_begint_het_met_het_archief():
    uit = json.loads(get_uwv_vacatures("Utrecht", sector="Zorg en welzijn", gemeente="Amersfoort"))
    assert next(iter(uit)) == "archief" and uit["archief"]["peildatum"] == "16-05-2023"


@pytest.mark.parametrize(
    "args",
    [
        {"provincie": "Atlantis"},
        {"provincie": "Utrecht", "gemeente": "Atlantis"},
        {"provincie": "Utrecht", "sector": "X"},
    ],
)
def test_een_melding_zonder_cijfers_noemt_het_archief_ook(args):
    uit = get_uwv_vacatures(**args)
    assert uit.startswith("Archief (UWV Open Match, peildatum 16-05-2023): UWV maakt deze reeks niet meer")
    assert "get_vacatures" in uit


def test_de_ouderdomstoelichting_verwijst_naar_de_actuele_tool():
    uit = json.loads(get_uwv_vacatures("Utrecht"))
    assert "get_vacatures" in uit["ouderdom_toelichting"]
    assert "(nog) niet" not in uit["ouderdom_toelichting"]  # de app laadt de kwartaalcijfers nu wel


def _beschrijving(naam: str) -> str:
    return next(t["function"]["description"] for t in TOOL_SCHEMAS if t["function"]["name"] == naam)


def test_de_tooltoelichting_stuurt_eerst_naar_get_vacatures():
    uwv = _beschrijving(TOOL_GET_UWV_VACATURES)
    assert uwv.startswith("Archief") and "get_vacatures" in uwv and "mei 2023" in uwv
    assert "eerste keus" in _beschrijving(TOOL_GET_VACATURES)


def test_de_systeemprompt_stuurt_eerst_naar_get_vacatures():
    assert "get_vacatures" in _PROMPT and "get_ontstane_vacatures" in _PROMPT
    eerste_vacatures = _PROMPT.index("get_vacatures")
    assert eerste_vacatures < _PROMPT.index("get_uwv_vacatures")
    assert "UWV-vacatures als arbeidsmarkt-context" not in _PROMPT
