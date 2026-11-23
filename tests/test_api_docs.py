"""docs/api.md noemt elk eindpunt van de API (#1168)."""

import re
from pathlib import Path

from server import create_app

API_MD = (Path(__file__).resolve().parent.parent / "docs" / "api.md").read_text(encoding="utf-8")


def _zonder_namen(pad: str) -> str:
    """`/api/workbooks/{wb_id}` en `/api/workbooks/{id}` zijn hetzelfde pad: de naam van de parameter telt niet."""
    return re.sub(r"\{[^}]+\}", "{}", pad)


def test_elk_eindpunt_uit_het_schema_staat_in_de_api_referentie():
    # Het schema van een app met documentatie aan: elke route die geen include_in_schema=False heeft.
    paden = create_app(api_docs=True).openapi()["paths"]
    referentie = _zonder_namen(API_MD)

    ontbreekt = sorted(pad for pad in paden if _zonder_namen(pad) not in referentie)

    assert not ontbreekt, f"niet in docs/api.md: {ontbreekt}"


def test_de_bronstatus_staat_met_zijn_antwoordvorm_in_de_referentie():
    rij = next(regel for regel in API_MD.splitlines() if "`/api/bronstatus`" in regel)

    assert "niet_live" in rij
    assert "operatie.md" in rij
