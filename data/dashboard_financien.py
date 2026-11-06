"""Financiën van het bestuur op Mijn instelling (#935): `/api/dashboard/financien`.

De kengetallen van het bestuur van de gekozen instelling (solvabiliteit, liquiditeit, rentabiliteit, rijksbijdragen)
per verslagjaar, naast het gewogen sectorcijfer van de Inspectie, met de signaleringen en de vaste voorbehouden. Het
rekenen en het beleid staan in `tools/financien.py` (`voor_instelling`), dezelfde regels als de chat; hier alleen de
lading: de instelling uit het register, en een bron die uitvalt als gat (`niet_beschikbaar`) in plaats van een kapot
dashboard. Geen ranking van besturen en geen gemiddelde over besturen; de LLM komt er niet aan te pas.
"""

from __future__ import annotations

from data import instellingen
from tools import financien

from .dashboard import _dashboardlading, _niet_beschikbaar, _Onderdeel

ONDERDEEL = _Onderdeel("Financiën van het bestuur", financien.BRONNAAM)


def _oorzaak(e: Exception) -> Exception:
    """De netwerkfout achter `FinancienOnbereikbaar`, zodat de reden zegt wat er misging (time-out, HTTP-status)."""
    return e.__cause__ if isinstance(e.__cause__, Exception) else e


@_dashboardlading
def load_dashboard_financien(instelling: str) -> dict:
    profiel = instellingen.instellingsprofiel(instelling)
    if profiel is None:
        return {"instelling": instelling, "gevonden": False}
    result: dict = {"instelling": profiel["naam"], "gevonden": True, "sector": profiel["sector"], "financien": None}
    try:
        uitkomst = financien.voor_instelling(profiel)
    except Exception as e:
        _niet_beschikbaar(_oorzaak(e), "financien: niet beschikbaar", onderdeel=ONDERDEEL)
        return result
    if isinstance(uitkomst, str):
        result["melding"] = uitkomst
    else:
        result["financien"] = uitkomst
    return result
