"""Staat een getal bij het jaar en de instelling van zijn eigen rij? (#197)

De getalcontrole (#185) vraagt of een getal ergens in de data staat, de
selectiecontroles (#187, #143) of het genoemde jaar en de genoemde instelling
ergens in de selectie zitten. Samen laten ze "2025/26 = 27.135" door als beide
jaren geselecteerd zijn, terwijl 27.135 bij 2024/25 hoort.

Hier moet een getal in een rij staan met het jaar of de instelling die dezelfde
zin of tabelrij noemt. Alleen bij precies één genoemd jaar of één genoemde
instelling: noemt een zin er meer, dan is niet vast te stellen welk getal
waarbij hoort. Staat een getal in geen enkele rij (een som, een KPI), dan
beslist de getalcontrole erover, niet deze.
"""

import re
from collections import defaultdict
from collections.abc import Callable

import pandas as pd

from tools import instelling, periode, store
from tools.store import KeyMeta

from .grounding import checked_numbers
from .selectie import data_keys

# Een zin of een tabelrij. Een punt in een getal (27.135) wordt niet gevolgd door witruimte.
_SEGMENT = re.compile(r"\n|(?<=[.!?;])\s+")

_Index = dict[str, set]  # getal (cijfers) → de jaren of instellingen van de rijen waarin het staat


def _jaren(df: pd.DataFrame, known: KeyMeta) -> pd.Series | None:
    """Het startjaar per rij, uit de periodecode of, zonder code, uit haar label (#194)."""
    kolom = known.periodekolom
    if kolom and kolom in df.columns:
        return df[kolom].map(lambda v: periode.startjaar(known.bron, v))
    if kolom and (label := f"{kolom}_label") in df.columns:
        return df[label].map(lambda v: next(iter(periode.gevraagde_schooljaren(str(v))), None))
    return None


def _index(df: pd.DataFrame, per_rij: pd.Series, index: _Index) -> None:
    getallen = df.select_dtypes("number")
    for waarde, rij in zip(per_rij, getallen.itertuples(index=False), strict=True):
        if waarde is None or pd.isna(waarde):
            continue
        for v in rij:
            if pd.notna(v) and float(v).is_integer():
                index[str(int(v))].add(waarde)


def _verkeerd(tekst: str, index: _Index, genoemd: Callable[[str], set], naam: Callable[[set], str]) -> list[str]:
    bekend = set().union(*index.values()) if index else set()
    problemen = []
    for segment in filter(None, (s.strip() for s in _SEGMENT.split(tekst))):
        noemt = genoemd(segment)
        if len(noemt) != 1 or not noemt <= bekend:
            continue
        for geschreven, getal in checked_numbers(segment):
            bij = index.get(getal)
            if bij and not noemt & bij:
                problemen.append(
                    f"{geschreven} hoort bij {naam(bij)}, niet bij {naam(noemt)} ('{segment}'). "
                    f"Neem het getal uit de rij van {naam(noemt)}."
                )
    return problemen


def verkeerd_gebonden(tekst: str, tool_results: list[str]) -> list[str]:
    """Getallen die in de tekst bij een ander jaar of een andere instelling staan dan in de data."""
    jaren: _Index = defaultdict(set)
    instellingen: _Index = defaultdict(set)
    namen: dict[str, str] = {}
    for key in data_keys(tool_results):
        known, df = store.meta(key), store.get(key)
        if known is None or df is None:
            continue
        if (per_jaar := _jaren(df, known)) is not None:
            _index(df, per_jaar, jaren)
        if (kolom := known.instellingskolom) and kolom in df.columns and instelling.codekolom(df.columns):
            namen |= instelling.namen(df, kolom)
            _index(df, df[kolom].astype(str), instellingen)

    return [
        *_verkeerd(tekst, jaren, periode.gevraagde_schooljaren, lambda j: ", ".join(periode.labels(sorted(j)))),
        *_verkeerd(
            tekst, instellingen, lambda s: instelling.genoemde(s, namen),
            lambda codes: ", ".join(f"{namen.get(c, c)} ({c})" for c in sorted(codes)),
        ),
    ]
