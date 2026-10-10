"""Wat de getallen tellen, wanneer ze een ondergrens zijn en hoe ze afgerond zijn, uit code (#321, #352).

DUO-bestanden tellen personen of inschrijvingen en onderdrukken kleine aantallen
als -1. Beide staan in de metadata van de selectie, dus de app zet ze zelf onder
het antwoord. Het model formuleerde ze eerder zelf en kreeg er vals alarm van een
regex achteraf (#239): elke parafrase van de DUO-tekst gold als een fout.
"""

import re

from core.sentinels import BETEKENIS
from tools import cbs_afronding, duo, duo_bestandskeuze, periode, store
from tools.catalog import bron_naam

from .binding import zin_op
from .claimbinding import betekenis, kenmerken, kies
from .dimensielabels import selectie_regels
from .grounding import bewijs_getallen, getallen_met_positie
from .meetwaarden import Meetwaarde, meetwaarden
from .selectie import data_keys, laadkey, stapkeys

_KOP = "**Telling**"
# De eigen Definities-paragraaf van het model, tot de volgende vetgedrukte kop of het einde.
_EIGEN_DEFINITIES = re.compile(r"\n*\*\*Definities\*\*\n.*?(?=\n\n\*\*[^*\n]+\*\*|\Z)", re.DOTALL)


def _ondergrens(key: str) -> bool:
    """Valt er een onderdrukte cel in de selectie achter deze key? Een hele resource is geen selectie (#179)."""
    known = store.meta(key)
    return bool(known and known.afgeleid_van and duo.onderdrukt(key))


def _groepstotaal_exact(waarde: Meetwaarde | None) -> bool:
    """Is dit getal een groepstotaal zonder onderdrukte cel (CH-07)?

    De selectie per geslacht heeft een -1 bij MAN; het totaal voor VROUW is dan toch exact.
    Alleen bij groepstotalen van query_data: bij losse rijen kan een getal in de tekst ook
    een eigen som zijn die toevallig gelijk is aan één cel, en dan geldt de selectie.
    """
    if waarde is None or waarde.rij is None or waarde.data_key is None:
        return False
    return duo.onderdrukt_in_groep(waarde.data_key, waarde.rij, waarde.maat) == 0


def _bovengrens(key: str) -> bool:
    known = store.meta(key)
    return bool(known and known.afgeleid_van and known.vier_cellen)


# (dataset, resource): het bestand bepaalt welke cellen onderdrukt zijn (#325).
_Bestand = tuple[str, str | int | None]


def _grenzen(keys: list[str]) -> tuple[set[_Bestand], set[_Bestand]]:
    """De bestanden waarvan de selectie hier een ondergrens, en die waarvan ze een bovengrens geeft."""
    onder, boven = set(), set()
    for key in keys:
        known = store.meta(key)
        if known is None or known.bron != "duo":
            continue
        if _ondergrens(key):
            onder.add((known.dataset, known.resource))
        if _bovengrens(key):
            boven.add((known.dataset, known.resource))
    return onder, boven


def _antwoordgrenzen(tool_results: list[str], tekst: str) -> tuple[set[_Bestand], set[_Bestand]] | None:
    """De grenzen van de selecties waarop de getallen in `tekst` rusten (#414).

    Een getal rust op de toolstappen waarin het staat, net als bij de citaties (#365).
    Wijst de zin één selectie aan (instelling, jaar, maat), dan gelden haar grenzen: een
    exacte andere selectie met hetzelfde getal maakt de claim niet exact (CH-07). Wijst
    de zin niets aan en staat het getal ook in een selectie zonder grens, dan is het daar
    exact: een bredere verkenning met onderdrukte cellen maakt het geen ondergrens.
    None als geen getal in de tekst op een selectie rust.
    """
    stappen = [(keys, bewijs_getallen(r), meetwaarden(r)) for r in tool_results if (keys := stapkeys(r))]
    onder: set[_Bestand] = set()
    boven: set[_Bestand] = set()
    gedragen = False
    for _, cijfers, positie in getallen_met_positie(tekst):
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
            zin_op(tekst, positie),
        )
        if gekozen:
            o, b = _grenzen(list(gekozen[0]))
            onder |= set() if _groepstotaal_exact(gekozen[1]) else o
            boven |= b
            continue
        dragers = [_grenzen(list(keys)) for keys in dict.fromkeys(k for k, _ in kandidaten)]
        if all(o for o, _ in dragers):
            onder.update(*(o for o, _ in dragers))
        if all(b for _, b in dragers):
            boven.update(*(b for _, b in dragers))
    return (onder, boven) if gedragen else None


def _jaarnoten(tool_results: list[str]) -> dict[str, list[str]]:
    """Per dataset de jaarkolommen die geen schooljaar zijn, uit de geladen data (CH-41).

    Uit de laadkey: een selectie die de jaarkolom wegliet, gaat nog steeds over die jaren."""
    noten: dict[str, list[str]] = {}
    for key in data_keys(tool_results):
        bron = laadkey(key)
        known, df = store.meta(bron), store.get(bron)
        if known is not None and df is not None and (gevonden := periode.jaarnoten(df.columns)):
            noten.setdefault(known.dataset, gevonden)
    return noten


def _historienoten(tool_results: list[str]) -> dict[str, str]:
    """Per prognosebestand de noot over Historie-jaren, als een selectie ze bevat (#325, #442)."""
    noten: dict[str, str] = {}
    for key in data_keys(tool_results):
        known, df = store.meta(key), store.get(key)
        if (
            known
            and known.afgeleid_van
            and df is not None
            and (noot := duo_bestandskeuze.historienoot(known.dataset, df))
        ):
            noten.setdefault(known.dataset, noot)
    return noten


def _datasets(bestanden: set[_Bestand]) -> str:
    return ", ".join(sorted({dataset for dataset, _ in bestanden}))


def _teldefinities(tool_results: list[str]) -> dict[str, str]:
    definities: dict[str, str] = {}
    for key in data_keys(tool_results):
        known = store.meta(key)
        if known is not None and known.bron == "duo" and known.teldefinitie:
            definities.setdefault(known.dataset, known.teldefinitie)
    return definities


def telling_blok(tool_results: list[str], tekst: str = "") -> str:
    """Het blok onder het antwoord; leeg als de beurt geen teldefinitie, ondergrens, afronding, CBS-selectie,
    jaarkolom zonder schooljaar of Historie-jaren uit een prognosebestand raakte.

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
        grenzen = _grenzen([k for r in tool_results for k in stapkeys(r)])
    ondergrens, bovengrens = grenzen
    regels = [f"- {bron_naam(dataset)}: {definitie}" for dataset, definitie in definities.items()]
    regels += [f"- {bron_naam(dataset)}: {noot}" for dataset, noot in afgerond.items()]
    regels += [
        f"- {bron_naam(dataset)}: {noot}" for dataset, noten in _jaarnoten(tool_results).items() for noot in noten
    ]
    regels += [f"- {bron_naam(dataset)}: {noot}" for dataset, noot in _historienoten(tool_results).items()]
    regels += selectie_regels(tool_results)
    if ondergrens:
        regels.append(
            f"- Ondergrens: in de gekozen selectie van {_datasets(ondergrens)} zijn cellen met -1 uitgesloten "
            f"({BETEKENIS}); de totalen zijn daardoor een ondergrens."
        )
        # Een ander bestand van dezelfde dataset onderdrukt andere cellen en telt anders (#325).
        regels += [
            f"- {bron_naam(dataset)}: {noot}"
            for dataset, resource in sorted(ondergrens, key=str)
            if (noot := duo_bestandskeuze.noot(dataset, resource))
        ]
    if bovengrens:
        regels.append(
            f"- Bovengrens: in de gekozen selectie van {_datasets(bovengrens)} zijn kleine aantallen (1 t/m 4) als 4 "
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
