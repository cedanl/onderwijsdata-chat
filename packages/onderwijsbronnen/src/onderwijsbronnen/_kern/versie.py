"""Eén versiebron: pyproject.toml, via de geïnstalleerde distributie `onderwijsbronnen`."""

from importlib.metadata import PackageNotFoundError, version

try:
    VERSIE = version("onderwijsbronnen")
except PackageNotFoundError:  # broncode zonder installatie
    VERSIE = "0+onbekend"
