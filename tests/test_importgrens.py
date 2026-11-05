"""De grenzen rond het bronpakket (`packages/onderwijsbronnen`) en tussen de bronnen erin (#886, #910, #911).

Het pakket haalt de bronnen op, de chat beslist over scope, poorten en etiketten. Sinds #910 staan alle bronnen in één
pakket, met per bron een subpakket (`cbs`, `duo`, `rio`, `roa`, `uwv`, `inspectie`, `sbb`) en de gedeelde code in
`_kern`. Dat de bronnen elkaar niet raken, hield als losse pakketten vanzelf stand; in één pakket breekt één regel
`from ..duo import load` het zonder dat iets rood wordt. Vijf regels, statisch gecontroleerd op de broncode (AST, dus
ook een import binnen een functie of achter `try`, en relatieve imports omgerekend naar hun volledige pad):

1. Niets onder `packages/` importeert de chat (`tools`, `agent`, `core`, `routes`, `persistence`, …). Het pakket moet
   los te installeren en te testen blijven (`cd packages/onderwijsbronnen && pytest`).
2. Een bron importeert alleen zichzelf en `onderwijsbronnen._kern`: nooit een andere bron, nooit de bovenlaag
   (`onderwijsbronnen` zelf, `contract`, `scope`) en nooit een oude pakketnaam (`riodata`, `onderwijsdata`).
3. `_kern` importeert geen bron, geen bovenlaag en geen oude pakketnaam: alleen zichzelf.
4. De chat importeert alleen de publieke API van het pakket. Publiek is alles waarvan geen enkel deel van het pad met
   een underscore begint (`onderwijsbronnen.duo` wel, `onderwijsbronnen._kern.verrijking` niet).
5. De chat gebruikt de oude namen `riodata` en `onderwijsdata` niet. Ze bestaan sinds #914 niet meer (de shims van
   #910 zijn weg); een import binnen een functie zou pas falen als die functie draait, dus valt hij hier op. Een
   opgeslagen snippet met die namen staat als tekst in een fixture, niet als import.

Een nieuwe overtreding geeft hier een rode test met bestand en regel.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAKKETTEN_MAP = ROOT / "packages"
PAKKET = "onderwijsbronnen"
BRON_SRC = PAKKETTEN_MAP / PAKKET / "src"
BRONNEN = ("cbs", "duo", "rio", "roa", "uwv", "inspectie", "sbb")
KERN = "_kern"
OUDE_NAMEN = ("riodata", "onderwijsdata")

# Uit #886: de modules die een pakket nooit mag importeren. De afgeleide lijst hieronder vult dit aan met alles wat
# er verder op het hoogste niveau van de chat staat; deze vijf blijven expliciet, zodat hernoemen hier opvalt.
CHAT_KERN = ("tools", "agent", "core", "routes", "persistence")
# `tests` is een gewone naam in het pakket (tests/__init__.py) en geen chatcode om op te letten.
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


def _module_van(pad: Path, src: Path) -> tuple[str, str]:
    """(`module`, `pakket`) van een bestand onder `src`: `rio/client.py` geeft ('onderwijsbronnen.rio.client',
    'onderwijsbronnen.rio'), een `__init__.py` is zijn eigen pakket."""
    delen = list(pad.relative_to(src).with_suffix("").parts)
    if delen[-1] == "__init__":
        delen.pop()
        return ".".join(delen), ".".join(delen)
    return ".".join(delen), ".".join(delen[:-1])


def _modulepaden(bron: str, pakket: str | None = None) -> list[tuple[int, str]]:
    """Elk importpad in de bron als (regel, 'a.b.c'); een `from a import b` geeft ook 'a.b'.

    Met `pakket` (het pakket van het bestand) worden relatieve imports omgerekend: in `onderwijsbronnen.rio` wordt
    `from .._kern import lezen` 'onderwijsbronnen._kern' en 'onderwijsbronnen._kern.lezen'. Zonder `pakket` tellen
    relatieve imports niet mee (ze blijven binnen het eigen pakket). Dynamische imports tellen mee zolang het pad een
    letterlijke string is.
    """
    paden: list[tuple[int, str]] = []
    for knoop in ast.walk(ast.parse(bron)):
        if isinstance(knoop, ast.Import):
            paden += [(knoop.lineno, alias.name) for alias in knoop.names]
        elif isinstance(knoop, ast.ImportFrom):
            basis = _basis(knoop, pakket)
            if basis is None:
                continue
            if knoop.module or not knoop.level:
                paden.append((knoop.lineno, basis))
            paden += [(knoop.lineno, f"{basis}.{alias.name}") for alias in knoop.names]
        elif isinstance(knoop, ast.Call) and (pad := _dynamisch_pad(knoop)):
            paden.append((knoop.lineno, pad))
    return paden


def _basis(knoop: ast.ImportFrom, pakket: str | None) -> str | None:
    """Het volledige pad vóór `import` in een `from … import`; None voor een relatieve import zonder `pakket`."""
    if not knoop.level:
        return knoop.module
    if pakket is None:
        return None
    delen = pakket.split(".")
    basis = delen[: len(delen) - (knoop.level - 1)]
    return ".".join([*basis, *([knoop.module] if knoop.module else [])])


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


def laag_van(pad: str) -> str | None:
    """De laag van een importpad: een bronnaam, `_kern`, `bovenlaag`, `oude naam`, of None (buiten het pakket)."""
    delen = pad.split(".")
    if delen[0] in OUDE_NAMEN:
        return "oude naam"
    if delen[0] != PAKKET:
        return None
    if len(delen) == 1 or delen[1] not in (*BRONNEN, KERN):
        return "bovenlaag"
    return delen[1]


def ongeoorloofde_imports(bron: str, pakket: str) -> list[str]:
    """Regels 2 en 3: wat de module in `pakket` (een bron of `_kern`) importeert buiten zichzelf en `_kern`."""
    eigen = laag_van(pakket)
    toegestaan = {eigen, KERN}
    gezien: dict[int, str] = {}
    for regel, pad in _modulepaden(bron, pakket):
        laag = laag_van(pad)
        if laag is not None and laag not in toegestaan:
            gezien.setdefault(regel, f"{pad} ({laag})")
    return [f"regel {regel}: {wat}" for regel, wat in sorted(gezien.items())]


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
    """Regel 4: imports van een intern pakketdeel (underscore in het pad) en `alias._intern`-toegang daartoe."""
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


def chat_gebruikt_oude_naam(bron: str) -> list[str]:
    """Regel 5: imports van de oude pakketnamen `riodata` en `onderwijsdata`."""
    return _eerste_per_regel(_modulepaden(bron), frozenset(OUDE_NAMEN))


def _overtredingen(bestanden: Iterator[Path], controle) -> list[str]:
    return [
        f"{pad.relative_to(ROOT)}, {melding}"
        for pad in bestanden
        for melding in controle(pad.read_text(encoding="utf-8"))
    ]


def _chatbestanden() -> Iterator[Path]:
    return (p for p in _python_bestanden(ROOT) if PAKKETTEN_MAP not in p.parents)


def _bronbestanden(laag: str) -> list[Path]:
    return list(_python_bestanden(BRON_SRC / PAKKET / laag))


# --- de grenzen zelf -------------------------------------------------------------------------------------------


def test_een_pakket_importeert_de_chat_niet():
    chat = chatmodules()
    gevonden = _overtredingen(_python_bestanden(PAKKETTEN_MAP), lambda bron: pakket_importeert_chat(bron, chat))

    assert not gevonden, (
        "Een bronpakket importeert chatcode; het pakket haalt de bron op, het beleid (scope, poorten, etiketten) "
        "blijft in tools/. Verplaats de logica of geef haar als parameter mee:\n" + "\n".join(gevonden)
    )


@pytest.mark.parametrize("laag", [*BRONNEN, KERN])
def test_een_bron_importeert_alleen_zichzelf_en_de_kern(laag):
    gevonden = [
        f"{pad.relative_to(ROOT)}, {melding}"
        for pad in _bronbestanden(laag)
        for melding in ongeoorloofde_imports(pad.read_text(encoding="utf-8"), _module_van(pad, BRON_SRC)[1])
    ]

    assert not gevonden, (
        f"onderwijsbronnen.{laag} importeert buiten zichzelf en _kern. Gedeelde code hoort in _kern, samenvoegen van "
        "bronnen in de bovenlaag (onderwijsbronnen/__init__.py, contract.py):\n" + "\n".join(gevonden)
    )


def test_de_chat_importeert_alleen_de_publieke_api_van_het_pakket():
    gevonden = _overtredingen(_chatbestanden(), lambda bron: chat_gebruikt_niet_publiek(bron, frozenset({PAKKET})))

    assert not gevonden, (
        "De chat gebruikt een intern deel van het bronpakket (pad met underscore). Maak het deel publiek in het "
        "pakket, of gebruik wat het pakket aanbiedt:\n" + "\n".join(gevonden)
    )


def test_de_chat_gebruikt_de_oude_pakketnamen_niet():
    gevonden = _overtredingen(_chatbestanden(), chat_gebruikt_oude_naam)

    assert not gevonden, (
        "De chat importeert `riodata` of `onderwijsdata`; die namen bestaan sinds #914 niet meer. "
        "Gebruik onderwijsbronnen:\n" + "\n".join(gevonden)
    )


# --- de bewaking bewaakt zichzelf ------------------------------------------------------------------------------


def test_het_pakket_en_elke_bron_zijn_gevonden_en_de_scan_is_niet_leeg():
    """Zonder dit slaagt de grenstest ook als `packages/` of een bron verhuist of hernoemd wordt: dan scant hij niets."""
    assert _pakketnamen() == (PAKKET,)
    for laag in (*BRONNEN, KERN):
        assert _bronbestanden(laag), laag
    # Een map met alleen `__pycache__` (een oude checkout van vóór #914) telt niet: er staat geen code in.
    assert [p.name for p in BRON_SRC.iterdir() if p.is_dir() and any(_python_bestanden(p))] == [PAKKET]
    assert sum(1 for _ in _python_bestanden(PAKKETTEN_MAP / PAKKET / "tests")) >= 3
    assert sum(1 for _ in _chatbestanden()) > 100


def test_de_bronnen_in_de_test_zijn_die_van_het_pakket():
    import onderwijsbronnen

    assert set(BRONNEN) == set(onderwijsbronnen.BRONNEN)


def test_de_chatmodules_bevatten_de_kern_en_bestaan_nog():
    chat = chatmodules()

    assert set(CHAT_KERN) <= chat
    for naam in CHAT_KERN:
        assert (ROOT / naam).is_dir(), f"{naam}/ bestaat niet meer: werk CHAT_KERN in tests/test_importgrens.py bij"
    assert {"config", "server", "auth"} <= chat
    assert not chat & {"packages", "tests", PAKKET, *OUDE_NAMEN}


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
        "from onderwijsbronnen import duo",  # eigen pakket: regel 1 gaat over de chat
        "import importlib\nimportlib.import_module(naam)",  # geen letterlijk pad: niet te beoordelen
        "tools = 1\nprint(tools)",
    ],
)
def test_de_scanner_geeft_geen_vals_alarm(bron):
    assert pakket_importeert_chat(bron, chatmodules()) == []


@pytest.mark.parametrize(
    ("bron", "pakket"),
    [
        ("from ..duo import load", "onderwijsbronnen.rio"),
        ("from .. import duo", "onderwijsbronnen.rio"),
        ("def f():\n    from ...duo import notes", "onderwijsbronnen.rio.overgangen"),
        ("from onderwijsbronnen import duo", "onderwijsbronnen.rio"),
        ("import onderwijsbronnen.cbs.client", "onderwijsbronnen.duo"),
        ("from .. import catalog", "onderwijsbronnen.duo"),  # de bovenlaag haalt alle bronnen binnen
        ("from ..contract import get_dataset", "onderwijsbronnen.duo"),
        ("import riodata", "onderwijsbronnen.duo"),
        ("from ..rio import fetch", "onderwijsbronnen._kern"),  # de kern importeert geen bron
        ("import importlib\nimportlib.import_module('onderwijsbronnen.sbb')", "onderwijsbronnen.roa"),
    ],
)
def test_de_scanner_ziet_een_import_tussen_bronnen(bron, pakket):
    assert ongeoorloofde_imports(bron, pakket)


@pytest.mark.parametrize(
    ("bron", "pakket"),
    [
        ("from .client import get", "onderwijsbronnen.rio"),
        ("from .._kern import resolutie", "onderwijsbronnen.rio"),
        ("from .._kern.lezen import lees_csv", "onderwijsbronnen.uwv"),
        ("from .. import sbb", "onderwijsbronnen.sbb"),  # sbb/crebo.py naar zijn eigen bron
        ("from . import broncontract", "onderwijsbronnen._kern"),
        ("import httpx\nfrom importlib.resources import files", "onderwijsbronnen.cbs"),
    ],
)
def test_de_scanner_geeft_geen_vals_alarm_binnen_een_bron(bron, pakket):
    assert ongeoorloofde_imports(bron, pakket) == []


def test_de_scanner_rekent_relatieve_imports_om_vanuit_het_pakket_van_het_bestand():
    assert _module_van(BRON_SRC / "onderwijsbronnen/rio/client.py", BRON_SRC) == (
        "onderwijsbronnen.rio.client",
        "onderwijsbronnen.rio",
    )
    assert _module_van(BRON_SRC / "onderwijsbronnen/duo/__init__.py", BRON_SRC) == (
        "onderwijsbronnen.duo",
        "onderwijsbronnen.duo",
    )
    assert ("1", "onderwijsbronnen._kern.lezen") in [
        (str(r), p) for r, p in _modulepaden("from .._kern import lezen", "onderwijsbronnen.roa")
    ]


@pytest.mark.parametrize(
    "bron",
    [
        "from onderwijsbronnen import _kern",
        "from onderwijsbronnen._kern.verrijking import merge",
        "from onderwijsbronnen.rio import _filtercontract",
        "from onderwijsbronnen import duo\nduo._lees()",
        "import onderwijsbronnen.duo as d\nd._lees()",
        "import onderwijsbronnen\nonderwijsbronnen.duo._lees()",
    ],
)
def test_de_scanner_ziet_gebruik_van_een_intern_pakketdeel(bron):
    assert chat_gebruikt_niet_publiek(bron, frozenset({PAKKET}))


@pytest.mark.parametrize(
    "bron",
    [
        "from onderwijsbronnen import duo, roa\nduo.haal()",
        "from onderwijsbronnen.rio.client import zonder_lijstendpoint",
        "import onderwijsbronnen.duo\nonderwijsbronnen.duo.__name__",  # dunder is geen intern deel
        "from collections import namedtuple\nrecord._asdict()",  # eigen namen met underscore: niet van een pakket
        "from onderwijsbronnen.cbs import validate_selection as _v\n_v({})",
    ],
)
def test_de_scanner_geeft_geen_vals_alarm_op_de_publieke_api(bron):
    assert chat_gebruikt_niet_publiek(bron, frozenset({PAKKET})) == []


@pytest.mark.parametrize(
    ("bron", "fout"),
    [
        ("from riodata import duo", True),
        ("import onderwijsdata", True),
        ("import riodata.duo", True),
        ("from onderwijsbronnen import duo", False),
        ("x = 'from riodata import duo'", False),  # tekst, zoals een opgeslagen snippet in een fixture
    ],
)
def test_de_scanner_ziet_een_oude_pakketnaam(bron, fout):
    assert bool(chat_gebruikt_oude_naam(bron)) is fout
