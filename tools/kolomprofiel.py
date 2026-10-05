"""Wat er per kolom in een geladen bestand zit, vóór het model filtert (#362).

De catalogus kent per kolom alleen een steekproef ("STUDIEJAAR: bereik 2021-2021" bij
een bestand dat 2021-2025 dekt), en het aantal -1-cellen niet. Het profiel komt uit de
volledig geladen data: bereik voor getallen, het aantal unieke waarden en bij weinig
waarden de volledige lijst, plus hoeveel cellen DUO met -1 onderdrukte.
"""

import pandas as pd

# Tot zoveel unieke waarden is de lijst volledig: genoeg voor GESLACHT, ONDERDEEL of
# provincies, te weinig om instellingen of gemeenten letterlijk mee te sturen.
MAX_WAARDEN = 12


def _getal(v):
    """Een numpy-getal als JSON-getal; 4147.0 na de -1-maskering is een telling (#222)."""
    v = v.item() if hasattr(v, "item") else v
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _kolom(reeks: pd.Series, min1: int) -> dict:
    waarden = reeks.dropna()
    profiel: dict = {}
    if pd.api.types.is_numeric_dtype(reeks) and not pd.api.types.is_bool_dtype(reeks):
        if not waarden.empty:
            profiel["bereik"] = [_getal(waarden.min()), _getal(waarden.max())]
    else:
        uniek = waarden.unique()
        profiel["uniek"] = len(uniek)
        if len(uniek) <= MAX_WAARDEN:
            profiel["waarden"] = sorted(str(w) for w in uniek)
    if min1:
        profiel["min1_cellen"] = min1
    return profiel


def profiel(df: pd.DataFrame, min1: dict[str, int]) -> dict[str, dict]:
    """Per kolom bereik of unieke waarden, en het aantal -1-cellen uit `min1`.

    `df` is de gemaskeerde data: -1 is daar leeg, dus het bereik begint bij een echte telling.
    """
    return {col: _kolom(df[col], min1.get(col, 0)) for col in df.columns}
