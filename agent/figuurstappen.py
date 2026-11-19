"""De figuren die het gesprek maakte, als stap die de server opnieuw kan uitvoeren (#993).

Een figuur in de chat komt van een tool: `create_plot`, `create_choropleth_map` of een script van `run_analysis`. Het
rapport neemt een figuur uit het gesprek over door die stap opnieuw te draaien op de server
(`agent.report_figuren`), niet door de figuur-JSON van de client te lezen: die is geen bewijs. Daarom legt de server
bij elke figuur die een tool maakte de stap vast: de tool, haar argumenten, de titel van de figuur die de server zelf
maakte en de keys waar ze op rust.

**Een stap** is `{id, tool, arguments, titel, keys}`. `id` volgt uit tool en argumenten: dezelfde stap heeft na
heropenen dezelfde id, en twee keer dezelfde stap is één figuur. `keys` begint met de key waar de figuur thuishoort:
de `data_key` van de aanroep, anders de key die de stap maakte; daarna wat het script las (`store_get`). Een stap
zonder key (rijen die het model zelf meegaf in `data`) legt de server niet vast: daar is geen data om op te herhalen.

Zoals lineage en rekenbewijs (`session_data`) gaat wat sinds de vorige afgeronde beurt bijkwam in de rij van de
volgende in `beurtbewijs`, zodat een heropend gesprek dezelfde figuren kent.
"""

import hashlib
import json
import re

from tools import fouten, scriptcontrole, store
from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP, TOOL_CREATE_PLOT, TOOL_RUN_ANALYSIS

from .selectie import stapkeys

FIGUURTOOLS = frozenset({TOOL_CREATE_PLOT, TOOL_CREATE_CHOROPLETH_MAP, TOOL_RUN_ANALYSIS})

# Zoveel figuurstappen kent een sessie, live en na heropenen; de oudste vallen eerst af. Een stap draagt het script van
# run_analysis, dat in het rekenbewijs al bewaard wordt.
_MAX_STAPPEN = 30
MAX_TITEL = 200

_SESSIE = "figuurstappen"
_NIEUW = "_nieuwe_figuurstappen"

_TAG = re.compile(r"<[^>]*>")


def figuur_id(tool: str, arguments: dict) -> str:
    """De id van een stap: sha256 over tool en argumenten, kort. Dezelfde stap geeft dezelfde id, ook na heropenen."""
    tekst = json.dumps({"tool": tool, "arguments": arguments}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()[:12]


def titel(figure) -> str:
    """De titel van de figuur die de server maakte, als platte tekst op één regel; leeg als ze er geen heeft."""
    tekst = getattr(getattr(getattr(figure, "layout", None), "title", None), "text", None)
    if not isinstance(tekst, str):
        return ""
    tekst = " ".join(_TAG.sub(" ", tekst).split())
    return tekst if len(tekst) <= MAX_TITEL else tekst[: MAX_TITEL - 1] + "…"


def leg_vast(session: dict, tool: str, arguments: dict | None, result: str, figure) -> None:
    """Leg de stap vast die deze figuur maakte; niets zonder figuur, bij een andere tool, of zonder key."""
    if figure is None or tool not in FIGUURTOOLS or not isinstance(arguments, dict) or "data" in arguments:
        return
    if fouten.code(result) is not None:
        return
    if not (keys := _keys(tool, arguments, result)):
        return
    stap = {
        "id": figuur_id(tool, arguments),
        "tool": tool,
        "arguments": arguments,
        "titel": titel(figure),
        "keys": keys,
    }
    voeg_toe(session, [stap])
    voeg_toe(session, [stap], sleutel=_NIEUW)


def _keys(tool: str, arguments: dict, result: str) -> list[str]:
    """De data_key van de aanroep, de key die de stap maakte, en wat het script las; elk één keer."""
    data_key = arguments.get("data_key")
    keys = [store.canoniek(data_key)] if isinstance(data_key, str) and data_key else []
    keys += stapkeys(result)
    if tool == TOOL_RUN_ANALYSIS and isinstance(code := arguments.get("code"), str):
        keys += _scriptkeys(code, data_key if isinstance(data_key, str) else None)
    return list(dict.fromkeys(k for k in keys if k))


def _scriptkeys(code: str, data_key: str | None) -> list[str]:
    """De keys die het script letterlijk met store_get leest; het script draaide al, dus de controle slaagt."""
    try:
        return [store.canoniek(k) for k in scriptcontrole.ontleed(code, data_key).keys]
    except (scriptcontrole.Geweigerd, SyntaxError):
        return []


def voeg_toe(session: dict, stappen: list[dict], sleutel: str = _SESSIE) -> None:
    """Zet stappen achteraan; een stap met een id die er al is, blijft op haar eerste plek. Hoogstens `_MAX_STAPPEN`."""
    lijst = session.setdefault(sleutel, [])
    bekend = {s["id"] for s in lijst}
    for stap in stappen:
        if isinstance(stap, dict) and isinstance(stap.get("id"), str) and stap["id"] not in bekend:
            lijst.append(stap)
            bekend.add(stap["id"])
    lijst[:] = begrens(lijst)


def begrens(stappen: list[dict]) -> list[dict]:
    return stappen[-_MAX_STAPPEN:]


def samen(oud: list[dict], nieuw: list[dict]) -> list[dict]:
    """Twee lijsten stappen als één: eerst de oude, dan de nieuwe die er nog niet in staan; opnieuw samenvoegen
    verandert niets."""
    bekend = {s.get("id") for s in oud}
    return begrens([*oud, *(s for s in nieuw if s.get("id") not in bekend)])


def neem_nieuwe(session: dict) -> list[dict]:
    """De stappen sinds de vorige afgeronde beurt, voor haar rij in `beurtbewijs`; daarna begint de telling opnieuw."""
    return session.pop(_NIEUW, None) or []


def stappen(session: dict) -> list[dict]:
    """De figuurstappen van dit gesprek, in de volgorde waarin de figuren ontstonden."""
    return list(session.get(_SESSIE) or [])
