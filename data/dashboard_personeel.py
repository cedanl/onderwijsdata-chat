"""Personeel van een universiteit op Mijn instelling (#936): `/api/dashboard/personeel`, alleen met `ENABLE_WO_PERSONEEL`.

Fte zonder GEZO per jaar uit WOPI van Universiteiten van Nederland, naar wetenschappelijk personeel en OBP en het aandeel
tijdelijk, met de vaste zinnen van `tools/wo_personeel.py` (`reeks_van`, dezelfde rekenstappen als de chat). Een hbo- of
mbo-instelling krijgt geen cijfers en laadt WOPI niet: de kaart verschijnt daar niet. Een universiteit die niet in WOPI
staat, krijgt de vaste melding. Of het eindpunt bestaat, beslist de route (`tools.beschikbaarheid.wo_personeel`).
"""

from __future__ import annotations

from data import instellingen
from tools import wo_personeel

from .dashboard import _dashboardlading, _niet_beschikbaar, _Onderdeel

ONDERDEEL = _Onderdeel("Personeel (WOPI)", "UNL")


@_dashboardlading
def load_dashboard_personeel(instelling: str) -> dict:
    profiel = instellingen.instellingsprofiel(instelling)
    if profiel is None:
        return {"instelling": instelling, "gevonden": False}
    result: dict = {"instelling": profiel["naam"], "gevonden": True, "sector": profiel["sector"], "personeel": None}
    if profiel["sector"] != "wo":
        return result
    try:
        uitkomst = wo_personeel.reeks_van(profiel["instellingscode"], profiel["naam"])
    except Exception as e:
        _niet_beschikbaar(e, "personeel: WOPI niet beschikbaar", onderdeel=ONDERDEEL)
        return result
    if isinstance(uitkomst, str):
        result["melding"] = uitkomst
    else:
        result["personeel"] = uitkomst
    return result
