"""Wat de getallen tellen, wanneer ze een ondergrens zijn en hoe ze afgerond zijn, uit code (#321, #352).

DUO-bestanden tellen personen of inschrijvingen en onderdrukken kleine aantallen
als -1. Beide staan in de metadata van de selectie, dus de app zet ze zelf onder
het antwoord. Het model formuleerde ze eerder zelf en kreeg er vals alarm van een
regex achteraf (#239): elke parafrase van de DUO-tekst gold als een fout.
"""

from core.sentinels import BETEKENIS
from tools import cbs_afronding, duo, store
from tools.catalog import catalogus_titel

from .selectie import data_keys

_KOP = "**Telling**"


def _ondergrens(key: str) -> bool:
    """Valt er een onderdrukte cel in de selectie achter deze key? Een hele resource is geen selectie (#179)."""
    known = store.meta(key)
    return bool(known and known.afgeleid_van and duo.count_cells(duo.sentinel_cells(key)))


def _naam(dataset: str) -> str:
    titel = catalogus_titel(dataset)
    return dataset if titel == dataset else f"{dataset} ({titel})"


def telling_blok(tool_results: list[str]) -> str:
    """Het blok onder het antwoord; leeg als de beurt geen teldefinitie, ondergrens of afronding raakte."""
    definities: dict[str, str] = {}
    ondergrens: dict[str, None] = {}
    afgerond: dict[str, str] = {}
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known is not None and (noot := cbs_afronding.van_key(key)):
            afgerond.setdefault(known.dataset, noot)
        if known is None or known.bron != "duo":
            continue
        if known.teldefinitie:
            definities.setdefault(known.dataset, known.teldefinitie)
        if _ondergrens(key):
            ondergrens.setdefault(known.dataset)
    regels = [f"- {_naam(dataset)}: {definitie}" for dataset, definitie in definities.items()]
    regels += [f"- {_naam(dataset)}: {noot}" for dataset, noot in afgerond.items()]
    if ondergrens:
        regels.append(
            f"- Ondergrens: in de gekozen selectie van {', '.join(ondergrens)} zijn cellen met -1 uitgesloten "
            f"({BETEKENIS}); de totalen zijn daardoor een ondergrens."
        )
    return f"{_KOP}\n" + "\n".join(regels) if regels else ""


def met_telling(tekst: str, tool_results: list[str]) -> str:
    """Het antwoord met het telling-blok eronder."""
    blok = telling_blok(tool_results)
    if not blok or not tekst.strip():
        return tekst
    return f"{tekst.rstrip()}\n\n{blok}"
