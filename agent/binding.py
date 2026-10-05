"""Staat een getal bij het jaar en de instelling van zijn eigen rij? (#197, #212)

De getalcontrole (#185) vraagt of een getal ergens in de data staat, de
selectiecontroles (#187, #143) of het genoemde jaar en de genoemde instelling
ergens in de selectie zitten. Samen laten ze "2025/26 = 27.135" door als beide
jaren geselecteerd zijn, terwijl 27.135 bij 2024/25 hoort.

Hier moet een getal in een rij staan die past bij het jaar én de instelling die
dezelfde zin of tabelrij noemt. De index loopt per rij (jaar, instelling), niet
per as: anders komt "2024/25 + NHL Stenden + 55.555" door twee losse helften.
Noemt een zin meer waarden op één as (een vergelijking), dan is niet vast te
stellen welk getal waarbij hoort; de rij moet dan bij een van die waarden
passen. Staat een getal in geen enkele rij (een som, een KPI), dan beslist de
getalcontrole erover, niet deze.
"""

import re
from collections import defaultdict
from itertools import product

import pandas as pd

from tools import instelling, periode, store
from tools.store import KeyMeta

from .grounding import checked_numbers
from .selectie import data_keys

# Een zin of een tabelrij. Een punt in een getal (27.135) wordt niet gevolgd door witruimte.
_SEGMENT = re.compile(r"\n|(?<=[.!?;])\s+")

_Rij = tuple[int | None, str | None]  # (startjaar, instellingscode); None als de selectie die as mist
_Index = dict[str, set[_Rij]]  # getal (cijfers) → de dimensies van de rijen waarin het staat


def segmenten(tekst: str) -> list[str]:
    """De zinnen en tabelrijen van een tekst, zonder lege."""
    return [s for s in (s.strip() for s in _SEGMENT.split(tekst)) if s]


def _jaren(df: pd.DataFrame, known: KeyMeta) -> pd.Series | None:
    """Het startjaar per rij, uit de periodecode of, zonder code, uit haar label (#194)."""
    kolom = known.periodekolom
    if kolom and kolom in df.columns:
        return df[kolom].map(lambda v: periode.startjaar(known.bron, v))
    if kolom and (label := f"{kolom}_label") in df.columns:
        return df[label].map(lambda v: next(iter(periode.gevraagde_schooljaren(str(v))), None))
    return None


def _waarden(reeks: pd.Series | None, rijen: int) -> list:
    """De waarde per rij, None waar de as ontbreekt of de cel leeg is."""
    if reeks is None:
        return [None] * rijen
    return [None if pd.isna(v) else v for v in reeks]


def _index(df: pd.DataFrame, jaren: pd.Series | None, codes: pd.Series | None, index: _Index) -> None:
    per_rij = zip(
        _waarden(jaren, len(df)),
        _waarden(codes, len(df)),
        df.select_dtypes("number").itertuples(index=False),
        strict=True,
    )
    for jaar, code, getallen in per_rij:
        for v in getallen:
            if pd.notna(v) and float(v).is_integer():
                index[str(int(v))].add((jaar, code))


def _past(rij: _Rij, genoemd: tuple[set, set]) -> bool:
    """Past de rij bij wat de zin noemt? Een as die de zin niet noemt of de selectie mist, telt niet mee."""
    return all(not noemt or waarde is None or waarde in noemt for waarde, noemt in zip(rij, genoemd, strict=True))


def _label(rij: _Rij, genoemd: tuple[set, set], namen: dict[str, str]) -> str:
    """De rij als de lezer hem kent, alleen met de assen die de zin noemt."""
    jaar, code = rij
    delen = []
    if genoemd[0] and jaar is not None:
        delen.append(periode.label(jaar))
    if genoemd[1] and code is not None:
        delen.append(f"{namen.get(code, code)} ({code})")
    return " · ".join(delen)


def _verkeerd(tekst: str, index: _Index, bekend: tuple[set, set], namen: dict[str, str]) -> list[str]:
    problemen = []
    for segment in segmenten(tekst):
        genoemd = (
            periode.gevraagde_schooljaren(segment) & bekend[0],
            instelling.genoemde(segment, namen) & bekend[1],
        )
        if not any(genoemd):
            continue
        gevraagd = ", ".join(_label(r, genoemd, namen) for r in product(genoemd[0] or [None], genoemd[1] or [None]))
        for geschreven, getal in checked_numbers(segment):
            rijen = index.get(getal)
            if rijen and not any(_past(rij, genoemd) for rij in rijen):
                echt = ", ".join(sorted({_label(r, genoemd, namen) for r in rijen}))
                problemen.append(
                    f"{geschreven} hoort bij {echt}, niet bij {gevraagd} ('{segment}'). "
                    f"Neem het getal uit de rij van {gevraagd}."
                )
    return problemen


def verkeerd_gebonden(tekst: str, tool_results: list[str]) -> list[str]:
    """Getallen in de tekst die in de data bij een andere jaar-instellingcombinatie staan dan de zin noemt."""
    index: _Index = defaultdict(set)
    namen: dict[str, str] = {}
    for key in data_keys(tool_results):
        known, df = store.meta(key), store.get(key)
        if known is None or df is None:
            continue
        kolom = known.instellingskolom
        codes = None
        if kolom and kolom in df.columns and instelling.codekolom(df.columns):
            codes = df[kolom].astype(str)
            namen |= instelling.namen(df, kolom)
        _index(df, _jaren(df, known), codes, index)

    rijen = set().union(*index.values()) if index else set()
    bekend = ({j for j, _ in rijen if j is not None}, {c for _, c in rijen if c is not None})
    return _verkeerd(tekst, index, bekend, namen)
