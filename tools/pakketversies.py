"""Met welke pakketversies een snippet is gemaakt (#714, #888).

Een snippet laadt zijn bron via `onderwijsdata` of `riodata`. Wie hem later draait, installeert wat dan actueel is en
kan een andere uitkomst krijgen. De kop noemt daarom de versies waarop de app draait en een installatieregel die op
precies die code uitkomt. De pakketten staan in deze repo (`core/pakketherkomst.py`): de regel pint ze op de commit
waaruit de app is gebouwd. Niets hier is hardcoded, dus een versiebump verandert de kop zonder codewijziging.
"""

from config import Config
from core.pakketherkomst import installatiespec, pakketversie

# Welke regel in de snippet welk pakket betekent.
_IMPORTS = {"from onderwijsdata import": "onderwijsdata", "from riodata import": "riodata"}


def versiekop(snippet: str) -> list[str]:
    """Twee commentaarregels voor een snippet die een bronpakket gebruikt; leeg als hij er geen gebruikt."""
    pakketten = [(naam, v) for regel, naam in _IMPORTS.items() if regel in snippet and (v := pakketversie(naam))]
    if not pakketten:
        return []
    commit = Config.GIT_COMMIT
    gebruikt = [f"{naam} {versie}" for naam, versie in pakketten]
    if Config.APP_VERSION:
        gebruikt.append(f"app {Config.APP_VERSION}")
    if commit:
        gebruikt.append(f"commit {commit[:8]}")
    installeer = " ".join(f'"{installatiespec(naam, commit)}"' for naam, _ in pakketten)
    # Zonder commit pint de regel niets; zeg dat in plaats van schijnzekerheid te geven.
    opdracht = "Dezelfde versies installeren" if commit else "Commit onbekend, dus de nieuwste versie installeren"
    return [f"# Gemaakt met {', '.join(gebruikt)}.", f"# {opdracht}: pip install {installeer}"]
