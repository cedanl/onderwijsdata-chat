"""De versie van de app: één bron voor /version, het OpenAPI-schema, het manifest en de MCP-server (#1157)."""

import tomllib
from pathlib import Path

from config import Config

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def app_versie() -> str:
    """De release uit het chart (APP_VERSION), anders pyproject.toml: het image wordt op main gebouwd, dus alleen het
    chart weet welke release er draait."""
    if Config.APP_VERSION:
        return Config.APP_VERSION
    with open(_PYPROJECT, "rb") as bestand:
        return tomllib.load(bestand)["project"]["version"]
