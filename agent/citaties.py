"""Uit welke cel komt een getal in het antwoord? (#365, #415)

Elk gecontroleerd getal in een dataantwoord krijgt een citatie, zodat hetzelfde antwoord
altijd hetzelfde aantal heeft. Een getal dat als meetwaarde in een toolstap staat, linkt
naar de eerste zo'n stap: bron, maat, eenheid en de rij waarin het staat, in woorden. Staat
het alleen als code, rijtelling of stuk van een key in de uitvoer, of nergens, dan zegt de
citatie dat de herkomst niet is vastgesteld. Het model schrijft zelf geen markering.
"""

from tools import LABELS, store
from tools.catalog import catalogus_titel
from tools.kolomlabel import kolomlabel

from .grounding import checked_numbers
from .meetwaarden import Meetwaarde, eenheden, meetwaarden
from .selectie import data_keys, laadkey

_SCHEIDING = " · "


def _bron(data_key: str | None, tool: str) -> str:
    """De bron in woorden: DUO · <catalogustitel>; zonder bekende key het label van de stap."""
    known = store.meta(laadkey(data_key)) if data_key else None
    if known is None:
        return LABELS.get(tool, tool)
    return f"{known.bron.upper()}{_SCHEIDING}{catalogus_titel(known.dataset)}"


def _citatie(geschreven: str, stap: int, tool: str, waarde: Meetwaarde, eenheid: dict[str, str]) -> dict:
    return {
        "getal": geschreven,
        "vastgesteld": True,
        "stap": stap,
        "tool": tool,
        "label": LABELS.get(tool, tool),
        "bron": _bron(waarde.data_key, tool),
        "maat": kolomlabel(waarde.maat),
        **({"eenheid": e} if (e := waarde.eenheid or eenheid.get(waarde.maat)) else {}),
        **({"selectie": _SCHEIDING.join(waarde.selectie)} if waarde.selectie else {}),
        **({"data_key": waarde.data_key} if waarde.data_key else {}),
    }


def citaties(tekst: str, steps: list[tuple[str, str]]) -> list[dict]:
    """Per gecontroleerd getal in `tekst` een citatie; leeg als de beurt geen data las."""
    results = [result for _, result in steps]
    waarden = [(stap, tool, meetwaarden(result, tool)) for stap, (tool, result) in enumerate(steps, 1)]
    if not data_keys(results) and not any(w for _, _, w in waarden):
        return []
    eenheid = {k: v for result in results for k, v in eenheden(result).items()}
    gevonden: dict[str, dict] = {}
    for geschreven, cijfers in checked_numbers(tekst):
        if geschreven in gevonden:
            continue
        bron = next(((s, t, w) for s, t, ws in waarden for w in ws if cijfers in w.cijfers), None)
        gevonden[geschreven] = (
            _citatie(geschreven, *bron, eenheid) if bron else {"getal": geschreven, "vastgesteld": False}
        )
    return list(gevonden.values())
