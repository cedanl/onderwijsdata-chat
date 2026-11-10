"""Wat run_analysis vóór uitvoering uit een script leest en weigert (#11, #410).

De eerste verdedigingslaag; de tweede is het afgeschermde proces (`tools/sandbox.py`).
De controle werkt op de AST, niet op tekst:

- geen import, geen dunder (`__globals__`, `__class__`, ...) en geen frame-attributen,
  ook niet in een string (`df.query('x.__class__')`, `'{0.__class__}'.format`);
- geen stdlib-module als attribuut van een bibliotheekobject (`pd.io.common.os`,
  `pd.compat.sys`, #443): het kindproces heeft geen omgeving, netwerk of schrijfrechten,
  maar `os.getpid()`, `os.getcwd()` en `os.environ` waren zo nog bereikbaar; ook niet in
  een string, want pandas lost `@naam` in `df.query`/`df.eval` en elke naam in `pd.eval`
  op in de variabelen van het script (`df.eval('@pd.io.common.os.getpid()')`);
- `store_get` alleen met een letterlijke key: de sandbox krijgt precies die tabellen mee;
- geen overgetypte data, en het script leest data (`df` of `store_get`);
- welke `merge`, `join` of `concat` tabellen van twee of meer keys samenvoegt (#1014): `analysis` weigert die en
  verwijst naar `koppel_data`, dat in code koppelt zonder rijen te verliezen. De herkomst van elke naam volgt de
  toewijzingen (`a = store_get('x').groupby('k').sum()`, `for`, comprehensions, `lijst.append(...)`), over alle takken
  samen: een naam die in één tak een andere key krijgt, draagt beide. Dit is een patroonwacht, geen sluitende
  dataflow-analyse: `map`, `isin`, `reindex`, een opzoeking in een dict of een functie die een tabel als argument
  krijgt, combineren twee keys zonder dat de controle het ziet. Ze dwingt de gewone koppeling naar de tool, niet elk
  gebruik van twee keys samen.

Welke getallen in de uitkomst niet van de data afhangen, meet `tools/afhankelijkheid.py`
na de uitvoering (CH-27): een lijst van getypte constanten miste variabelen.

De controle op strings is een heuristiek: wie een expressie uit stukken plakt, komt erlangs.
Wat dan bereikbaar is, is het kindproces zelf, zonder omgeving, bestanden, netwerk of
processen; `tests/test_sandbox_isolatie.py` legt dat restrisico vast.
"""

import ast
import io
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass

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
# Modules die via een attribuut van pandas of numpy te bereiken zijn (`pd.io.common.os`) en bij het
# besturingssysteem, het proces, bestanden of het netwerk komen (#443). Geen importnaam: `import` is al weg.
_VERBODEN_MODULES = frozenset(
    {
        "os",
        "posix",
        "sys",
        "subprocess",
        "multiprocessing",
        "threading",
        "builtins",
        "importlib",
        "pkgutil",
        "runpy",
        "code",
        "socket",
        "ssl",
        "http",
        "urllib",
        "ctypes",
        "signal",
        "resource",
        "shutil",
        "pathlib",
        "tempfile",
        "glob",
        "io",
        "pickle",
        "marshal",
        "pty",
        "fcntl",
        "select",
        "platform",
        "webbrowser",
    }
)
# In een pandas-expressie geldt dezelfde regel als in de AST: geen module en geen frame achter een punt.
_VERBODEN_ACHTER_PUNT = _VERBODEN_MODULES | _VERBODEN_ATTRIBUTEN
# Tokens waar pandas overheen leest tussen een punt en de naam erna.
_TUSSENRUIMTE = frozenset({tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT})
_HARDCODED_MIN = 6
# Aanroepen die tabellen samenvoegen (#1014): als `pd.x(...)` of `tabel.x(...)`.
_KOPPELAANROEPEN = frozenset({"merge", "merge_asof", "merge_ordered", "join", "concat"})
# Methoden die hun argumenten in het object zelf zetten: `delen.append(ander)` geeft `delen` de herkomst van `ander`.
_VULLERS = frozenset({"append", "extend", "insert", "update", "setdefault", "add"})


class Geweigerd(ValueError):
    """Het script mag niet draaien; de tekst is de melding voor het model."""


@dataclass(frozen=True)
class Koppeling:
    """Een merge, join of concat in het script en de keys waar haar invoer uit komt (#1014)."""

    aanroep: str
    keys: frozenset[str]  # zoals het script ze noemt; `analysis` maakt ze canoniek


@dataclass(frozen=True)
class Script:
    keys: tuple[str, ...]  # letterlijke store_get-keys, in volgorde
    koppelingen: tuple[Koppeling, ...] = ()  # elke aanroep die invoer van twee of meer keys samenvoegt


def _niet_toegestaan(wat: str) -> Geweigerd:
    return Geweigerd(f"Niet toegestaan in analyse-scripts: '{wat}'. Gebruik de beschikbare libraries (pd, np, px, go).")


def _verboden_in_tekst(tekst: str) -> str | None:
    """Wat een string niet mag bevatten: een dunder, of een verboden naam achter een punt.

    Een string kan een pandas-expressie zijn (`df.query`, `df.eval`, `pd.eval`). pandas leest
    die als Python-tokens en lost `@naam`, en zonder kolomresolvers elke naam, op in de
    variabelen van het script: `@pd.io.common.os` komt zo bij `os` zonder import en zonder
    attribuut in de AST. Dezelfde regel als voor de AST, op dezelfde tokens.
    """
    if "__" in tekst:
        return tekst
    if "." not in tekst:
        return None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(tekst).readline))
    except (tokenize.TokenError, SyntaxError):
        return None  # geen tekst die pandas als expressie kan lezen
    na_punt = False
    for tok in tokens:
        if tok.type in _TUSSENRUIMTE:
            continue
        if na_punt and tok.type == tokenize.NAME and tok.string in _VERBODEN_ACHTER_PUNT:
            return f"{tok.string} (een module via een bibliotheekobject, in een pandas-expressie)"
        na_punt = tok.type == tokenize.OP and tok.string == "."
    return None


def _verboden(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"
    if isinstance(node, ast.Name) and (node.id in _VERBODEN_NAMEN or node.id.startswith("__")):
        return node.id
    if isinstance(node, ast.Attribute) and (node.attr in _VERBODEN_ATTRIBUTEN or node.attr.startswith("__")):
        return node.attr
    if isinstance(node, ast.Attribute) and node.attr in _VERBODEN_MODULES:
        return f"{node.attr} (een module via een bibliotheekobject)"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _verboden_in_tekst(node.value)
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


def _store_get_key(node: ast.AST) -> str | None:
    """De key van een `store_get('...')`; na de controle in `ontleed` is die altijd letterlijk."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "store_get":
        arg = node.args[0] if node.args else None
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _bronkeys(node: ast.AST, herkomst: dict[str, frozenset[str]]) -> frozenset[str]:
    """De keys waar een expressie uit leest: de herkomst van elke naam erin plus elke store_get erin."""
    keys: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            keys |= herkomst.get(n.id, frozenset())
        elif (key := _store_get_key(n)) is not None:
            keys.add(key)
    return frozenset(keys)


def _namen(doel: ast.AST) -> tuple[str, ...]:
    """De namen die een toewijzing raakt: `a, b = ...` beide, `df['x'] = ...` en `t.loc[i, 'y'] = ...` de tabel zelf,
    niet de namen in de index."""
    if isinstance(doel, ast.Name):
        return (doel.id,)
    if isinstance(doel, (ast.Tuple, ast.List)):
        return tuple(n for deel in doel.elts for n in _namen(deel))
    if isinstance(doel, (ast.Starred, ast.Subscript, ast.Attribute)):
        return _namen(doel.value)
    return ()


def _stromen(tree: ast.AST) -> Iterator[tuple[tuple[str, ...], ast.AST]]:
    """Elke plek waar data een naam in gaat: (de namen, de expressie waar ze vandaan komt)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            yield tuple(n for doel in node.targets for n in _namen(doel)), node.value
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            yield _namen(node.target), node.value
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            yield _namen(node.target), node.iter
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            yield _namen(node.optional_vars), node.context_expr
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _VULLERS:
            yield _namen(node.func.value), ast.Tuple(elts=[*node.args, *(k.value for k in node.keywords)])


def _herkomst(tree: ast.AST, data_key: str | None) -> dict[str, frozenset[str]]:
    """Per naam de keys waar hij uit leest, over alle toewijzingen tot er niets meer bijkomt; `df` is `data_key`."""
    herkomst: dict[str, frozenset[str]] = {"df": frozenset({data_key})} if data_key else {}
    stromen = list(_stromen(tree))
    veranderd = True
    while veranderd:  # de verzamelingen groeien alleen, binnen de keys van het script: dit stopt
        veranderd = False
        for namen, bron in stromen:
            keys = _bronkeys(bron, herkomst)
            for naam in namen:
                if not keys <= (oud := herkomst.get(naam, frozenset())):
                    herkomst[naam] = oud | keys
                    veranderd = True
    return herkomst


def _koppelingen(tree: ast.AST, herkomst: dict[str, frozenset[str]]) -> tuple[Koppeling, ...]:
    """Elke merge, join of concat waarvan de aanroep (object, argumenten, keywords) uit twee of meer keys leest.

    Een `join` telt alleen als het object zelf uit een key leest: `", ".join(...)` of `sep.join(...)` is een string.
    """
    uit = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        aanroep = node.func.attr
        if aanroep not in _KOPPELAANROEPEN or (aanroep == "join" and not _bronkeys(node.func.value, herkomst)):
            continue
        if len(keys := _bronkeys(node, herkomst)) >= 2:
            uit.append(Koppeling(aanroep, keys))
    return tuple(uit)


def ontleed(code: str, data_key: str | None = None) -> Script:
    """Controleer `code`; Geweigerd (of SyntaxError) als het niet mag draaien.

    `data_key` is de key achter `df`: zo weet de controle uit welke keys een merge, join of concat leest.
    """
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
    return Script(keys=tuple(dict.fromkeys(keys)), koppelingen=_koppelingen(tree, _herkomst(tree, data_key)))
