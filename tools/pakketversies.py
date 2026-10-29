"""Met welke pakketversies een snippet is gemaakt (#714).

Een snippet laadt zijn bron via `onderwijsdata` of `riodata`. Wie hem later draait, installeert wat dan actueel is en
kan een andere uitkomst krijgen. De kop noemt daarom de versies waarop de app draait en hoe je ze installeert, uit de
metadata van het geïnstalleerde pakket (`direct_url.json` bij een git-installatie): niets hier is hardcoded, dus een
versiebump verandert de kop zonder codewijziging.
"""

import json
from functools import cache
from importlib import metadata

from config import Config

# Welke regel in de snippet welk pakket betekent.
_IMPORTS = {"from onderwijsdata import": "onderwijsdata", "from riodata import": "riodata"}


@cache
def _pakket(naam: str) -> tuple[str, str] | None:
    """(weergave, pip-spec) van een geïnstalleerd pakket; None als het niet te vinden is."""
    try:
        dist = metadata.distribution(naam)
    except metadata.PackageNotFoundError:
        return None
    try:
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
    except ValueError:
        direct = {}
    vcs = direct.get("vcs_info") or {}
    commit = vcs.get("commit_id")
    if direct.get("url") and commit:
        gevraagd = vcs.get("requested_revision") or commit[:8]
        return f"{naam} {dist.version} ({gevraagd})", f"{naam} @ git+{direct['url']}@{commit}"
    return f"{naam} {dist.version}", f"{naam}=={dist.version}"


def versiekop(snippet: str) -> list[str]:
    """Twee commentaarregels voor een snippet die een bronpakket gebruikt; leeg als hij er geen gebruikt."""
    pakketten = [p for regel, naam in _IMPORTS.items() if regel in snippet and (p := _pakket(naam))]
    if not pakketten:
        return []
    gebruikt = [weergave for weergave, _ in pakketten]
    if Config.APP_VERSION:
        gebruikt.append(f"app {Config.APP_VERSION}")
    installeer = " ".join(f'"{spec}"' for _, spec in pakketten)
    return [f"# Gemaakt met {', '.join(gebruikt)}.", f"# Dezelfde versies installeren: pip install {installeer}"]
