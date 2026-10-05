"""Welke catalogusdata een omgeving draait (#361).

De chat installeert de CBS- en RIO/DUO-catalogus als git-dependencies; uv.lock bepaalt de
commit. /version noemde alleen de app-commit (#231), zodat niet te zien was dat playground
een catalogus-commit achter liep. Dit leest de gebouwde revisie uit de geïnstalleerde
package-metadata: geen netwerk, geen GitHub-HEAD.
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
