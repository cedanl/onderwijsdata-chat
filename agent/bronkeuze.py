"""Een vaste regel onder het antwoord met de gekozen bron, haar definitie en het alternatief, uit code (#667).

"Hoeveel leerlingen stromen van het vmbo door naar het mbo?" kreeg in de ene run CBS 85569NED en in de andere DUO
"Instromende mbo-studenten": twee juiste getallen met een andere definitie. Nu kiest het recept van `get_maat` de
bron (#191: code beslist, het model formuleert), en eindigt het antwoord met één regel "**Bron en definitie:** …":
de gekozen bron met haar teldefinitie en de andere bron met de hare. Alles uit het toolresultaat, niets uit de
modeltekst; een regel die het model zelf schreef (bijvoorbeeld overgenomen uit een eerdere beurt) vervalt, zodat de
regel één keer onder het antwoord staat.
"""

import json
import re

from tools.schemas import TOOL_GET_MAAT

from .grounding import checked_numbers

KOP = "**Bron en definitie:**"
_EIGEN_REGEL = re.compile(rf"^[ \t]*{re.escape(KOP)}.*(?:\n|\Z)", re.MULTILINE)


def _json(result: str) -> dict:
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tekst(waarde: object) -> str:
    return waarde.strip() if isinstance(waarde, str) else ""


def _regel(parsed: dict) -> str | None:
    """De regel bij één get_maat-resultaat met een alternatieve bron; None als een onderdeel ontbreekt."""
    alternatief = parsed.get("alternatieve_bron")
    recept = parsed.get("recept")
    if not isinstance(alternatief, dict) or not isinstance(recept, dict):
        return None
    bron = f"{_tekst(recept.get('bron')).upper()} {_tekst(recept.get('dataset'))}".strip()
    definitie = _tekst(parsed.get("teldefinitie"))
    naam, dataset = _tekst(alternatief.get("naam")), _tekst(alternatief.get("dataset"))
    bestand, andere = _tekst(alternatief.get("bestand")), _tekst(alternatief.get("definitie"))
    if not all((bron, definitie, naam, dataset, bestand, andere)):
        return None
    regel = (
        f"{KOP} dit cijfer komt uit {bron} en telt {definitie}. Een andere bron, {naam} ({dataset}, {bestand}), "
        f"telt {andere}. Door die andere definitie verschillen de cijfers van beide bronnen."
    )
    # Een getal hoort alleen in de modeltekst, waar de controle het toetst: deze regel noemt er geen.
    return None if checked_numbers(regel) else regel


def bronregel(steps: list[tuple[str, str]]) -> str | None:
    """De regel(s) voor de get_maat-stappen van deze beurt met een alternatieve bron; None als er geen is."""
    regels = [regel for tool, result in steps if tool == TOOL_GET_MAAT and (regel := _regel(_json(result)))]
    return "\n\n".join(dict.fromkeys(regels)) or None


def met_bronregel(tekst: str, steps: list[tuple[str, str]]) -> str:
    """Het antwoord met de regel eronder, één keer; een regel van het model zelf vervalt."""
    regel = bronregel(steps)
    if not tekst.strip() or (regel is None and KOP not in tekst):
        return tekst
    tekst = _EIGEN_REGEL.sub("", tekst).rstrip()
    return f"{tekst}\n\n{regel}" if regel else tekst
