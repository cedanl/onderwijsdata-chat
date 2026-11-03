"""De grens tussen de bronpakketten (`packages/`) en de chat wordt bewaakt (#886, epic #883).

`onderwijsdata` en `riodata` staan sinds #885 in deze repo, maar het blijven aparte pakketten: het pakket haalt de bron
op, de chat beslist over scope, poorten en etiketten. Die scheiding hield als twee repo's vanzelf stand; als monorepo
kan één regel `from tools import …` haar breken zonder dat iets rood wordt. Drie regels, statisch gecontroleerd op de
broncode (AST, dus ook een import binnen een functie of achter `try`):

1. Niets onder `packages/` importeert de chat (`tools`, `agent`, `core`, `routes`, `persistence`, …). Het pakket moet
   los te installeren en te testen blijven (`cd packages/<naam> && pytest`).
2. De pakketten importeren elkaar niet. Dat is nu zo en dat blijft zo: elk pakket hangt alleen van `httpx` en zijn
   eigen extras af.
3. De chat importeert alleen de publieke API van de pakketten. Publiek is alles waarvan geen enkel deel van het pad
   met een underscore begint (`riodata.duo` wel, `riodata._catalog` niet), zoals de pakketten het zelf noemen.

Een nieuwe overtreding geeft hier een rode test met bestand en regel.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAKKETTEN_MAP = ROOT / "packages"

# Uit #886: de modules die een pakket nooit mag importeren. De afgeleide lijst hieronder vult dit aan met alles wat
# er verder op het hoogste niveau van de chat staat; deze vijf blijven expliciet, zodat hernoemen hier opvalt.
CHAT_KERN = ("tools", "agent", "core", "routes", "persistence")
# `tests` is een gewone naam in elk pakket (tests/__init__.py) en geen chatcode om op te letten.
_GEEN_CHATMODULE = {"packages", "tests"}
_DYNAMISCH = {"import_module", "__import__"}


def _pakketnamen() -> tuple[str, ...]:
    return tuple(sorted(p.name for p in PAKKETTEN_MAP.iterdir() if (p / "pyproject.toml").is_file()))


def _is_overgeslagen(pad: Path) -> bool:
    """Verborgen mappen (.venv, .git, .claude), caches en node_modules bevatten geen code van deze repo."""
    return any(deel.startswith(".") or deel in {"__pycache__", "node_modules"} for deel in pad.relative_to(ROOT).parts)


def _python_bestanden(map_: Path) -> Iterator[Path]:
    return (p for p in sorted(map_.rglob("*.py")) if not _is_overgeslagen(p))


def chatmodules() -> frozenset[str]:
    """Wat de chat zelf op het hoogste niveau aanbiedt: losse .py-bestanden en mappen met Python erin."""
    namen = {p.stem for p in ROOT.glob("*.py")}
    namen |= {p.name for p in ROOT.iterdir() if p.is_dir() and not _is_overgeslagen(p) and any(p.rglob("*.py"))}
    return frozenset(namen - _GEEN_CHATMODULE) | frozenset(CHAT_KERN)


def _modulepaden(bron: str) -> list[tuple[int, str]]:
    """Elk absoluut importpad in de bron als (regel, 'a.b.c'); een `from a import b` geeft ook 'a.b'.

    Relatieve imports (`from .client import get`) blijven binnen het eigen pakket en tellen niet mee. Dynamische imports
    tellen mee zolang het pad een letterlijke string is.
    """
    paden: list[tuple[int, str]] = []
    for knoop in ast.walk(ast.parse(bron)):
        if isinstance(knoop, ast.Import):
            paden += [(knoop.lineno, alias.name) for alias in knoop.names]
        elif isinstance(knoop, ast.ImportFrom) and knoop.level == 0 and knoop.module:
            paden.append((knoop.lineno, knoop.module))
            paden += [(knoop.lineno, f"{knoop.module}.{alias.name}") for alias in knoop.names]
        elif isinstance(knoop, ast.Call) and (pad := _dynamisch_pad(knoop)):
            paden.append((knoop.lineno, pad))
    return paden


def _dynamisch_pad(oproep: ast.Call) -> str | None:
    """Het letterlijke pad in `importlib.import_module("a.b")` of `__import__("a")`; anders None."""
    functie = oproep.func
    naam = functie.attr if isinstance(functie, ast.Attribute) else getattr(functie, "id", "")
    if naam not in _DYNAMISCH or not oproep.args:
        return None
    eerste = oproep.args[0]
    return eerste.value if isinstance(eerste, ast.Constant) and isinstance(eerste.value, str) else None


def _eerste_per_regel(paden: list[tuple[int, str]], hoogste_niveau: set[str] | frozenset[str]) -> list[str]:
    """De paden met een bepaald hoogste niveau, één melding per regel (`from tools import x` geeft 'tools')."""
    gezien: dict[int, str] = {}
    for regel, pad in paden:
        if pad.split(".")[0] in hoogste_niveau:
            gezien.setdefault(regel, pad)
    return [f"regel {regel}: {pad}" for regel, pad in sorted(gezien.items())]


def pakket_importeert_chat(bron: str, chat: frozenset[str]) -> list[str]:
    """Regel 1: de imports in `bron` die een chatmodule binnenhalen."""
    return _eerste_per_regel(_modulepaden(bron), chat)


def pakket_importeert_pakket(bron: str, andere: frozenset[str]) -> list[str]:
    """Regel 2: de imports in `bron` die een ander bronpakket binnenhalen."""
    return _eerste_per_regel(_modulepaden(bron), andere)


def _is_intern(pad: str) -> bool:
    return any(deel.startswith("_") for deel in pad.split("."))


def _pakketaliassen(boom: ast.AST, pakketten: frozenset[str]) -> set[str]:
    """De namen waaronder het bestand een pakket (of iets eruit) heeft binnengehaald."""
    aliassen: set[str] = set()
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.Import):
            aliassen |= {a.asname or a.name.split(".")[0] for a in knoop.names if a.name.split(".")[0] in pakketten}
        elif isinstance(knoop, ast.ImportFrom) and knoop.level == 0 and (knoop.module or "").split(".")[0] in pakketten:
            aliassen |= {a.asname or a.name for a in knoop.names}
    return aliassen


def chat_gebruikt_niet_publiek(bron: str, pakketten: frozenset[str]) -> list[str]:
    """Regel 3: imports van een intern pakketdeel (underscore in het pad) en `alias._intern`-toegang daartoe."""
    boom = ast.parse(bron)
    gevonden = _eerste_per_regel([(regel, pad) for regel, pad in _modulepaden(bron) if _is_intern(pad)], pakketten)
    aliassen = _pakketaliassen(boom, pakketten)
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.Attribute) and knoop.attr.startswith("_") and not knoop.attr.startswith("__"):
            basis = knoop.value
            while isinstance(basis, ast.Attribute):
                basis = basis.value
            if isinstance(basis, ast.Name) and basis.id in aliassen:
                gevonden.append(f"regel {knoop.lineno}: toegang tot {ast.unparse(knoop)}")
    return gevonden


def _overtredingen(bestanden: Iterator[Path], controle) -> list[str]:
    return [
        f"{pad.relative_to(ROOT)}, {melding}"
        for pad in bestanden
        for melding in controle(pad.read_text(encoding="utf-8"))
    ]


def _chatbestanden() -> Iterator[Path]:
    return (p for p in _python_bestanden(ROOT) if PAKKETTEN_MAP not in p.parents)


# --- de grens zelf ---------------------------------------------------------------------------------------------


def test_een_pakket_importeert_de_chat_niet():
    chat = chatmodules()
    gevonden = _overtredingen(_python_bestanden(PAKKETTEN_MAP), lambda bron: pakket_importeert_chat(bron, chat))

    assert not gevonden, (
        "Een bronpakket importeert chatcode; het pakket haalt de bron op, het beleid (scope, poorten, etiketten) "
        "blijft in tools/. Verplaats de logica of geef haar als parameter mee:\n" + "\n".join(gevonden)
    )


@pytest.mark.parametrize("pakket", _pakketnamen())
def test_de_pakketten_importeren_elkaar_niet(pakket):
    andere = frozenset(_pakketnamen()) - {pakket}
    gevonden = _overtredingen(
        _python_bestanden(PAKKETTEN_MAP / pakket), lambda bron: pakket_importeert_pakket(bron, andere)
    )

    assert not gevonden, f"{pakket} importeert een ander bronpakket:\n" + "\n".join(gevonden)


def test_de_chat_importeert_alleen_de_publieke_api_van_de_pakketten():
    pakketten = frozenset(_pakketnamen())
    gevonden = _overtredingen(_chatbestanden(), lambda bron: chat_gebruikt_niet_publiek(bron, pakketten))

    assert not gevonden, (
        "De chat gebruikt een intern deel van een bronpakket (pad met underscore). Maak het deel publiek in het "
        "pakket, of gebruik wat het pakket aanbiedt:\n" + "\n".join(gevonden)
    )


# --- de bewaking bewaakt zichzelf ------------------------------------------------------------------------------


def test_de_pakketten_zijn_gevonden_en_de_scan_is_niet_leeg():
    """Zonder dit slaagt de grenstest ook als `packages/` verhuist of hernoemd wordt: dan scant hij niets."""
    assert _pakketnamen() == ("onderwijsdata", "riodata")
    for pakket in _pakketnamen():
        assert sum(1 for _ in _python_bestanden(PAKKETTEN_MAP / pakket / "src")) >= 3
        assert sum(1 for _ in _python_bestanden(PAKKETTEN_MAP / pakket / "tests")) >= 3
    assert sum(1 for _ in _chatbestanden()) > 100


def test_de_chatmodules_bevatten_de_kern_en_bestaan_nog():
    chat = chatmodules()

    assert set(CHAT_KERN) <= chat
    for naam in CHAT_KERN:
        assert (ROOT / naam).is_dir(), f"{naam}/ bestaat niet meer: werk CHAT_KERN in tests/test_importgrens.py bij"
    assert {"config", "server", "auth"} <= chat
    assert not chat & {"packages", "tests", "onderwijsdata", "riodata"}


@pytest.mark.parametrize(
    "bron",
    [
        "from tools import catalog",
        "from tools.catalog import zoek",
        "import agent.loop",
        "import core.config as cfg",
        "def f():\n    from persistence import store",
        "try:\n    import routes\nexcept ImportError:\n    routes = None",
        "import importlib\nimportlib.import_module('tools.scopeprofiel')",
        "__import__('core')",
    ],
)
def test_de_scanner_ziet_elke_vorm_van_een_chatimport(bron):
    assert pakket_importeert_chat(bron, chatmodules())


@pytest.mark.parametrize(
    "bron",
    [
        "from .client import get",
        "from . import duo",
        "import httpx\nimport json",
        "from importlib.resources import files",
        "from riodata import duo",  # eigen pakket: regel 1 gaat over de chat
        "import importlib\nimportlib.import_module(naam)",  # geen letterlijk pad: niet te beoordelen
        "tools = 1\nprint(tools)",
    ],
)
def test_de_scanner_geeft_geen_vals_alarm(bron):
    assert pakket_importeert_chat(bron, chatmodules()) == []


def test_de_scanner_ziet_een_import_tussen_pakketten():
    assert pakket_importeert_pakket("from riodata import duo", frozenset({"riodata"}))
    assert pakket_importeert_pakket("import riodata.duo", frozenset({"riodata"}))
    assert not pakket_importeert_pakket("from .client import get", frozenset({"riodata"}))


@pytest.mark.parametrize(
    "bron",
    [
        "from riodata import _catalog",
        "from riodata._catalog import merge",
        "import onderwijsdata._intern",
        "from riodata import duo\nduo._lees()",
        "import riodata.duo as d\nd._lees()",
        "import riodata\nriodata.duo._lees()",
    ],
)
def test_de_scanner_ziet_gebruik_van_een_intern_pakketdeel(bron):
    assert chat_gebruikt_niet_publiek(bron, frozenset({"riodata", "onderwijsdata"}))


@pytest.mark.parametrize(
    "bron",
    [
        "from riodata import duo, roa\nduo.haal()",
        "from riodata.client import zonder_lijstendpoint",
        "import riodata.duo\nriodata.duo.__name__",  # dunder is geen intern deel
        "from collections import namedtuple\nrecord._asdict()",  # eigen namen met underscore: niet van een pakket
        "from onderwijsdata import validate_selection as _v\n_v({})",
    ],
)
def test_de_scanner_geeft_geen_vals_alarm_op_de_publieke_api(bron):
    assert chat_gebruikt_niet_publiek(bron, frozenset({"riodata", "onderwijsdata"})) == []
