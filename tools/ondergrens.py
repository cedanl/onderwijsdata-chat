"""Welke rij en welk punt een ondergrens is: een onderdrukte cel (DUO -1, CBS '.') valt erin (#1257, #1261).

De noten boven een export zeggen al dat "een totaal waarin zo'n cel valt" een ondergrens is (`duo.sentinel_notes`),
maar niet wélk totaal. Hier per rij van de tabel in de store: `ja` als een onderdrukte cel in die rij valt, anders
`nee`. Dezelfde cellen als in de noten (`duo.sentinel_cells`); store.put en query_data leggen ze per rij vast, ook na
een aggregatie (een groepstotaal draagt de cellen van zijn groep).

Een eigen berekening (run_analysis) heeft geen cellen per rij: ze erft alleen de telling van wat ze las
(`duo.onderdrukt`). Dan is per punt niet bekend welk getal een ondergrens is, en zegt de figuur dat
(`NIET_PER_PUNT`) in plaats van te raden.
"""

import pandas as pd

from . import duo, store

KOLOM = "ondergrens"
JA = "ja"
NEE = "nee"

# De noot bij een figuur of export waarvan de bron onderdrukte cellen heeft, maar niet per rij.
NIET_PER_PUNT = "ondergrens niet per punt bekend: de bron heeft onderdrukte cellen, maar niet per rij vastgelegd"

# De '#'-regel boven een export met de kolom `ondergrens` (docs/reproducibility.md).
KOLOMREGEL = (
    f"kolom {KOLOM}: {JA} als in die rij een onderdrukte cel valt; het getal is dan ten minste zo groot (een "
    "ondergrens), anders nee"
)

# Wat een hover en de tabel bij zo'n punt zeggen (#1261).
TEN_MINSTE = "ten minste"
ONDERDRUKT = "(onderdrukte cellen)"


def _cellen(key: str, df: pd.DataFrame) -> pd.DataFrame | None:
    """De onderdrukte cellen van `key` op de rijen van `df`; None zonder vastgelegde cellen of zonder één."""
    cellen = duo.sentinel_cells(key)
    if cellen is None or cellen.empty or not cellen.to_numpy().any():
        return None
    return cellen.reindex(df.index).fillna(0)


def rijvlaggen(key: str | None) -> list[bool] | None:
    """Per rij van de tabel onder `key`: valt er een onderdrukte cel in? None als de bron er per rij geen heeft."""
    df = store.get(key) if key else None
    if not isinstance(df, pd.DataFrame):
        return None
    cellen = _cellen(str(key), df)
    if cellen is None:
        return None
    return [bool(n) for n in cellen.sum(axis=1).gt(0)]


def celvlaggen(key: str | None, kolom: str) -> list[bool] | None:
    """Per rij: is de cel in `kolom` (de waarde van het punt) een ondergrens? None zonder cellen per rij."""
    df = store.get(key) if key else None
    if not isinstance(df, pd.DataFrame):
        return None
    cellen = _cellen(str(key), df)
    if cellen is None:
        return None
    if kolom not in cellen.columns:
        return [False] * len(df)
    return [bool(n) for n in cellen[kolom].gt(0)]


def alleen_totaal(key: str | None) -> bool:
    """Heeft de bron van `key` onderdrukte cellen die niet per rij bekend zijn (een eigen berekening, #414)?"""
    return bool(key) and rijvlaggen(key) is None and bool(duo.onderdrukt(str(key)))


def met_kolom(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """De tabel met de kolom `ondergrens` (ja/nee) erachter als er een onderdrukte cel in valt; anders ongewijzigd."""
    vlaggen = rijvlaggen(key)
    if vlaggen is None or KOLOM in df.columns:
        return df
    return df.assign(**{KOLOM: [JA if v else NEE for v in vlaggen]})
