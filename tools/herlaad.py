"""Een data-key terughalen na een herstart, uit zijn recept (#472).

De store leeft in het geheugen. Per key bewaart de database daarom hoe hij ontstond: de
laadaanroep (get_cbs_data, get_duo_data, get_rio_data, get_uwv_vacatures, get_roa_benchmark)
of de selectie (query_data) op een andere key. Hier wordt dat recept opnieuw uitgevoerd, door dezelfde tools als de eerste
keer: scopegrens, sentinelmaskering, CBS-afronding en KeyMeta komen zo hetzelfde terug.
Alleen toolnamen uit een vaste lijst; de argumenten toetst de tool zelf, er wordt niets
geëvalueerd. Een eigen berekening (run_analysis) wordt niet opnieuw uitgevoerd: van die
stap wordt geen script bewaard.
"""

import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from core.logging_util import foutkenmerk

from . import store
from .arbeidsmarkt import get_roa_benchmark, get_uwv_vacatures
from .catalog import catalogus_laatste_update
from .cbs import get_cbs_data
from .duo import get_duo_data
from .maten import get_maat
from .query import query_data
from .rio import get_rio_data
from .schemas import (
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_RIO_DATA,
    TOOL_GET_ROA_BENCHMARK,
    TOOL_GET_UWV_VACATURES,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)

logger = logging.getLogger(__name__)

STAP_ANALYSE = "eigen berekening (run_analysis)"

# De enige tools die een recept mag aanroepen, met de bron die een fout dan noemt.
_LADERS: dict[str, tuple[Callable[..., str], str]] = {
    TOOL_GET_CBS_DATA: (get_cbs_data, "CBS"),
    TOOL_GET_DUO_DATA: (get_duo_data, "DUO"),
    TOOL_GET_RIO_DATA: (get_rio_data, "RIO"),
    # Een arbeidsmarktresultaat is een dataset met een laadaanroep (#577).
    TOOL_GET_UWV_VACATURES: (get_uwv_vacatures, "UWV"),
    TOOL_GET_ROA_BENCHMARK: (get_roa_benchmark, "ROA"),
}
_MAX_STAPPEN = 10  # een keten van selecties; meer is een kapot of rondlopend recept
_MAX_REDEN = 300

Receptbron = Callable[[str], dict | None]

# Per gebruiker en key de dag (dd-mm-jjjj) waarop de data ná zijn eerdere antwoord opnieuw bij de bron is opgehaald
# (#472): haar cijfers kunnen afwijken van dat antwoord. De store is gedeeld, deze vlag niet (#788): dezelfde data is
# voor de een herladen en voor een ander, die haar net live opvroeg, de data van zijn antwoord. Een afleiding erft haar
# niet: wat live op deze data wordt berekend, is wat dat antwoord toont. Begrensd: zonder vlag geen melding.
_MAX_MARKERINGEN = 5000
_markeringen: OrderedDict[tuple[str, str], str] = OrderedDict()
_markeringen_slot = threading.Lock()


@dataclass(frozen=True)
class Herlaadresultaat:
    key: str
    gelukt: bool
    melding: str = ""  # waarom niet: de stap of de bron, met de key
    bronfout: bool = False  # de bron faalde, niet het recept
    herladen: bool = False  # de data komt van een nieuwe ophaalslag bij de bron, niet van het eerste antwoord


def recept(key: str, call: dict) -> dict | None:
    """Hoe `key` ontstond, als JSON-recept; None als deze aanroep de key niet maakte."""
    naam = call.get("name")
    known = store.meta(key)
    if naam == TOOL_RUN_ANALYSIS:
        # Zonder script: modelcode wordt in deze stap niet bewaard (#472).
        return {"afgeleid_van": known.afgeleid_van if known else None, "stap": STAP_ANALYSE, "herlaadbaar": False}
    if known is None or (naam not in _LADERS and naam not in (TOOL_QUERY_DATA, TOOL_GET_MAAT)):
        return None
    if known.laad:
        tool, args = known.laad
        return {"laad": [tool, args]}
    if naam == TOOL_QUERY_DATA and known.afgeleid_van:
        args = {k: v for k, v in (call.get("arguments") or {}).items() if k != "data_key"}
        return {"afgeleid_van": known.afgeleid_van, "tool": TOOL_QUERY_DATA, "args": args, "stap": known.stap}
    if naam == TOOL_GET_MAAT and known.afgeleid_van:
        # Het recept laadt en selecteert zelf (#188): de aanroep opnieuw doen geeft dezelfde key.
        return {
            "afgeleid_van": known.afgeleid_van,
            "tool": TOOL_GET_MAAT,
            "args": dict(call.get("arguments") or {}),
            "stap": known.stap,
        }
    return None


def herlaad(
    key: str, recept: dict, recept_van: Receptbron = lambda _key: None, username: str | None = None
) -> Herlaadresultaat:
    """Zet `key` terug in de store volgens `recept`; ouders eerst, via `recept_van`. De vlag krijgt `username`."""
    return _herlaad(key, recept, recept_van, 0, username)


def markeer(username: str | None, key: str) -> None:
    """Voor `username` staat `key` (weer) in de store met data die na zijn eerdere antwoord bij de bron is opgehaald."""
    if not username:
        return
    with _markeringen_slot:
        _markeringen[username, key] = f"{date.today():%d-%m-%Y}"
        _markeringen.move_to_end((username, key))
        while len(_markeringen) > _MAX_MARKERINGEN:
            _markeringen.popitem(last=False)


def wis_markering(username: str | None, key: str) -> None:
    """Een antwoord van `username` rust nu op de data zoals ze is: voor hem is ze niet (meer) herladen."""
    if username:
        with _markeringen_slot:
            _markeringen.pop((username, key), None)


def herladen_op(username: str | None, key: str) -> str | None:
    """De dag waarop `key` voor `username` opnieuw is opgehaald, of None; alleen zolang de store de key heeft."""
    if not username or store.meta(key) is None:
        return None
    with _markeringen_slot:
        return _markeringen.get((username, key))


def vergeet_gebruiker(username: str) -> None:
    """Na "verwijder al mijn gegevens" (#646) geen vlag van deze gebruiker meer."""
    with _markeringen_slot:
        for sleutel in [s for s in _markeringen if s[0] == username]:
            del _markeringen[sleutel]


def wis() -> None:
    with _markeringen_slot:
        _markeringen.clear()


def notitie(username: str | None, key: str) -> str | None:
    """Wat bij herladen data hoort: de cijfers kunnen afwijken van het eerdere antwoord. None als ze dat niet is.

    Per gebruiker, dus ook bij een latere download van wat een recept voor hem terugzette, en nooit voor een ander.
    """
    op = herladen_op(username, key)
    if op is None:
        return None
    known = store.meta(key)
    tekst = f"opnieuw opgehaald op {op}; de bron kan intussen zijn gewijzigd"
    if known is not None and known.bron == "cbs" and (update := catalogus_laatste_update(known.dataset)):
        tekst += f" (CBS-tabel laatst bijgewerkt op {update})"
    return tekst


def _herlaad(key: str, recept: dict, recept_van: Receptbron, stappen: int, username: str | None) -> Herlaadresultaat:
    if store.get(key) is not None:
        return _terug(key, username)
    if stappen > _MAX_STAPPEN or not isinstance(recept, dict):
        return Herlaadresultaat(key, gelukt=False, melding=f"Het recept van key {key} is onbruikbaar.")
    if "laad" in recept:
        return _laad(key, recept["laad"], username)
    if recept.get("tool") == TOOL_QUERY_DATA and recept.get("herlaadbaar", True):
        return _selecteer(key, recept, recept_van, stappen, username)
    if recept.get("tool") == TOOL_GET_MAAT:
        return _hermaat(key, recept, username)
    return Herlaadresultaat(key, gelukt=False, melding=_onherhaalbaar(key, recept.get("stap")))


def _onherhaalbaar(key: str, stap: object) -> str:
    stap = stap if isinstance(stap, str) and stap else "eerdere stap"
    return f"Stap '{stap}' van key {key} wordt niet automatisch opnieuw uitgevoerd."


def _laad(key: str, laad: object, username: str | None) -> Herlaadresultaat:
    tool, args = laad if isinstance(laad, list | tuple) and len(laad) == 2 else (None, None)
    if not isinstance(tool, str) or tool not in _LADERS or not isinstance(args, dict):
        return Herlaadresultaat(key, gelukt=False, melding=f"Het recept van key {key} noemt geen bekende laadstap.")
    functie, bron = _LADERS[tool]
    try:
        uitkomst = functie(**args)
    except Exception as e:  # een recept met argumenten die de tool niet (meer) kent
        logger.warning("herladen %s via %s mislukt: %s", key, tool, foutkenmerk(e))
        logger.debug("herladen %s via %s mislukt: %r", key, tool, e)
        uitkomst = ""
    if store.get(key) is None:
        reden = _reden(uitkomst) or "geen data."
        return Herlaadresultaat(
            key, gelukt=False, bronfout=True, melding=f"{bron} gaf de data voor key {key} niet opnieuw: {reden}"
        )
    markeer(username, key)
    return _terug(key, username)


def _selecteer(key: str, recept: dict, recept_van: Receptbron, stappen: int, username: str | None) -> Herlaadresultaat:
    ouder, args = recept.get("afgeleid_van"), recept.get("args")
    if not isinstance(ouder, str) or not isinstance(args, dict):
        return Herlaadresultaat(key, gelukt=False, melding=f"Het recept van key {key} is onbruikbaar.")
    if store.get(ouder) is None:
        ouder_recept = recept_van(ouder)
        if ouder_recept is None:
            return Herlaadresultaat(
                key, gelukt=False, melding=f"Key {key} rust op key {ouder}, en die is niet bewaard."
            )
        eerst = _herlaad(ouder, ouder_recept, recept_van, stappen + 1, username)
        if not eerst.gelukt:
            return Herlaadresultaat(key, gelukt=False, melding=eerst.melding, bronfout=eerst.bronfout)
    try:
        uitkomst = query_data(**{**args, "data_key": ouder})
    except Exception as e:  # argumenten die query_data op de herladen bron niet (meer) aanneemt
        logger.warning("herladen %s via query_data mislukt: %s", key, foutkenmerk(e))
        logger.debug("herladen %s via query_data mislukt: %r", key, e)
        uitkomst = ""
    if store.get(key) is None:
        stap = recept.get("stap") or "selectie"
        reden = _reden(uitkomst) or "geen data."
        return Herlaadresultaat(key, gelukt=False, melding=f"Stap '{stap}' gaf key {key} niet opnieuw: {reden}")
    # Ook op een ouder die live werd geladen: die is van ná het antwoord waar deze selectie onder stond.
    markeer(username, key)
    return _terug(key, username)


def _hermaat(key: str, recept: dict, username: str | None) -> Herlaadresultaat:
    """Een vaste maat (#188) opnieuw: get_maat laadt de bron en selecteert zelf, met dezelfde key als uitkomst."""
    args = recept.get("args")
    if not isinstance(args, dict):
        return Herlaadresultaat(key, gelukt=False, melding=f"Het recept van key {key} is onbruikbaar.")
    try:
        uitkomst = get_maat(**args)
    except Exception as e:  # argumenten die get_maat niet (meer) aanneemt
        logger.warning("herladen %s via get_maat mislukt: %s", key, foutkenmerk(e))
        logger.debug("herladen %s via get_maat mislukt: %r", key, e)
        uitkomst = ""
    if store.get(key) is None:
        stap = recept.get("stap") or "vaste maat"
        return Herlaadresultaat(
            key, gelukt=False, bronfout=True, melding=f"Stap '{stap}' gaf key {key} niet opnieuw: {_reden(uitkomst)}"
        )
    markeer(username, key)
    return _terug(key, username)


def _terug(key: str, username: str | None) -> Herlaadresultaat:
    return Herlaadresultaat(key, gelukt=True, herladen=herladen_op(username, key) is not None)


def _reden(uitkomst: str) -> str:
    """De kern van een toolmelding voor een mens: zonder foutcode, één zin."""
    try:
        parsed = json.loads(uitkomst)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        tekst = parsed.get("melding") if isinstance(parsed.get("melding"), str) else ""
    else:
        tekst = uitkomst
    if tekst.startswith("Fout ("):
        tekst = tekst.split("): ", 1)[-1]
    zin = tekst.split(". ", 1)[0].strip()
    if zin and not zin.endswith("."):
        zin += "."
    return zin[:_MAX_REDEN]
