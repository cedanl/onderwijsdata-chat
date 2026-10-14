"""DUO-sentinels: -1 is een onderdrukte cel, geen telwaarde.

Eén plek voor de regel, omdat drie consumenten hem nodig hebben: de store
(chat-tools), de dashboards en de code-snippets. Toen alleen de store maskeerde,
toonde het dashboard -1 studenten en lagere totalen dan de chat (#228), en gaf
de snippet andere getallen dan de app (#227).

De waarden, hun betekenis en de uitgezonderde kolommen staan als regel [sentinel] in
data/domeinregels.toml, met de DUO-passage als bron (#363). Hier staat hoe ze worden toegepast.
"""

import pandas as pd

from core import domeinregels

_REGEL = domeinregels.laad().sentinel

SENTINELS = _REGEL.waarden

# Wat -1 betekent, in de woorden die tool-output en snippets delen (#244).
BETEKENIS = _REGEL.betekenis

# Kolommen waarin -1 een geldige meetwaarde kan zijn in plaats van een onderdrukte cel.
SIGNED_HINTS = _REGEL.uitgezonderd_als_kolom_bevat

EMPTY_CELLS = pd.DataFrame()


def is_maskable(df: pd.DataFrame, col) -> bool:
    if not pd.api.types.is_numeric_dtype(df[col]):
        return False
    return not any(hint in str(col).upper() for hint in SIGNED_HINTS)


def mask_sentinels(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vervang DUO-sentinels (-1) door pd.NA en geef per rij aan welke cellen dat waren.

    DUO markeert onderdrukte waarden (kleine aantallen) met -1. Die mogen nooit als
    telwaarde meedoen. De cellen worden bijgehouden omdat een onderdrukte cel betekent
    dat een totaal een ondergrens is: bij 2 onderdrukte cellen kan 300 in werkelijkheid
    hoger liggen, en dat moet de gebruiker kunnen zien.

    Geeft (gemaskeerde df, cellen) terug; `cellen` heeft de index van df, alleen rijen
    met minstens één sentinel, en per maskeerbare kolom het aantal (0/1).
    Idempotent: al gemaskeerde data levert niets op.
    """
    masks = {}
    for col in df.columns:
        if is_maskable(df, col):
            mask = df[col].isin(SENTINELS)
            if mask.any():
                masks[col] = mask
    if not masks:
        return df, EMPTY_CELLS
    # Pas kopiëren als er echt iets te maskeren valt: put() draait dit op elke
    # DataFrame die de store in gaat, ook de al gemaskeerde.
    out = df.copy()
    for col, mask in masks.items():
        out.loc[mask, col] = pd.NA
    cells = pd.DataFrame(masks).astype(int)
    return out, cells[cells.any(axis=1)]
