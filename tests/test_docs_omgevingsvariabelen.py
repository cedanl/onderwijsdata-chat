"""Elke omgevingsvariabele die de app-code leest, staat ergens in docs/ (audit 26-11-2026, "env-vars zonder docs").

Alleen wat de code letterlijk met `os.getenv(...)` of `os.environ[...]` leest; variabelen die een helper samenstelt
(zoals `_namenlijst("X")`) ziet deze test niet. De configuratiepagina is de plek voor instellingen van een beheerder;
sommige staan bewust bij hun onderwerp (APP_URL bij MCP, POSTGRES_POOL_SIZE bij hosting).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPEN = ("agent", "auth", "core", "data", "persistence", "routes", "tools")
BESTANDEN = ("config.py", "server.py", "mcp_server.py", "health.py", "logging_config.py", "frontend_static.py")
LEZEN = re.compile(r"""os\.(?:getenv|environ(?:\.get)?)\(?\[?\s*["']([A-Z][A-Z0-9_]{3,})["']""")


def _gelezen() -> set[str]:
    bestanden = [ROOT / b for b in BESTANDEN] + [p for m in MAPPEN for p in (ROOT / m).rglob("*.py")]
    return {naam for p in bestanden if p.exists() for naam in LEZEN.findall(p.read_text(encoding="utf-8"))}


def test_de_regex_vindt_variabelen():
    assert len(_gelezen()) > 30  # een stille regexbreuk zou de test leeg laten slagen


def test_elke_gelezen_omgevingsvariabele_staat_in_de_docs():
    docs = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs").rglob("*.md"))

    ontbreekt = sorted(naam for naam in _gelezen() if naam not in docs)

    assert not ontbreekt, f"gelezen door de code, nergens in docs/: {ontbreekt}"
