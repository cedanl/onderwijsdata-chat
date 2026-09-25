"""Wat een selectie bevat, vastgelegd wanneer een key wordt afgeleid (#187, #143).

query_data en run_analysis leggen dit vast vóór kolomkeuze of aggregatie: daarna
kan de periode- of instellingskolom weg zijn terwijl de selectie er wel op staat.
"""

import pandas as pd

from . import instelling, periode
from .store import KeyMeta


def van(df: pd.DataFrame, known: KeyMeta | None) -> dict:
    """Overschrijvingen voor store.derive(): de schooljaren en instellingen in `df`."""
    if known is None:
        return {}
    return {
        "schooljaren": periode.dekking(df, known.bron, known.periodekolom),
        "instellingen": instelling.dekking(df, known.instellingskolom),
    }
