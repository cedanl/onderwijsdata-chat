"""Het versielabel van de app: één plek voor `/version`, MCP `serverInfo.version` en het manifest van een rapport (#1105).

Een release is wat het chart zegt (`APP_VERSION`, de chartversie = de tag). Zonder die waarde draait de code niet als
release: `make dev` of de MCP-server via stdio draait code die honderden commits na de laatste tag ligt. Het label is
dan de versie uit `pyproject.toml` met `+dev` en, als `git` de commit van de werkboom kent, de korte commit
(`2.8.0+dev.5e29298b`), zodat het nooit gelijk is aan een release. De build-metadata van SemVer sorteert niet mee.

`commit` in `/version` blijft `GIT_COMMIT` uit de image-build: alleen die commit mag in een snippet als installatieregel
(`core/pakketherkomst.py`), en een werkboom met lokale wijzigingen staat niet op de spiegel.
"""

import subprocess
import tomllib
from functools import cache
from pathlib import Path

from core.pakketherkomst import korte_commit

_WORTEL = Path(__file__).resolve().parent.parent
_PYPROJECT = _WORTEL / "pyproject.toml"
_GIT_TIMEOUT = 2


@cache
def _werkboom_commit() -> str | None:
    """De volledige HEAD-commit van de repo waar de app uit draait; None zonder git of zonder repo."""
    try:
        uit = subprocess.run(
            ["git", "-C", str(_WORTEL), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return uit.stdout.strip() or None


def app_versie(release: str | None) -> str:
    """`release` (APP_VERSION) als de omgeving een release meldt, anders het ontwikkellabel `<pyproject>+dev[.<commit>]`."""
    if release:
        return release
    with open(_PYPROJECT, "rb") as bestand:
        versie = tomllib.load(bestand)["project"]["version"]
    commit = korte_commit(_werkboom_commit())
    return f"{versie}+dev.{commit}" if commit else f"{versie}+dev"
