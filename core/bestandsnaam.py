"""De naamregel voor een bestandsnaam die uit tekst van de gebruiker komt (#1124, #1125).

Een rapporttitel, een catalogustitel of een grafiektitel wordt een deel van een bestandsnaam en van de header
`Content-Disposition`. Eén regel voor browser en server: `frontend/src/bestandsnaam.js` is de tweeling van dit
bestand en `tests/fixtures/bestandsnamen.json` houdt ze gelijk.
"""

import re
import unicodedata

# Een rapportnaam is hoogstens zoveel tekens vóór de extensie: een bestandssysteem staat 255 bytes toe, en de naam is
# door de regel hieronder alleen ASCII, dus tekens zijn bytes.
RAPPORT_MAX = 120
RAPPORT_ZONDER_TITEL = "rapport"


def bestandsdeel(tekst: str | None, maximum: int | None = None) -> str:
    """Veilig voor een bestandsnaam: accenten vallen weg (é wordt e), elke reeks andere tekens (spatie, leesteken, een
    emoji) wordt één underscore. Met `maximum` hoogstens zoveel tekens, afgekapt op een woordgrens; zonder
    woordgrens binnen het maximum midden in het woord."""
    zonder_accenten = "".join(c for c in unicodedata.normalize("NFD", str(tekst or "")) if not "̀" <= c <= "ͯ")
    deel = re.sub(r"[^A-Za-z0-9]+", "_", zonder_accenten).strip("_")
    if maximum is None or len(deel) <= maximum:
        return deel
    knip = deel[:maximum]
    if deel[maximum] != "_" and (grens := knip.rfind("_")) > 0:
        knip = knip[:grens]
    return knip.rstrip("_")


def rapportdeel(titel: str | None) -> str:
    """De naam van een rapportdownload zonder extensie (HTML, Markdown en Word): de titel, ingekort, of `rapport`."""
    return bestandsdeel(titel, RAPPORT_MAX) or RAPPORT_ZONDER_TITEL
