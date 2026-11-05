"""Welke catalogusdata een omgeving draait (#361).

De CBS- en RIO/DUO-catalogus komen uit het pakket `onderwijsbronnen` (tot #910 de packages `onderwijsdata` en
`riodata`). Die waren git-dependencies, met de commit uit uv.lock; sinds #885 is het een workspace-lid (packages/), dat
uit dezelfde commit komt als de app.
Hun metadata heeft geen vcs-commit meer, dus noemt /version per pakket de commit van de chat-repo waaruit het image is
gebouwd (#888, `core/pakketherkomst.py`). /version noemde alleen de app-commit (#231), zodat niet te zien was dat
playground een catalogus-commit achter liep. Dit leest de gebouwde revisie uit de geïnstalleerde
package-metadata: geen netwerk, geen GitHub-HEAD.

UWV en ROA zitten niet als eigen package in de catalogus; hun dataversie staat in de statische
catalogusrecords van onderwijsbronnen (CH-46). Ook dat zonder download: de app laadt die data pas bij het
eerste gebruik.
"""

from functools import cache

from core.pakketherkomst import pakketversie

# Importnaam van de package, zoals in packages/<naam>/pyproject.toml.
PAKKETTEN = ("onderwijsbronnen",)


def _pakket(naam: str, commit: str | None) -> dict:
    versie = pakketversie(naam)
    return {"pakket": naam, "versie": versie, "commit": commit if versie else None}


def _cbs_manifest() -> dict | None:
    """Welke CBS-catalogus de package werkelijk levert (#370): revisie, consistentie en versheid.

    Uit `catalog_manifest()` van de package, volledig offline. None bij een package zonder
    manifest of een artefact dat niet te lezen is: /version blijft dan werken.
    """
    try:
        from onderwijsbronnen.cbs import catalog_manifest  # hier en niet bovenaan: zie arbeidsmarktversie

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
def catalogusversie(commit: str | None = None) -> list[dict]:
    """Per pakket de versie en `commit`: de chat-commit waaruit het pakket komt (None als de build hem niet kent)."""
    pakketten = [_pakket(naam, commit) for naam in PAKKETTEN]
    for pakket in pakketten:
        if pakket["pakket"] == "onderwijsbronnen":
            pakket["manifest"] = _cbs_manifest()
    return pakketten


def _arbeidsmarktbron(bron: str, dataset: str, records: list[dict], sleutel: str) -> dict:
    """De periode uit het catalogusrecord van `dataset`, letterlijk; None als het record ontbreekt."""
    periode = next((r.get("periode") for r in records if r.get(sleutel) == dataset), None)
    return {"bron": bron, "dataset": dataset, "periode": periode}


@cache
def arbeidsmarktversie() -> list[dict]:
    # Hier en niet bovenaan: server.py importeert deze module vóór de logging-setup, en tools trekt pandas mee.
    from onderwijsbronnen import roa, uwv

    from tools.arbeidsmarkt import ROA_ID, UWV_ID

    return [
        _arbeidsmarktbron("UWV", UWV_ID, uwv.catalog(live=False), "_ckan_id"),
        _arbeidsmarktbron("ROA", ROA_ID, roa.catalog(), "_roa_id"),
    ]
