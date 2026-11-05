"""Wat een selectie bevat, vastgelegd wanneer een key wordt afgeleid (#187, #143, #728).

query_data en run_analysis leggen dit vast vóór kolomkeuze of aggregatie: daarna
kan de periode- of instellingskolom weg zijn terwijl de selectie er wel op staat.
Dat geldt ook voor de fusies binnen de reeks: zonder instellingskolom zijn ze niet meer te zien, en voor de
instellingen die alleen via een onderwijslocatie in de selectie kwamen (#744).
"""

import pandas as pd

from . import fusies, instelling, periode
from .store import KeyMeta


def _fusies(df: pd.DataFrame, known: KeyMeta, instellingen: tuple[str, ...] | None, jaren) -> tuple[str, ...]:
    """De vaste fusieregels van een DUO-reeks per instelling; de naam uit de data, anders de code."""
    if known.bron != "duo" or not instellingen:
        return ()
    kolom = known.instellingskolom
    namen = instelling.namen(df, kolom) if kolom and instelling.codekolom(df.columns) == kolom else {}
    return fusies.in_reeks({code: namen.get(code, code) for code in instellingen}, jaren)


def _nevenlocaties(known: KeyMeta, instellingen: tuple[str, ...] | None) -> tuple:
    """De nevenlocaties van de ouder die nog in de selectie staan; zonder instellingskolom (een som) allemaal."""
    return tuple(n for n in known.nevenlocaties if instellingen is None or n.code in instellingen)


def van(df: pd.DataFrame, known: KeyMeta | None) -> dict:
    """Overschrijvingen voor store.derive(): de schooljaren, instellingen, fusies en nevenlocaties in `df`."""
    if known is None:
        return {}
    jaren = periode.dekking(df, known.bron, known.periodekolom)
    instellingen = instelling.dekking(df, known.instellingskolom)
    return {
        "schooljaren": jaren,
        "instellingen": instellingen,
        "fusies": _fusies(df, known, instellingen, jaren),
        "nevenlocaties": _nevenlocaties(known, instellingen),
    }
