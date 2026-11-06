"""Met welke pakketversies een snippet is gemaakt (#714, #888).

Een snippet laadt zijn bron via `onderwijsbronnen` (#910). Wie hem later draait, installeert wat dan actueel is en
kan een andere uitkomst krijgen. De kop noemt daarom de versies waarop de app draait en een installatieregel die op
precies die code uitkomt. De pakketten staan in deze repo (`core/pakketherkomst.py`): de regel pint ze op de commit
waaruit de app is gebouwd. Niets hier is hardcoded, dus een versiebump verandert de kop zonder codewijziging.
"""

from config import Config
from core.pakketherkomst import installatiespec, pakketversie

# Welke regel in de snippet welk pakket betekent: `from onderwijsbronnen import duo`, `from onderwijsbronnen.cbs import`.
_IMPORTS = {"from onderwijsbronnen": "onderwijsbronnen"}

# De extras die een snippet van het pakket vraagt (#971): `analyse` geeft pandas (elke snippet leest een DataFrame) en
# openpyxl (de financiën van DUO en de crebolijst van SBB lezen Excel). Zonder extras faalde de regel bij `load`.
_EXTRAS = {"onderwijsbronnen": ("analyse",)}

# Wat een snippet verder importeert en geen afhankelijkheid van het pakket is: een grafiek gebruikt plotly (numpy komt
# met pandas mee). Ongepind: de app pint plotly niet in de kop, en de grafiek hangt niet af van de bronversie.
_LOSSE_PAKKETTEN = {"import plotly": "plotly"}


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
    installeer = " ".join(
        [
            *(f'"{installatiespec(naam, commit, _EXTRAS.get(naam, ()))}"' for naam, _ in pakketten),
            *(pakket for regel, pakket in _LOSSE_PAKKETTEN.items() if regel in snippet),
        ]
    )
    # Zonder commit pint de regel niets; zeg dat in plaats van schijnzekerheid te geven.
    opdracht = "Dezelfde versies installeren" if commit else "Commit onbekend, dus de nieuwste versie installeren"
    return [f"# Gemaakt met {', '.join(gebruikt)}.", f"# {opdracht}: pip install {installeer}"]
