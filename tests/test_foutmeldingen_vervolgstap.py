"""Elke foutmelding naar de browser geeft een vervolgstap en lekt niets technisch (#703).

De meldingen die de browser kan krijgen staan in `tests/e2e/fixtures/foutmeldingen.json`; de Playwright-spec
`foutmeldingen.spec.js` speelt ze af tegen de echte pagina. Deze test houdt dat bestand gelijk aan wat `core.errors`
nu maakt, zodat de spec nooit een verouderde tekst toetst. Bijwerken na een bewuste wijziging van een tekst:
`FOUTMELDINGEN_BIJWERKEN=1 pytest tests/test_foutmeldingen_vervolgstap.py`.
"""

import json
import os
import re
import uuid
from pathlib import Path

import litellm
import pytest

from core.errors import Gebruikersfout, error_event

FIXTURE = Path(__file__).parent / "e2e" / "fixtures" / "foutmeldingen.json"
_FOUT_ID = "abcd1234"
_GEHEIM = "geheim intern detail /app/data/cache/x.parquet"

# Eén geval per categorie die de gebruiker kan zien. De sleutel is de naam in de tabel van docs/operatie.md.
_GEVALLEN = {
    "api-sleutel": lambda: litellm.AuthenticationError(_GEHEIM, llm_provider="azure_ai", model="m"),
    "model-onbekend": lambda: litellm.NotFoundError(_GEHEIM, llm_provider="azure_ai", model="m"),
    "limiet": lambda: litellm.RateLimitError(_GEHEIM, llm_provider="azure_ai", model="m"),
    "api-onbereikbaar": lambda: litellm.APIConnectionError(_GEHEIM, llm_provider="azure_ai", model="m"),
    "modelfout": lambda: litellm.BadRequestError(_GEHEIM, llm_provider="azure_ai", model="m"),
    "timeout": lambda: TimeoutError(_GEHEIM),
    "intern": lambda: ValueError(_GEHEIM),
    "gebruikersfout": lambda: Gebruikersfout(
        "Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald."
    ),
}

# Een vervolgstap is een werkwoord in gebiedende wijs dat de gebruiker iets te doen geeft.
_VERVOLGSTAP = re.compile(r"\b(probeer|wacht|controleer|kies|stel|geef)\b", re.IGNORECASE)
_TECHNISCH = re.compile(r"Traceback|\.py\b|\.parquet|/app/|/home/|File \"|\{|\}|Exception|Error:", re.IGNORECASE)


@pytest.fixture
def vaste_fout_id(monkeypatch):
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(f"{_FOUT_ID}-0000-4000-8000-000000000000"))


def _catalogus() -> dict[str, dict]:
    return {naam: error_event(maak()) for naam, maak in _GEVALLEN.items()}


@pytest.fixture
def catalogus(vaste_fout_id):
    return _catalogus()


def test_elke_foutmelding_geeft_een_vervolgstap(catalogus):
    zonder = [naam for naam, ev in catalogus.items() if not _VERVOLGSTAP.search(ev["message"])]

    assert not zonder, f"geen vervolgstap in: {zonder}"


def test_geen_foutmelding_lekt_technische_details(catalogus):
    lekken = {naam: ev["message"] for naam, ev in catalogus.items() if _TECHNISCH.search(ev["message"])}

    assert not lekken, lekken
    assert not [naam for naam, ev in catalogus.items() if "geheim" in ev["message"]]


def test_een_fout_zonder_vaste_tekst_noemt_het_fout_id(catalogus):
    """De beheerder zoekt het ID in het log (docs/operatie.md): modelfout en interne fout moeten het tonen."""
    for naam in ("modelfout", "timeout", "intern"):
        assert f"fout-ID {_FOUT_ID}" in catalogus[naam]["message"], naam


def test_de_browserfixture_is_gelijk_aan_wat_core_errors_maakt(catalogus):
    if os.environ.get("FOUTMELDINGEN_BIJWERKEN"):
        FIXTURE.write_text(json.dumps(catalogus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == catalogus, (
        "tests/e2e/fixtures/foutmeldingen.json loopt achter; draai met FOUTMELDINGEN_BIJWERKEN=1"
    )
