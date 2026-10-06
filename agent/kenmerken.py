"""Staat een kenmerk bij de instelling van zijn eigen rij? (#238)

binding.py toetst getallen aan hun rij; een kenmerk zonder getal glipte erdoor.
Live (RIO Windesheim): "Windesheim (01VU) is BIJZONDER", terwijl die waarde bij
basisschool 07KT in dezelfde uitvoer hoort en het veld bij 01VU leeg is.

Hier moet een kenmerkwaarde die een zin noemt, in een rij staan van een
instelling die dezelfde zin noemt. Een instelling telt als genoemd met haar code
als los woord of met haar volledige naam; haar vestigingen (01VU00) horen erbij. Alleen RIO, en alleen kolommen met een
vaste waardenlijst (BIJZONDER, WHW, HBOS): vrije tekst, namen, codes en datums
vallen erbuiten. Staat de waarde nergens anders in de data, dan zegt deze
controle niets: dan is het geen verwisseling.
"""

import re
from collections import defaultdict

import pandas as pd

from tools import store

from .binding import segmenten
from .selectie import data_keys

_CODEKOLOM = "code"
_NAAMKOLOMMEN = ("volledigeNaam", "verkorteNaam")
# Een vaste waarde: hoofdletters met eventueel underscores (BIJZONDER, NIET_BEKOSTIGD, WHW).
_VASTE_WAARDE = re.compile(r"[A-Z][A-Z_]{2,}")

_Kenmerken = dict[str, set[str]]  # waarde → codes van de rijen waarin ze staat (per kolom)


def _woord(tekst: str, flags: int = re.IGNORECASE) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(tekst)}(?!\w)", flags)


def _kenmerkkolommen(df: pd.DataFrame) -> list[str]:
    uitgesloten = {_CODEKOLOM, *_NAAMKOLOMMEN}
    return [
        k
        for k in df.columns
        if k not in uitgesloten
        and (waarden := df[k].dropna()).map(lambda v: isinstance(v, str)).all()
        and not waarden.empty
        and waarden.map(_VASTE_WAARDE.fullmatch).all()
    ]


def _lees(df: pd.DataFrame, per_kolom: dict[str, _Kenmerken], namen: dict[str, set[str]]) -> None:
    codes = df[_CODEKOLOM].astype(str)
    for kolom in _NAAMKOLOMMEN:
        if kolom in df.columns:
            for code, naam in zip(codes, df[kolom], strict=True):
                if isinstance(naam, str) and naam.strip():
                    namen[naam.strip().lower()].add(code)
    for kolom in _kenmerkkolommen(df):
        for code, waarde in zip(codes, df[kolom], strict=True):
            if isinstance(waarde, str):
                per_kolom[kolom].setdefault(waarde, set()).add(code)


def _hoort_bij(code: str, genoemd: set[str]) -> bool:
    """Een vestiging (01VU00) hoort bij haar instelling (01VU)."""
    return any(code == g or (code.startswith(g) and code[len(g) :].isdigit()) for g in genoemd)


def _genoemd(segment: str, patronen: list[tuple[re.Pattern, set[str]]]) -> set[str]:
    return {code for patroon, codes in patronen if patroon.search(segment) for code in codes}


def _waarden(segment: str, kenmerken: _Kenmerken) -> list[str]:
    """De waarden die de zin letterlijk noemt; een langere gaat voor (NIET_BEKOSTIGD boven BEKOSTIGD).

    Alleen in hoofdletters, zoals RIO ze levert: "bijzonder" is ook een gewoon woord.
    """
    treffers = sorted(
        (
            (m.start(), m.end(), waarde)
            for waarde in kenmerken
            for m in _woord(waarde.replace("_", " "), 0).finditer(segment.replace("_", " "))
        ),
        key=lambda t: t[0] - t[1],
    )
    bezet: list[tuple[int, int]] = []
    gevonden = []
    for start, eind, waarde in treffers:
        if not any(start < e and s < eind for s, e in bezet):
            bezet.append((start, eind))
            gevonden.append(waarde)
    return gevonden


def verkeerde_kenmerken(tekst: str, tool_results: list[str]) -> list[str]:
    """Kenmerken in de tekst die in de RIO-data bij een andere instelling staan dan de zin noemt."""
    per_kolom: dict[str, _Kenmerken] = defaultdict(dict)
    namen: dict[str, set[str]] = defaultdict(set)
    for key in data_keys(tool_results):
        known, df = store.meta(key), store.get(key)
        if known is None or df is None or known.bron != "rio" or _CODEKOLOM not in df.columns:
            continue
        _lees(df, per_kolom, namen)
    if not per_kolom:
        return []

    alle_codes = set().union(*(c for k in per_kolom.values() for c in k.values()), *namen.values())
    patronen = [(_woord(code), {code}) for code in alle_codes] + [(_woord(n), c) for n, c in namen.items()]
    problemen = []
    for segment in segmenten(tekst):
        if not (genoemd := _genoemd(segment, patronen)):
            continue
        for kolom, kenmerken in per_kolom.items():
            for waarde in _waarden(segment, kenmerken):
                codes = kenmerken[waarde]
                if any(_hoort_bij(c, genoemd) for c in codes):
                    continue
                problemen.append(
                    f"{kolom} {waarde} hoort bij {', '.join(sorted(codes))}, niet bij "
                    f"{', '.join(sorted(genoemd))} ('{segment}'). Neem het kenmerk uit de rij van die instelling "
                    "of laat het weg."
                )
    return problemen
