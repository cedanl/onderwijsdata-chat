"""Welke getallen in een run_analysis-uitkomst niet van de data afhangen (CH-27, #432).

Een script kan een getal typen, het uit eigen constanten laten uitrekenen of via een
variabele doorgeven, en df alleen schijnbaar lezen (`a = 987650; result = a + 4 + len(df) * 0`).
Een lijst van getypte constanten vangt dat niet: dat is een wedloop met elke nieuwe vorm.
Wat het script met de data doet, laat zich wel meten: draai het nog twee keer op verstoorde
invoer. Een getal dat in beide herhalingen terugkomt en zelf niet in de invoer staat, hangt
niet van de data af en is geen bewijs.

- waarden: elke numerieke cel maal een eigen factor (2, 3, 4, ...), zodat sommen, verschillen
  en verhoudingen tussen cellen veranderen;
- rijen: één rij erbij (een kopie van de laatste met gewijzigde tekst), zodat tellingen en
  aantallen unieke waarden veranderen.

Mislukt een herhaling (een filter op een verstoorde code geeft een lege selectie en dan een
fout), dan is niets vastgesteld en blijft de uitkomst bewijs, zoals vóór deze controle.
"""

import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from . import sandbox

logger = logging.getLogger(__name__)

_GETAL = re.compile(r"\d+(?:\.\d+)?")
_ANDERE_TEKST = "·"


def _getallen(tekst: str) -> set[Decimal]:
    return {Decimal(g) for g in _GETAL.findall(tekst)}


def _uit(waarde: Any) -> set[Decimal]:
    return _getallen(json.dumps(waarde, ensure_ascii=False, default=str))


def _uit_frame(frame: Any) -> set[Decimal]:
    if not isinstance(frame, pd.DataFrame):
        return set()
    return _getallen(frame.to_json(orient="values", default_handler=str))


def _waarden(frame: pd.DataFrame) -> pd.DataFrame:
    """Elke numerieke cel maal een eigen factor: geen twee cellen met dezelfde."""
    kopie = frame.copy()
    kolommen = [k for k in kopie.columns if pd.api.types.is_numeric_dtype(kopie[k]) and kopie[k].dtype != bool]
    for i, kolom in enumerate(kolommen):
        kopie[kolom] = kopie[kolom] * (np.arange(len(kopie)) + 2 + i * len(kopie))
    return kopie


def _rijen(frame: pd.DataFrame) -> pd.DataFrame:
    """Eén rij erbij: de laatste, met andere tekst, zodat ook unieke waarden meetellen."""
    if frame.empty:
        return frame
    extra = frame.iloc[[-1]].copy()
    for kolom in extra.columns:
        if pd.api.types.is_object_dtype(extra[kolom]) or pd.api.types.is_string_dtype(extra[kolom]):
            extra[kolom] = extra[kolom].astype(str) + _ANDERE_TEKST
    return pd.concat([frame, extra], ignore_index=True)


def _verstoord(
    code: str, df: pd.DataFrame | None, tabellen: dict[str, Any], verstoor: Callable[[pd.DataFrame], pd.DataFrame]
) -> sandbox.Uitkomst:
    def toe(frame: Any) -> Any:
        return verstoor(frame) if isinstance(frame, pd.DataFrame) else frame

    return sandbox.voer_uit(code, toe(df), {k: toe(v) for k, v in tabellen.items()})


def onafhankelijke_getallen(
    code: str, df: pd.DataFrame | None, tabellen: dict[str, Any], result: Any
) -> tuple[int | float, ...]:
    """De getallen in `result` die niet van de data afhangen; leeg als niets vast te stellen is."""
    eigen = _uit(result)
    if not eigen:
        return ()
    with ThreadPoolExecutor(max_workers=2) as pool:
        herhalingen = list(pool.map(lambda v: _verstoord(code, df, tabellen, v), (_waarden, _rijen)))
    if fout := next((h.fout for h in herhalingen if h.fout), None):
        logger.info("afhankelijkheid niet vast te stellen: %s", fout[:200])
        return ()
    for herhaling in herhalingen:
        eigen &= _uit(herhaling.result)
    eigen -= set().union(_uit_frame(df), *(_uit_frame(t) for t in tabellen.values()))
    return tuple(sorted(int(g) if g == g.to_integral_value() else float(g) for g in eigen))
