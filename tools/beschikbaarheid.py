"""Geeft een bron met een eigen tool in deze omgeving antwoord? Eén plek voor die vraag (#956).

Twee bronnen hangen van de omgeving af:

- de financiële verantwoording van DUO per bestuur (#935): tot DUO de licentie bevestigt alleen lokaal en op test
  (besluit 6 op #725); op playground en productie geeft `get_bestuursfinancien` alleen een melding;
- WOPI van UNL (#936): alleen met de vlag `ENABLE_WO_PERSONEEL` (core/config.py), aan op test, tot UNL hergebruik
  bevestigt.

Wie wil weten of zo'n bron hier antwoord geeft, vraagt het hier: de tool zelf, de toolset, herladen uit een recept, de
suggestievragen op het startscherm (`/api/config`), de status in de catalogus (search_catalog, dataset_details) en de
tellingen. Zo kan de ene plek niet "beschikbaar" zeggen terwijl de andere een melding geeft.

De regels lezen de instelling bij elke aanroep, niet bij import; alleen de toolset en de schema's leggen de vlag van WOPI
vast bij het starten (tools/__init__.py, tools/schemas.py), want de toolset is per proces.
"""

from config import Config
from core import config

# Tot DUO de licentie van de financiële verantwoording bevestigt (besluit 6 op #725). Na de bevestiging: True.
LICENTIE_BEVESTIGD = False
_OMGEVINGEN_ZONDER_LICENTIE = ("local", "development", "test")

# De bronnen bij naam, zoals /api/config en de frontend ze noemen.
FINANCIEN = "financien"
WO_PERSONEEL = "wo_personeel"


def financien() -> bool:
    """Mag get_bestuursfinancien cijfers geven? Overal na de bevestiging van de licentie, tot dan lokaal en op test."""
    return LICENTIE_BEVESTIGD or Config.APP_ENV in _OMGEVINGEN_ZONDER_LICENTIE


def wo_personeel() -> bool:
    """Staat WOPI aan (ENABLE_WO_PERSONEEL)?"""
    return config.WO_PERSONEEL_ENABLED


_REGELS = {FINANCIEN: financien, WO_PERSONEEL: wo_personeel}


def bronnen() -> dict[str, bool]:
    """Per bron met een omgevingsregel of hij hier antwoord geeft; voor /api/config."""
    return {naam: regel() for naam, regel in _REGELS.items()}


def tool(naam: str) -> bool:
    """Geeft deze tool hier antwoord? Een tool zonder omgevingsregel altijd."""
    from .schemas import TOOL_GET_BESTUURSFINANCIEN, TOOL_GET_WO_PERSONEEL  # hier: schemas leest deze module

    regel = {TOOL_GET_BESTUURSFINANCIEN: financien, TOOL_GET_WO_PERSONEEL: wo_personeel}.get(naam)
    return regel is None or regel()
