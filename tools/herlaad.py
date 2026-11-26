"""Een data-key terughalen na een herstart, uit zijn recept (#472).

De store leeft in het geheugen. Per key bewaart de database daarom hoe hij ontstond: de
laadaanroep (get_cbs_data, get_duo_data, get_rio_data, get_vacatures, get_ontstane_vacatures, get_uwv_vacatures,
get_roa_benchmark, get_bestuursfinancien, get_wo_personeel, get_studiekeuze), de vaste maat (get_maat) of de selectie (query_data) op
een andere key. Hier wordt dat recept opnieuw uitgevoerd, door dezelfde tools als de eerste keer: scopegrens,
sentinelmaskering, CBS-afronding en KeyMeta komen zo hetzelfde terug. Alleen toolnamen uit een vaste lijst; de argumenten toetst de tool zelf, er wordt niets
geëvalueerd. Een eigen berekening (run_analysis) wordt niet opnieuw uitgevoerd: van die
stap wordt geen script bewaard. Een koppeling (koppel_data) ook niet: ze rust op twee tabellen.
"""

import json
import logging
import re
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from core.logging_util import foutkenmerk

from . import beschikbaarheid, maten, store
from .arbeidsmarkt import get_roa_benchmark, get_uwv_vacatures
from .catalog import bron_titel, catalogus_laatste_update, is_scopeweigering
from .cbs import laad_cbs_data
from .duo import get_duo_data
from .financien import get_bestuursfinancien
from .koppel import STAP as STAP_KOPPELING
from .maten import get_maat
from .query import query_data
from .rio import laad_rio_data
from .schemas import (
    TOOL_GET_BESTUURSFINANCIEN,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_MAAT,
    TOOL_GET_ONTSTANE_VACATURES,
    TOOL_GET_RIO_DATA,
    TOOL_GET_ROA_BENCHMARK,
    TOOL_GET_STUDIEKEUZE,
    TOOL_GET_UWV_VACATURES,
    TOOL_GET_VACATURES,
    TOOL_GET_WO_PERSONEEL,
    TOOL_KOPPEL_DATA,
    TOOL_QUERY_DATA,
    TOOL_RUN_ANALYSIS,
)
from .studiekeuze import get_studiekeuze
from .vacatures import get_ontstane_vacatures, get_vacatures
from .wo_personeel import get_wo_personeel

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

STAP_ANALYSE = "eigen berekening (run_analysis)"

# De enige tools die een recept mag aanroepen, met de bron die een fout dan noemt. CBS en RIO zonder de poort van de
# beurt: het recept zegt zelf of de lading het vo-deel had (`vo_context`, #879, #880).
_LADERS: dict[str, tuple[Callable[..., str], str]] = {
    TOOL_GET_CBS_DATA: (laad_cbs_data, "CBS"),
    TOOL_GET_DUO_DATA: (get_duo_data, "DUO"),
    TOOL_GET_RIO_DATA: (laad_rio_data, "RIO"),
    # Een arbeidsmarktresultaat is een dataset met een laadaanroep (#577).
    TOOL_GET_UWV_VACATURES: (get_uwv_vacatures, "UWV"),
    # De actuele vacatures van CBS (#1226, #1227): ook een vaste tabel met laadaanroep.
    TOOL_GET_VACATURES: (get_vacatures, "CBS"),
    TOOL_GET_ONTSTANE_VACATURES: (get_ontstane_vacatures, "CBS"),
    TOOL_GET_ROA_BENCHMARK: (get_roa_benchmark, "ROA"),
    # Een bron met een eigen resultaatvorm zet haar tabel met laadaanroep in de store (#956). Of die bron hier antwoord
    # geeft, beslist tools/beschikbaarheid.py bij het herladen: zonder vlag of licentie haalt ook een recept niets op.
    TOOL_GET_BESTUURSFINANCIEN: (get_bestuursfinancien, "DUO"),
    TOOL_GET_WO_PERSONEEL: (get_wo_personeel, "Universiteiten van Nederland"),
    TOOL_GET_STUDIEKEUZE: (get_studiekeuze, "Landelijk Centrum Studiekeuze"),
}
_MAX_STAPPEN = 10  # een keten van selecties; meer is een kapot of rondlopend recept
_MAX_REDEN = 300
_NIET_MEER_IN_CATALOGUS = "Deze dataset staat niet meer in de catalogus."
# Een interne key in een toolmelding, met of zonder aanhalingstekens: bron, dataset en minstens één deel meer.
_KEY_IN_TEKST = re.compile(r"'?\b[a-z][\w]*:[\w.-]+(?::[\w.-]+)+\b'?")

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
    melding: str = ""  # waarom niet: de stap of de bron, met de catalogustitel; de key staat alleen in de log
    bronfout: bool = False  # de bron faalde, niet het recept
    herladen: bool = False  # de data komt van een nieuwe ophaalslag bij de bron, niet van het eerste antwoord


# De laders die hun tabel aan de aanroeper geven in plaats van aan de store (`apart`, #1240): voor "herhaal deze
# analyse", nu alleen CBS. DUO en RIO sluiten hier later aan.
_APART: dict[str, Callable[..., str]] = {TOOL_GET_CBS_DATA: laad_cbs_data}


@dataclass(frozen=True)
class Apart:
    """Een laadrecept opnieuw uitgevoerd, buiten de store: de tabel zoals de bron haar nu levert, met haar meta."""

    key: str
    data: "pd.DataFrame"
    meta: store.KeyMeta


def apart_herhaalbaar(tool: object) -> bool:
    """Kan `apart` deze laadstap opnieuw uitvoeren?"""
    return isinstance(tool, str) and tool in _APART


def recept(key: str, call: dict) -> dict | None:
    """Hoe `key` ontstond, als JSON-recept; None als deze aanroep de key niet maakte."""
    naam = call.get("name")
    known = store.meta(key)
    if naam == TOOL_RUN_ANALYSIS:
        # Zonder script: modelcode wordt in deze stap niet bewaard (#472).
        return {"afgeleid_van": known.afgeleid_van if known else None, "stap": STAP_ANALYSE, "herlaadbaar": False}
    if naam == TOOL_KOPPEL_DATA:
        # Een koppeling rust op twee tabellen (#988): ze komt niet vanzelf terug, haar stap zegt welke het was.
        return {
            "afgeleid_van": known.afgeleid_van if known else None,
            "stap": (known.stap if known else None) or STAP_KOPPELING,
            "herlaadbaar": False,
        }
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
    if (
        known is not None
        and known.bron == "cbs"
        and (update := known.bijgewerkt_op or catalogus_laatste_update(known.dataset))
    ):
        tekst += f" (CBS-tabel laatst bijgewerkt op {update})"
    return tekst


def _herlaad(key: str, recept: dict, recept_van: Receptbron, stappen: int, username: str | None) -> Herlaadresultaat:
    if store.get(key) is not None:
        return _terug(key, username)
    if stappen > _MAX_STAPPEN or not isinstance(recept, dict):
        return _niet(key, "onbruikbaar recept", f"Het recept voor {_de_data_van(key)} is onbruikbaar.")
    if "laad" in recept:
        return _laad(key, recept["laad"], username)
    if recept.get("tool") == TOOL_QUERY_DATA and recept.get("herlaadbaar", True):
        return _selecteer(key, recept, recept_van, stappen, username)
    if recept.get("tool") == TOOL_GET_MAAT:
        return _hermaat(key, recept, username)
    return _niet(key, "stap zonder herlaadrecept", _onherhaalbaar(key, recept))


def onherhaalbaar(key: str, recept: dict) -> str:
    """Wat de gebruiker leest bij een stap die niet opnieuw wordt uitgevoerd, zonder key (#1063, #1240)."""
    return _onherhaalbaar(key, recept)


def _onherhaalbaar(key: str, recept: dict) -> str:
    """De stap en de dataset waarop ze rekende (`afgeleid_van`, anders de key zelf); nooit de key (#1063)."""
    stap = recept.get("stap")
    stap = stap if isinstance(stap, str) and stap else "eerdere stap"
    ouder = recept.get("afgeleid_van")
    data = _de_data_van(ouder if isinstance(ouder, str) and ouder else key)
    return f"Stap '{stap}' op {data} wordt niet automatisch opnieuw uitgevoerd."


def _niet(key: str, soort: str, melding: str, bronfout: bool = False) -> Herlaadresultaat:
    """Een mislukt herladen: de melding is voor de gebruiker en zonder key, de log houdt de key (#1063)."""
    logger.warning("herladen %s mislukt: %s", key, soort)
    return Herlaadresultaat(key, gelukt=False, melding=melding, bronfout=bronfout)


def _laad(key: str, laad: object, username: str | None) -> Herlaadresultaat:
    tool, args = laad if isinstance(laad, list | tuple) and len(laad) == 2 else (None, None)
    if not isinstance(tool, str) or tool not in _LADERS or not isinstance(args, dict):
        return _niet(key, "onbekende laadstap", f"Het recept voor {_de_data_van(key)} noemt geen bekende laadstap.")
    functie, bron = _LADERS[tool]
    if not beschikbaarheid.tool(tool):
        melding = f"{bron} geeft in deze omgeving geen cijfers, dus {_de_data(args)} komt niet terug."
        return Herlaadresultaat(key, gelukt=False, bronfout=True, melding=melding)
    try:
        uitkomst = functie(**args)
    except Exception as e:  # een recept met argumenten die de tool niet (meer) kent
        logger.warning("herladen %s via %s mislukt: %s", key, tool, foutkenmerk(e))
        logger.debug("herladen %s via %s mislukt: %r", key, tool, e)
        uitkomst = ""
    if store.get(key) is None:
        if is_scopeweigering(uitkomst):
            # De app weigerde (catalogus, scope), de bron niet: geen "<bron> gaf de data niet", geen 502 (#1126).
            return _niet(key, "buiten catalogus of scope", _scopemelding(uitkomst))
        reden = _reden(uitkomst) or "geen data."
        melding = f"{bron} gaf {_de_data(args)} niet opnieuw: {reden}"
        return Herlaadresultaat(key, gelukt=False, bronfout=True, melding=melding)
    markeer(username, key)
    return _terug(key, username)


def apart(key: str, laad: object) -> Apart | Herlaadresultaat:
    """Voer het laadrecept van `key` opnieuw uit zonder de store te raken (#1240).

    Dezelfde tool, scopegrens en meldingen als `herlaad`, maar de nieuwe tabel komt terug in plaats van in de store:
    daar blijft de data van het eerdere antwoord staan, voor iedereen die erop rust. Mislukt het, dan een
    Herlaadresultaat met de melding voor de gebruiker, zonder key (#1063).
    """
    tool, args = laad if isinstance(laad, list | tuple) and len(laad) == 2 else (None, None)
    if not isinstance(tool, str) or tool not in _APART or not isinstance(args, dict):
        return _niet(key, "geen herhaalbare laadstap", f"Het recept voor {_de_data_van(key)} is niet te herhalen.")
    bron = _LADERS[tool][1]
    if not beschikbaarheid.tool(tool):
        melding = f"{bron} geeft in deze omgeving geen cijfers, dus {_de_data(args)} komt niet terug."
        return Herlaadresultaat(key, gelukt=False, bronfout=True, melding=melding)
    opgevangen: dict[str, tuple[pd.DataFrame, store.KeyMeta]] = {}

    def opvang(k: str, df: "pd.DataFrame", meta: store.KeyMeta) -> None:
        opgevangen[k] = (df, meta)

    try:
        uitkomst = _APART[tool](**args, bewaar=opvang)
    except Exception as e:  # een recept met argumenten die de tool niet (meer) kent
        logger.warning("herhalen %s via %s mislukt: %s", key, tool, foutkenmerk(e))
        logger.debug("herhalen %s via %s mislukt: %r", key, tool, e)
        uitkomst = ""
    # Een recept van vóór de canonieke digest (#342) heeft een oude key; de lader geeft de tabel onder de nieuwe.
    gevangen = opgevangen.get(key) or (next(iter(opgevangen.values())) if len(opgevangen) == 1 else None)
    if gevangen is None:
        if is_scopeweigering(uitkomst):
            return _niet(key, "buiten catalogus of scope", _scopemelding(uitkomst))
        reden = _reden(uitkomst) or "geen data."
        return _niet(key, "bron gaf niets", f"{bron} gaf {_de_data(args)} niet opnieuw: {reden}", bronfout=True)
    return Apart(key, *gevangen)


def _scopemelding(weigering: str) -> str:
    """Wat de gebruiker leest bij een weigering van scope_blokkade: het scopeprofiel zegt het zelf, een ID dat de
    catalogus niet meer kent, krijgt een vaste zin (zonder het kale ID, #1053)."""
    return _reden(weigering) if weigering.startswith("{") else _NIET_MEER_IN_CATALOGUS


def _de_data(args: dict) -> str:
    """De data in de melding van een laadstap: "de data van '<titel>'", zonder bekende dataset alleen "de data".

    Sinds #1050 leest de gebruiker deze melding in de report_error: hij kent de dataset aan haar catalogustitel, niet
    aan de interne key `duo:p01hoinges:0` of het kale ID (#1053). De key blijft intern, in `Herlaadresultaat.key`.
    """
    dataset_id = args.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        return "de data"
    titel = bron_titel(dataset_id, vo_context=bool(args.get("vo_context")))
    return "de data" if titel == dataset_id else f"de data van '{titel}'"


def _de_data_van(key: str) -> str:
    """Als `_de_data`, voor een key: de store kent haar ouder na een herstart niet meer, dus de dataset komt uit de
    eerste twee delen van de key (`duo:p01hoinges` uit `duo:p01hoinges:0:analyse:1`, #1063)."""
    delen = key.split(":")
    return _de_data({"dataset_id": ":".join(delen[:2])}) if len(delen) >= 2 else "de data"


def _selecteer(key: str, recept: dict, recept_van: Receptbron, stappen: int, username: str | None) -> Herlaadresultaat:
    ouder, args = recept.get("afgeleid_van"), recept.get("args")
    if not isinstance(ouder, str) or not isinstance(args, dict):
        return _niet(key, "onbruikbaar recept", f"Het recept voor {_de_data_van(key)} is onbruikbaar.")
    if store.get(ouder) is None:
        ouder_recept = recept_van(ouder)
        if ouder_recept is None:
            logger.warning("herladen %s mislukt: ouder %s is niet bewaard", key, ouder)
            melding = f"{_de_data_van(key)} rust op een eerdere stap die niet is bewaard."
            return Herlaadresultaat(key, gelukt=False, melding=melding[0].upper() + melding[1:])
        eerst = _herlaad(ouder, ouder_recept, recept_van, stappen + 1, username)
        if not eerst.gelukt:
            logger.warning("herladen %s mislukt: ouder %s kwam niet terug", key, ouder)
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
        return _niet(key, "selectie gaf niets", f"Stap '{stap}' gaf {_de_data_van(key)} niet opnieuw: {reden}")
    # Ook op een ouder die live werd geladen: die is van ná het antwoord waar deze selectie onder stond.
    markeer(username, key)
    return _terug(key, username)


def _hermaat(key: str, recept: dict, username: str | None) -> Herlaadresultaat:
    """Een vaste maat (#188) opnieuw: get_maat laadt de bron en selecteert zelf, met dezelfde key als uitkomst."""
    args = recept.get("args")
    if not isinstance(args, dict):
        return _niet(key, "onbruikbaar recept", f"Het recept voor {_de_data_van(key)} is onbruikbaar.")
    try:
        # Code herlaadt hier een stap die er al was: ook een interne vorm van de regel "Andere definities" (#1256).
        with maten.codestap():
            uitkomst = get_maat(**args)
    except Exception as e:  # argumenten die get_maat niet (meer) aanneemt
        logger.warning("herladen %s via get_maat mislukt: %s", key, foutkenmerk(e))
        logger.debug("herladen %s via get_maat mislukt: %r", key, e)
        uitkomst = ""
    if store.get(key) is None:
        stap = recept.get("stap") or "vaste maat"
        melding = f"Stap '{stap}' gaf {_de_data_van(key)} niet opnieuw: {_reden(uitkomst) or 'geen data.'}"
        return _niet(key, "vaste maat gaf niets", melding, bronfout=True)
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
    # Een toolmelding kan een key noemen ("Geen data gevonden voor 'duo:x:0'"); de gebruiker leest de data (#1063).
    zin = _KEY_IN_TEKST.sub("de data", zin)
    if zin and not zin.endswith("."):
        zin += "."
    return zin[:_MAX_REDEN]
