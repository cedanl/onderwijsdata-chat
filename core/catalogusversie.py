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


def _cbs_manifest() -> dict | None:
    """Welke CBS-catalogus de package werkelijk levert (#370): revisie, consistentie en versheid.

    Uit `catalog_manifest()` van de package, volledig offline. None bij een package zonder
    manifest of een artefact dat niet te lezen is: /version blijft dan werken.
    """
    try:
        from onderwijsdata import catalog_manifest  # hier en niet bovenaan: zie arbeidsmarktversie

        manifest = catalog_manifest()
    except Exception:
        return None
    bouw = manifest.get("bouw") or {}
    return {
        "catalogusrevisie": manifest.get("catalogusrevisie"),
        "consistent": manifest.get("consistent"),
        "aantal": manifest.get("aantal"),
        "laatste_succesvolle_controle": bouw.get("laatste_succesvolle_controle"),
        "versheid": bouw.get("versheid"),
    }


@cache
def catalogusversie() -> list[dict]:
    pakketten = [_pakket(naam) for naam in PAKKETTEN]
    for pakket in pakketten:
        if pakket["pakket"] == "onderwijsdata":
            pakket["manifest"] = _cbs_manifest()
    return pakketten


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
