"""De versie van een geladen DUO-bestand (#717), uit `df.attrs["bron"]` van riodata (vanaf 0.7.0).

DUO vermeldt per bestand wanneer het is vervangen (`last_modified`, UTC) en een md5. riodata neemt die over en zet
er de md5 van de geladen bytes naast. Het peilmoment komt in de bronregel en het manifest, zoals de peildatum van UWV
en de stand van RIO. De bronhash is de md5 van het bestand zelf: gelijk aan wat DUO opgeeft als het geladen bestand
het geregistreerde is, en te narekenen met `md5sum` op een download. Hij vervangt voor DUO de eigen inhoudshash (#715).

Een datastore-dump (15 van de 288 DUO-resources) heeft geen datum; een oudere riodata heeft geen van beide. Dan
valt de app terug op niets: geen fout.
"""

from collections.abc import Mapping
from datetime import datetime

_MD5_LENGTE = 32


def peilmoment(bron: Mapping) -> str | None:
    """'versie van 08-04-2026': de dag (UTC, zoals DUO hem geeft) waarop DUO het bestand verving; None zonder datum."""
    waarde = bron.get("last_modified")
    if not isinstance(waarde, str):
        return None
    try:
        dag = datetime.fromisoformat(waarde).date()
    except ValueError:
        return None
    return f"versie van {dag:%d-%m-%Y}"


def bronhash(bron: Mapping) -> str | None:
    """De md5 van het geladen bestand; None als riodata hem niet levert of hij geen md5 is."""
    waarde = bron.get("md5")
    if isinstance(waarde, str) and len(waarde) == _MD5_LENGTE and all(c in "0123456789abcdef" for c in waarde):
        return waarde
    return None
