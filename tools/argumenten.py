"""Een argument buiten het schema als melding met de naam, niet als kale TypeError (#891).

`dispatch()` roept de handler aan met wat het model meegaf. Een argument dat de handler niet kent, gaf
"faalde (TypeError). Controleer de argumenten.": zonder de naam herhaalt het model de fout tot de tool op slot
gaat. Hier toetsen we de argumenten aan de handlersignatuur vóór de aanroep en noemen we de naam, waar hij hoort
en wat wel mag. De waarde komt nooit terug; de naam alleen als hij op een parameternaam lijkt.
"""

import inspect
import logging
from collections.abc import Callable

from . import cbs_selectie, fouten
from .schemas import TOOL_GET_CBS_DATA, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

_MAX_NAAM = 40

# Sleutels die het model naast een object-argument zet in plaats van erin: naam van het argument en zijn sleutels.
_GENESTE_SLEUTELS: dict[str, tuple[str, tuple[str, ...]]] = {
    TOOL_GET_CBS_DATA: ("selectie", cbs_selectie.SLEUTELS),
}


def _toegestaan(tool: str, handler: Callable) -> list[str]:
    """De argumenten zoals het model ze uit het schema kent; zonder schema die van de handler."""
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == tool:
            return list(schema["function"]["parameters"].get("properties", {}))
    return list(inspect.signature(handler).parameters)


def _onbekend(handler: Callable, tool_input: dict) -> list[str]:
    parameters = inspect.signature(handler).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return []
    return [naam for naam in tool_input if naam not in parameters]


def _noem(naam: object) -> str:
    return f"`{naam}`" if isinstance(naam, str) and naam.isidentifier() and len(naam) <= _MAX_NAAM else "een argument"


def onbekende_argumenten(tool: str, handler: Callable, tool_input: dict) -> str | None:
    """De melding voor argumenten die `handler` niet kent, of None als alles past."""
    if not (onbekend := _onbekend(handler, tool_input)):
        return None
    logger.warning("Tool %s kreeg %d onbekende argument(en)", tool, len(onbekend))
    geneste = _GENESTE_SLEUTELS.get(tool)
    delen = []
    for naam in onbekend:
        deel = f"{tool} kent het argument {_noem(naam)} niet"
        if geneste and naam in geneste[1]:
            deel += f"; het hoort binnen `{geneste[0]}`"
        delen.append(deel + ".")
    toegestaan = ", ".join(_toegestaan(tool, handler))
    return fouten.melding(fouten.Fout.TOOLFOUT, f"{' '.join(delen)} Toegestane argumenten: {toegestaan}.")
