"""Welke catalogusdata een omgeving draait (#361).

De chat installeert de CBS- en RIO/DUO-catalogus als git-dependencies; uv.lock bepaalt de
commit. /version noemde alleen de app-commit (#231), zodat niet te zien was dat playground
een catalogus-commit achter liep. Dit leest de gebouwde revisie uit de geïnstalleerde
package-metadata: geen netwerk, geen GitHub-HEAD.

UWV en ROA zitten niet als eigen package in de catalogus; hun dataversie staat in de statische
catalogusrecords van riodata (CH-46). Ook dat zonder download: de app laadt die data pas bij het
eerste gebruik.
"""

import json
from functools import cache
from importlib import metadata

# Importnaam van de package -> repository, zoals in pyproject.toml.
PAKKETTEN = ("onderwijsdata", "riodata")


def _pakket(naam: str) -> dict:
    try:
        dist = metadata.distribution(naam)
    except metadata.PackageNotFoundError:
        return {"pakket": naam, "versie": None, "commit": None}
    vcs = (json.loads(dist.read_text("direct_url.json") or "{}")).get("vcs_info") or {}
    return {"pakket": naam, "versie": dist.version, "commit": vcs.get("commit_id")}


@cache
def catalogusversie() -> list[dict]:
    return [_pakket(naam) for naam in PAKKETTEN]


def _arbeidsmarktbron(bron: str, dataset: str, records: list[dict], sleutel: str) -> dict:
    """De periode uit het catalogusrecord van `dataset`, letterlijk; None als het record ontbreekt."""
    periode = next((r.get("periode") for r in records if r.get(sleutel) == dataset), None)
    return {"bron": bron, "dataset": dataset, "periode": periode}


@cache
def arbeidsmarktversie() -> list[dict]:
    # Hier en niet bovenaan: server.py importeert deze module vóór de logging-setup, en tools trekt pandas mee.
    from riodata import roa, uwv

    from tools.arbeidsmarkt import ROA_ID, UWV_ID

    return [
        _arbeidsmarktbron("UWV", UWV_ID, uwv.catalog(live=False), "_ckan_id"),
        _arbeidsmarktbron("ROA", ROA_ID, roa.catalog(), "_roa_id"),
    ]
