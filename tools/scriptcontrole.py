"""Wat run_analysis vóór uitvoering uit een script leest en weigert (#11, #410).

De eerste verdedigingslaag; de tweede is het afgeschermde proces (`tools/sandbox.py`).
De controle werkt op de AST, niet op tekst:

- geen import, geen dunder (`__globals__`, `__class__`, ...) en geen frame-attributen,
  ook niet in een string (`df.query('x.__class__')`, `'{0.__class__}'.format`);
- `store_get` alleen met een letterlijke key: de sandbox krijgt precies die tabellen mee;
- geen overgetypte data, en het script leest data (`df` of `store_get`).

Daarnaast verzamelt hij de getallen die het script zelf typt (`constanten`): een
getal in de uitkomst dat het script zelf schreef, is geen bewijs (#410).
"""

import ast
import math
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_VERBODEN_NAMEN = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "open",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "breakpoint",
        "input",
        "help",
        "memoryview",
    }
)
# Attributen die zonder dunder bij frames, code en globals komen.
_VERBODEN_ATTRIBUTEN = frozenset(
    {
        "gi_frame",
        "gi_code",
        "cr_frame",
        "cr_code",
        "ag_frame",
        "ag_code",
        "f_globals",
        "f_locals",
        "f_builtins",
        "f_back",
        "f_code",
        "tb_frame",
        "tb_next",
    }
)
_HARDCODED_MIN = 6
_GETAL_IN_TEKST = re.compile(r"\d+(?:\.\d+)?")
_REKENEN: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


class Geweigerd(ValueError):
    """Het script mag niet draaien; de tekst is de melding voor het model."""


@dataclass(frozen=True)
class Script:
    keys: tuple[str, ...]  # letterlijke store_get-keys, in volgorde
    constanten: tuple[int | float, ...]  # getallen die het script zelf typt


def _niet_toegestaan(wat: str) -> Geweigerd:
    return Geweigerd(f"Niet toegestaan in analyse-scripts: '{wat}'. Gebruik de beschikbare libraries (pd, np, px, go).")


def _verboden(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"
    if isinstance(node, ast.Name) and (node.id in _VERBODEN_NAMEN or node.id.startswith("__")):
        return node.id
    if isinstance(node, ast.Attribute) and (node.attr in _VERBODEN_ATTRIBUTEN or node.attr.startswith("__")):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
        return node.value
    return None


def _store_key(node: ast.Call) -> str:
    if len(node.args) == 1 and not node.keywords:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    raise _niet_toegestaan("store_get met een berekende key; schrijf de key letterlijk, zoals store_get('cbs:...')")


def _hardcoded(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Dict, ast.Tuple)):
            nums = [n for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]
            if len(nums) >= _HARDCODED_MIN:
                return True
    return False


def _vouw(node: ast.AST) -> int | float | None:
    """De waarde van een expressie uit alleen getallen (987650 + 4), anders None."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (int, float)) and not isinstance(node.value, bool) else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        waarde = _vouw(node.operand)
        return None if waarde is None else (-waarde if isinstance(node.op, ast.USub) else waarde)
    if isinstance(node, ast.BinOp) and type(node.op) in _REKENEN:
        links, rechts = _vouw(node.left), _vouw(node.right)
        if links is None or rechts is None:
            return None
        try:
            return _REKENEN[type(node.op)](links, rechts)
        except ArithmeticError:
            return None
    return None


def _constanten(tree: ast.AST) -> tuple[int | float, ...]:
    gevonden: set[int | float] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            gevonden.update(float(g) if "." in g else int(g) for g in _GETAL_IN_TEKST.findall(node.value))
        elif (waarde := _vouw(node)) is not None:
            gevonden.add(waarde)
    return tuple(sorted(w for w in gevonden if math.isfinite(w)))


def ontleed(code: str) -> Script:
    """Controleer `code`; Geweigerd (of SyntaxError) als het niet mag draaien."""
    tree = ast.parse(code)
    keys: list[str] = []
    leest = False
    for node in ast.walk(tree):
        if wat := _verboden(node):
            raise _niet_toegestaan(wat)
        if isinstance(node, ast.Name) and node.id in ("df", "store_get"):
            leest = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "store_get":
            keys.append(_store_key(node))
    if _hardcoded(tree):
        raise Geweigerd(
            "Script bevat een literal datastructuur met ≥6 getallen. "
            "Dit ziet eruit als overgetypte data. Lees data via df of store_get(key)."
        )
    if not leest:
        raise Geweigerd("Script leest geen data. Lees data via `df` of `store_get(key)`; typ nooit data over.")
    return Script(keys=tuple(dict.fromkeys(keys)), constanten=_constanten(tree))
