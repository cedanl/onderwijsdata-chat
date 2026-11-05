"""Een regiovergelijking van mbo-instellingen via hun onderwijslocaties, in code (#744).

DUO kent studentaantallen en een adres per instelling (BRIN), met de plaats van de hoofdvestiging. Een vergelijking van
de instellingen "in Doetinchem" liet zo Zone.college (31JC, hoofdvestiging Lochem) weg, dat er 22 opleidingen geeft.

Filtert `query_data` een mbo-bestand op de plaats, de gemeente, de provincie of de arbeidsmarktregio van de instelling,
en blijft het resultaat per instelling, dan neemt het hier ook de instellingen mee met een onderwijslocatie in dat
gebied. Een totaal over de instellingen heen blijft bij de hoofdvestiging: anders telde een instelling met één locatie in
Gelderland met al haar studenten mee (Gelderland 2025: 53.761 werd 104.040). Een lezing zegt dan hoeveel instellingen er
niet in zitten (`niet_in_totaal`). Het niveau volgt uit de kolom van het filter (`KOLOMMEN`), het gebied uit zijn
waarden; het model kiest niets. Een vaste regel zegt welke instellingen alleen zo meedoen en dat hun aantallen per
instelling gelden, niet per locatie (`regels`); hij reist mee op de selectie (`KeyMeta.nevenlocaties`) naar het
Telling-blok onder het antwoord, zoals de fusieregel van #728.

De bronnen:
- het aanbod per onderwijslocatie, met de plaats en de aanbieder: DUO's dagelijkse export van RIO,
  `mbo_opleidingsaanbod`. RIO zelf kan niet op plaats filteren (13.655 locaties, alleen per pagina van 100).
- de aanbieders per instelling uit RIO (`riodata.onderwijsaanbieders`): zo komt een locatie bij het BRIN.
- de gemeente en provincie van een woonplaats uit CBS (`data/woonplaatsen.py`), de arbeidsmarktregio van die gemeente
  uit de CBS-indeling van `data/arbeidsmarktregio.py`. Een woonplaatsnaam in meer gemeenten
  (Velp) krijgt geen gemeente: de locatie telt dan alleen op plaatsniveau, de code raadt niet.

Beide bronnen staan een dag in de cache (`core.actualiteit.Lading`). Een fout komt niet in de cache; een storing geeft
geen extra instellingen, geen regel en een WARNING, en breekt het antwoord niet.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
from riodata import duo, onderwijsaanbieders

from core import actualiteit
from data import arbeidsmarktregio, woonplaatsen

from . import instelling, relaties
from .kaartlocaties import sleutel

logger = logging.getLogger(__name__)

# De kolom van het filter bepaalt het niveau. Deze kolommen staan alleen in DUO's mbo-bestanden; PROVINCIE INSTELLING
# en ARBEIDSMARKTREGIO INSTELLING zet de app erbij waar het bestand ze mist (tools/instellingsprovincie.py).
KOLOMMEN = {
    "PLAATSNAAM INSTELLING": "plaats",
    "GEMEENTE INSTELLING": "gemeente",
    "GEMEENTENUMMER INSTELLING": "gemeente",
    "PROVINCIE INSTELLING": "provincie",
    "ARBEIDSMARKTREGIO INSTELLING": "arbeidsmarktregio",
}
CODEKOLOM = "INSTELLINGSCODE"
AANBOD = ("mbo_opleidingsaanbod", 0)
# Zoveel RIO-aanroepen tegelijk, zoals tools/rio_instelling.py.
_PARALLEL = 8
_TOEVOEGING = re.compile(r"\s*\([^)]*\)\s*$")  # 'hengelo (o)' → 'hengelo'


@dataclass(frozen=True)
class Nevenlocatie:
    """Een instelling die alleen via een onderwijslocatie in het gebied in een selectie kwam."""

    code: str
    naam: str
    hoofdvestiging: str  # de waarde van de regiokolom bij de instelling, op het niveau van het filter
    kolom: str  # de gefilterde kolom: de snippet herhaalt het filter
    gebied: str  # "plaats Doetinchem", "provincie Gelderland of Overijssel"


# --- de gebieden: van een filterwaarde naar een toets op de plaats van een locatie ---


@lru_cache(maxsize=1)
def _woonplaatsindex() -> dict[str, tuple[str, list[str]]]:
    """sleutel(woonplaats) → (de naam zoals CBS hem schrijft, de gemeentecodes)."""
    return {sleutel(naam): (naam, codes) for naam, codes in woonplaatsen.woonplaatsen().items()}


@lru_cache(maxsize=1)
def _gemeenteindex() -> dict[str, str]:
    """sleutel(gemeentenaam) → code; ook zonder toevoeging ('Hengelo (O.)' → 'hengelo') als dat één gemeente is."""
    index = {sleutel(g["naam"]): code for code, g in woonplaatsen.gemeenten().items()}
    kort: dict[str, list[str]] = {}
    for naam, code in index.items():
        kort.setdefault(_TOEVOEGING.sub("", naam), []).append(code)
    return {**{k: codes[0] for k, codes in kort.items() if len(codes) == 1}, **index}


def _gemeentecode(waarde) -> str | None:
    """'DOETINCHEM', 'Doetinchem', 222, '0222' of 'GM0222' → '0222'; None als onbekend."""
    code = relaties.norm_gemeente(waarde)
    if code is None:
        code = _gemeenteindex().get(sleutel(str(waarde)))
    return code if code in woonplaatsen.gemeenten() else None


def _gemeente_van_plaats(plaats: str) -> str | None:
    """De gemeente van een woonplaats; None als de naam onbekend is of in meer gemeenten ligt."""
    _, codes = _woonplaatsindex().get(sleutel(plaats), ("", []))
    return codes[0] if len(codes) == 1 else None


@lru_cache(maxsize=1)
def _regioindex() -> dict[str, str]:
    """sleutel(arbeidsmarktregio) → de naam zoals de CBS-indeling hem schrijft."""
    return {sleutel(regio): regio for regio in set(arbeidsmarktregio.gemeenten().values())}


def _arbeidsmarktregio(waarde) -> str | None:
    return _regioindex().get(sleutel(str(waarde)))


def _doelen(niveau: str, waarden: list) -> set[str]:
    """De waarden van het filter in de vorm waarin een locatie getoetst wordt."""
    if niveau == "plaats":
        return {sleutel(str(w)) for w in waarden}
    if niveau == "arbeidsmarktregio":
        return {d for w in waarden if (d := _arbeidsmarktregio(w))}
    lees = _gemeentecode if niveau == "gemeente" else relaties.norm_provincie
    return {d for w in waarden if (d := lees(w))}


def _ligt_in(niveau: str, plaats: str, doelen: set[str]) -> bool:
    if niveau == "plaats":
        return sleutel(plaats) in doelen
    if (gemeente := _gemeente_van_plaats(plaats)) is None:
        return False
    if niveau == "arbeidsmarktregio":
        return arbeidsmarktregio.gemeenten().get(gemeente) in doelen
    return (gemeente if niveau == "gemeente" else woonplaatsen.gemeenten()[gemeente]["provincie"]) in doelen


def _weergave(niveau: str, waarde) -> str:
    """De naam van een gebied zoals CBS hem schrijft ('LOCHEM' → 'Lochem', 222 → 'Doetinchem'); anders de waarde."""
    if niveau == "plaats":
        return _woonplaatsindex().get(sleutel(str(waarde)), (str(waarde), []))[0]
    if niveau == "gemeente":
        code = _gemeentecode(waarde)
        return woonplaatsen.gemeenten()[code]["naam"] if code else str(waarde)
    if niveau == "arbeidsmarktregio":
        return _arbeidsmarktregio(waarde) or str(waarde)
    code = relaties.norm_provincie(waarde)
    return relaties.PROVINCIES[code] if code else str(waarde)


# --- de bronnen, een dag in de cache ---


def _laad_aanbod() -> pd.DataFrame:
    return duo.load(*AANBOD)


@actualiteit.Lading
def _locaties() -> tuple[tuple[str, str], ...]:
    """(aanbieder, plaats) van elke onderwijslocatie met mbo-aanbod."""
    paren = _laad_aanbod()[["ONDERWIJSAANBIEDERID", "PLAATSNAAM"]].dropna().drop_duplicates()
    return tuple(sorted((str(a), str(p)) for a, p in paren.itertuples(index=False)))


@actualiteit.Lading
def _aanbieders(codes: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """Per instelling haar onderwijsaanbieders in RIO; alle codes van een bestand in één lading."""
    with ThreadPoolExecutor(_PARALLEL) as pool:
        return dict(zip(codes, (frozenset(a) for a in pool.map(onderwijsaanbieders, codes)), strict=True))


def wis_caches() -> None:
    _locaties.cache_clear()
    _aanbieders.cache_clear()


# --- de selectie ---


def _van_toepassing(df: pd.DataFrame, kolom: str, known) -> bool:
    return known is not None and known.bron == "duo" and kolom in KOLOMMEN and CODEKOLOM in df.columns


def erbij(df: pd.DataFrame, kolom: str, waarden: list, gekozen: pd.Series, known) -> frozenset[str]:
    """De instellingen die het filter op `kolom` niet kiest (`gekozen`) maar die een onderwijslocatie hebben in het
    gebied van `waarden`; leeg bij een ander bestand of een andere kolom, en bij een storing (met een WARNING)."""
    if not _van_toepassing(df, kolom, known):
        return frozenset()
    niveau = KOLOMMEN[kolom]
    codes = df[CODEKOLOM].astype(str).str.strip()
    kandidaten = set(codes[~gekozen]) - set(codes[gekozen])
    if not kandidaten or not (doelen := _doelen(niveau, waarden)):
        return frozenset()
    try:
        in_gebied = {aanbieder for aanbieder, plaats in _locaties() if _ligt_in(niveau, plaats, doelen)}
        per_code = _aanbieders(tuple(sorted(set(codes)))) if in_gebied else {}
    except Exception as e:  # een storing bij DUO of RIO breekt het antwoord niet: niemand erbij, geen regel
        logger.warning("REGIOLOCATIES_ONBEKEND kolom=%s fout=%s", kolom, type(e).__name__)
        return frozenset()
    return frozenset(c for c in kandidaten if per_code.get(c, frozenset()) & in_gebied)


def _gebied(kolom: str, waarden: list) -> str:
    """'plaats Doetinchem', 'provincie Gelderland of Overijssel'."""
    niveau = KOLOMMEN[kolom]
    return f"{niveau} " + " of ".join(dict.fromkeys(_weergave(niveau, w) for w in waarden))


def nevenlocaties(df: pd.DataFrame, kolom: str, waarden: list, codes: frozenset[str]) -> tuple[Nevenlocatie, ...]:
    """De instellingen uit `codes` die in de selectie `df` staan, met hun naam en hoofdvestiging."""
    if not codes or CODEKOLOM not in df.columns:
        return ()
    namen = instelling.namen(df, CODEKOLOM) if instelling.codekolom(df.columns) == CODEKOLOM else {}
    rijen = df.assign(_code=df[CODEKOLOM].astype(str).str.strip())
    hoofdvestiging = rijen.drop_duplicates("_code").set_index("_code")[kolom]
    gebied = _gebied(kolom, waarden)
    return tuple(
        Nevenlocatie(code, namen.get(code, code), _weergave(KOLOMMEN[kolom], hoofdvestiging[code]), kolom, gebied)
        for code in sorted(codes & set(hoofdvestiging.index))
    )


def niet_in_totaal(kolom: str, waarden: list, aantal: int) -> str:
    """De lezing bij een totaal over instellingen heen: wie alleen een onderwijslocatie in het gebied heeft, telt niet."""
    wie = (
        "1 instelling met alleen een onderwijslocatie daar telt"
        if aantal == 1
        else (f"{aantal} instellingen met alleen een onderwijslocatie daar tellen")
    )
    return (
        f"Het totaal telt de instellingen met hun hoofdvestiging in de {_gebied(kolom, waarden)}; {wie} niet mee "
        "(vergelijk per instelling om ze te zien)."
    )


def regels(locaties) -> list[str]:
    """De vaste regel per gebied, zonder opsommingsteken: wie alleen via een locatie meedoet en wat dat betekent."""
    per_gebied: dict[str, dict[str, None]] = {}
    for n in sorted(locaties, key=lambda n: (n.naam, n.code)):
        per_gebied.setdefault(n.gebied, {})[f"{n.naam} ({n.code}, hoofdvestiging {n.hoofdvestiging})"] = None
    return [
        f"Mee via een onderwijslocatie in de {gebied} (RIO): {', '.join(wie)}. Hun studentaantallen gelden per "
        "instelling, niet per locatie: ze tellen ook hun andere locaties mee."
        for gebied, wie in per_gebied.items()
    ]


def locatiecodes(locaties) -> dict[str, list[str]]:
    """Per gefilterde kolom de instellingen die er via een locatie bij kwamen, voor de snippet."""
    per_kolom: dict[str, set[str]] = {}
    for n in locaties:
        per_kolom.setdefault(n.kolom, set()).add(n.code)
    return {kolom: sorted(codes) for kolom, codes in per_kolom.items()}
