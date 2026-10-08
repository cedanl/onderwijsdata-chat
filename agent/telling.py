"""Wat de getallen tellen, wanneer ze een ondergrens zijn en hoe ze afgerond zijn, uit code (#321, #352).

DUO-bestanden tellen personen of inschrijvingen en onderdrukken kleine aantallen
als -1. Beide staan in de metadata van de selectie, dus de app zet ze zelf onder
het antwoord. Het model formuleerde ze eerder zelf en kreeg er vals alarm van een
regex achteraf (#239): elke parafrase van de DUO-tekst gold als een fout.
"""

import json
import re

from core.sentinels import BETEKENIS
from tools import cbs_afronding, duo, store
from tools.catalog import catalogus_titel

from .claimbinding import betekenis, kenmerken, kies, zin_van
from .dimensielabels import selectie_regels
from .grounding import bewijs_getallen, checked_numbers
from .meetwaarden import meetwaarden
from .selectie import data_keys

_KOP = "**Telling**"
# De eigen Definities-paragraaf van het model, tot de volgende vetgedrukte kop of het einde.
_EIGEN_DEFINITIES = re.compile(r"\n*\*\*Definities\*\*\n.*?(?=\n\n\*\*[^*\n]+\*\*|\Z)", re.DOTALL)


def _ondergrens(key: str) -> bool:
    """Valt er een onderdrukte cel in de selectie achter deze key? Een hele resource is geen selectie (#179)."""
    known = store.meta(key)
    return bool(known and known.afgeleid_van and duo.onderdrukt(key))


def _bovengrens(key: str) -> bool:
    known = store.meta(key)
    return bool(known and known.afgeleid_van and known.vier_cellen)


def _stapkeys(result: str) -> list[str]:
    """De keys waarop één toolstap rust: zijn data_key, wat run_analysis las, of de bron van een KPI."""
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    kandidaten = [parsed.get("data_key"), *(parsed.get("gelezen") or [])]
    if isinstance(bron := parsed.get("bron"), dict):
        kandidaten.append(bron.get("data_key"))
    return [k for k in kandidaten if isinstance(k, str)]


def _grenzen(keys: list[str]) -> tuple[set[str], set[str]]:
    """De datasets waarvan de selectie hier een ondergrens, en die waarvan ze een bovengrens geeft."""
    onder, boven = set(), set()
    for key in keys:
        known = store.meta(key)
        if known is None or known.bron != "duo":
            continue
        if _ondergrens(key):
            onder.add(known.dataset)
        if _bovengrens(key):
            boven.add(known.dataset)
    return onder, boven


def _antwoordgrenzen(tool_results: list[str], tekst: str) -> tuple[set[str], set[str]] | None:
    """De grenzen van de selecties waarop de getallen in `tekst` rusten (#414).

    Een getal rust op de toolstappen waarin het staat, net als bij de citaties (#365).
    Wijst de zin één selectie aan (instelling, jaar, maat), dan gelden haar grenzen: een
    exacte andere selectie met hetzelfde getal maakt de claim niet exact (CH-07). Wijst
    de zin niets aan en staat het getal ook in een selectie zonder grens, dan is het daar
    exact: een bredere verkenning met onderdrukte cellen maakt het geen ondergrens.
    None als geen getal in de tekst op een selectie rust.
    """
    stappen = [(keys, bewijs_getallen(r), meetwaarden(r)) for r in tool_results if (keys := _stapkeys(r))]
    onder: set[str] = set()
    boven: set[str] = set()
    gedragen = False
    for geschreven, cijfers in checked_numbers(tekst):
        kandidaten = [
            (tuple(keys), w)
            for keys, getallen, ws in stappen
            if cijfers in getallen
            for w in [w for w in ws if cijfers in w.cijfers] or [None]
        ]
        if not kandidaten:
            continue
        gedragen = True
        gekozen = kies(
            kandidaten,
            lambda k: (k[0], betekenis(k[1]) if k[1] else None),
            lambda k: kenmerken(k[1]) if k[1] else (),
            zin_van(tekst, geschreven),
        )
        if gekozen:
            o, b = _grenzen(list(gekozen[0]))
            onder |= o
            boven |= b
            continue
        dragers = [_grenzen(list(keys)) for keys in dict.fromkeys(k for k, _ in kandidaten)]
        if all(o for o, _ in dragers):
            onder.update(*(o for o, _ in dragers))
        if all(b for _, b in dragers):
            boven.update(*(b for _, b in dragers))
    return (onder, boven) if gedragen else None


def _naam(dataset: str) -> str:
    titel = catalogus_titel(dataset)
    return dataset if titel == dataset else f"{dataset} ({titel})"


def _teldefinities(tool_results: list[str]) -> dict[str, str]:
    definities: dict[str, str] = {}
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known is not None and known.bron == "duo" and known.teldefinitie:
            definities.setdefault(known.dataset, known.teldefinitie)
    return definities


def telling_blok(tool_results: list[str], tekst: str = "") -> str:
    """Het blok onder het antwoord; leeg als de beurt geen teldefinitie, ondergrens, afronding of CBS-selectie raakte.

    Onder- en bovengrens horen bij de selecties waarop de getallen in `tekst` rusten, niet
    bij elke verkenning van de beurt (#414). Rust er geen getal op een selectie, dan gelden
    alle selecties van de beurt: een grens verzwijgen is erger dan er een te veel noemen.
    """
    definities = _teldefinities(tool_results)
    afgerond: dict[str, str] = {}
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known is not None and (noot := cbs_afronding.van_key(key)):
            afgerond.setdefault(known.dataset, noot)
    grenzen = _antwoordgrenzen(tool_results, tekst)
    if grenzen is None:
        grenzen = _grenzen([k for r in tool_results for k in _stapkeys(r)])
    ondergrens, bovengrens = (sorted(g) for g in grenzen)
    regels = [f"- {_naam(dataset)}: {definitie}" for dataset, definitie in definities.items()]
    regels += [f"- {_naam(dataset)}: {noot}" for dataset, noot in afgerond.items()]
    regels += selectie_regels(tool_results)
    if ondergrens:
        regels.append(
            f"- Ondergrens: in de gekozen selectie van {', '.join(ondergrens)} zijn cellen met -1 uitgesloten "
            f"({BETEKENIS}); de totalen zijn daardoor een ondergrens."
        )
    if bovengrens:
        regels.append(
            f"- Bovengrens: in de gekozen selectie van {', '.join(bovengrens)} zijn kleine aantallen (1 t/m 4) als 4 "
            "gepubliceerd; de totalen zijn daardoor een bovengrens."
        )
    return f"{_KOP}\n" + "\n".join(regels) if regels else ""


def met_telling(tekst: str, tool_results: list[str]) -> str:
    """Het antwoord met het telling-blok eronder.

    Met een teldefinitie uit de bron vervalt de eigen Definities-paragraaf van het model:
    één definitieblok, uit de bron. Bij TU Delft spraken ze elkaar tegen (#402).
    """
    blok = telling_blok(tool_results, tekst)
    if not blok or not tekst.strip():
        return tekst
    if _teldefinities(tool_results):
        tekst = _EIGEN_DEFINITIES.sub("", tekst)
    return f"{tekst.rstrip()}\n\n{blok}"
