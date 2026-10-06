"""VO-bestanden publiceren elk aantal van 1 t/m 4 als 4: een som ervan is een bovengrens (#406, #407).

Naast de -1-sentinel (onderdrukt, dus een ondergrens). De regel staat in de
DUO-beschrijving, maar niet elk bestand volgt hem: de HO-bestanden gebruiken -1
(#407). Daarom toetst dit de data: de regel geldt als er 4-cellen zijn en geen 1-3.
"""

import pandas as pd

from core.sentinels import EMPTY_CELLS

# Het kleinste aantal dat DUO wel exact publiceert is 5: tot en met 4 is samengevoegd.
_PUBLICATIEWAARDE = 4
_ACHTERGROND = 3  # 1..4 gepubliceerd als 4: een 4 kan maximaal 3 te hoog zijn

NOOT_ALS_MIN_EEN = (
    "De DUO-beschrijving noemt '1-4 gepubliceerd als 4', maar in dit bestand staan kleine aantallen als -1 "
    "(onderdrukte cel). Een 4 is hier een echte 4; de regel is niet gebruikt."
)


def _aantalkolommen(df: pd.DataFrame) -> list:
    return [c for c in df.columns if "AANTAL" in str(c).upper() and pd.api.types.is_numeric_dtype(df[c])]


def regel_geldt(df: pd.DataFrame) -> bool:
    """Volgt de data de regel: 4-cellen aanwezig en geen 1-3-cellen in de aantalkolommen?"""
    kolommen = _aantalkolommen(df)
    if not kolommen:
        return False
    waarden = df[kolommen]
    return bool((waarden == _PUBLICATIEWAARDE).any(axis=None) and not waarden.isin([1, 2, 3]).any(axis=None))


def vier_cellen(df: pd.DataFrame) -> pd.DataFrame:
    """Per rij en aantalkolom 1 voor een als 4 gepubliceerde cel; alleen rijen met er minstens één."""
    kolommen = _aantalkolommen(df)
    if not kolommen:
        return EMPTY_CELLS
    cellen = (df[kolommen] == _PUBLICATIEWAARDE).astype(int)
    return cellen[cellen.any(axis=1)]


def bereik(som: float, cellen: int) -> tuple[int, int]:
    """Tussen welke waarden ligt het werkelijke totaal: elke als-4-cel is 1 tot 4."""
    return round(som - _ACHTERGROND * cellen), round(som)


def noten(aantallen: dict[str, int]) -> list[str]:
    """Melding per kolom voor de tool-output van een selectie."""
    return [
        f"{n} cellen met waarde 4 in '{kolom}': DUO publiceert 1 t/m 4 als 4, dus de som is een bovengrens "
        f"(het werkelijke totaal ligt per cel 0 tot 3 lager)"
        for kolom, n in aantallen.items()
    ]
