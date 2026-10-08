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

Drie uitkomsten, niet twee (#456): onafhankelijk (de getallen erbij), afhankelijk, of niet
vast te stellen. Dat laatste gebeurt als een herhaling mislukt (een filter op een verstoorde
code geeft een lege selectie en dan een fout); dan telt elk getal dat niet in de invoer
staat als onafhankelijk. Een mislukte controle is geen vertrouwen.

Een conditionele constante (`987654 if df['a'].iloc[0] == 1 else 0`) kiest bij verstoorde
waarden de andere tak, en verdwijnt dan uit de doorsnede. Daarom telt ook een getal dat het
script letterlijk of als rekensom van literals bevat en dat niet in de invoer staat.

Een waarde die een eerdere stap afkeurde (`geerfd`) staat daarna in de invoer van een volgende
stap; dat maakt haar geen bewijs.
"""

import ast
import json
import logging
import operator
import re
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

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


_REKEN: dict[type[ast.AST], Callable[..., Decimal]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _reken(node: ast.AST) -> Decimal | None:
    """De waarde van een literal of een rekensom van literals; None voor al het andere."""
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
        try:
            return Decimal(str(node.value).strip()) if isinstance(node.value, int | float | str) else None
        except InvalidOperation:
            return None
    if isinstance(node, ast.UnaryOp) and type(node.op) in _REKEN and (w := _reken(node.operand)) is not None:
        return _REKEN[type(node.op)](w)
    if isinstance(node, ast.BinOp) and type(node.op) in _REKEN:
        links, rechts = _reken(node.left), _reken(node.right)
        if links is not None and rechts is not None:
            try:
                return _REKEN[type(node.op)](links, rechts)
            except (ArithmeticError, InvalidOperation):
                return None
    return None


def _literals(code: str) -> set[Decimal]:
    """Elk getal dat het script typt, ook als rekensom van literals (987650 + 4) of als tekst."""
    try:
        boom = ast.parse(code)
    except SyntaxError:
        return set()
    return {abs(w) for node in ast.walk(boom) if (w := _reken(node)) is not None}


def _getal(g: Decimal) -> int | float:
    return int(g) if g == g.to_integral_value() else float(g)


# Getallen die niet van de data afhangen; de getalcontrole telt ze niet als bewijs (#410, CH-27).
SCRIPTCONSTANTEN = "scriptconstanten"

AFHANKELIJK = "afhankelijk"
ONAFHANKELIJK = "onafhankelijk"
ONBEPAALD = "niet vast te stellen"

ONBEPAALD_MELDING = (
    "Afhankelijkheid niet vast te stellen: het script liep niet op verstoorde invoer. "
    "Getallen die niet in de invoer staan, gelden niet als bron."
)


@dataclass(frozen=True)
class Toets:
    """Wat de controle vaststelde, en welke getallen van `result` daarom geen bewijs zijn."""

    soort: Literal["afhankelijk", "onafhankelijk", "niet vast te stellen"]
    constanten: tuple[int | float, ...] = ()


def toets(
    code: str, df: pd.DataFrame | None, tabellen: dict[str, Any], result: Any, geerfd: Iterable[int | float] = ()
) -> Toets:
    """Hangen de getallen in `result` van de data af? Bij twijfel niet (fail-closed)."""
    eigen = _uit(result)
    if not eigen:
        return Toets(AFHANKELIJK)
    afgekeurd = {Decimal(str(g)) for g in geerfd}
    invoer = set().union(_uit_frame(df), *(_uit_frame(t) for t in tabellen.values())) - afgekeurd
    with ThreadPoolExecutor(max_workers=2) as pool:
        herhalingen = list(pool.map(lambda v: _verstoord(code, df, tabellen, v), (_waarden, _rijen)))
    if fout := next((h.fout for h in herhalingen if h.fout), None):
        logger.info("afhankelijkheid niet vast te stellen: %s", fout[:200])
        return Toets(ONBEPAALD, tuple(sorted(_getal(g) for g in eigen - invoer)))
    vast = set(eigen)
    for herhaling in herhalingen:
        vast &= _uit(herhaling.result)
    vast |= eigen & (_literals(code) | afgekeurd)
    vast -= invoer
    return Toets(ONAFHANKELIJK, tuple(sorted(_getal(g) for g in vast))) if vast else Toets(AFHANKELIJK)
