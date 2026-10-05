"""Gepubliceerde afronding van CBS-tabellen: geen schijnprecisie (#352).

CBS rondt sommige tabellen af; bij 85423NED en 85422NED staat in TableInfos.Description
"De aantallen in de tabel zijn afgerond op 10-tallen." Een som van afgeronde details
of een verschil daartussen lijkt dan exacter dan de bron. De regel komt uit die
beschrijving, niet uit een lijst in de prompt, en reist via KeyMeta.afronding mee
naar query, KPI, grafiek, export en het blok onder het antwoord.
"""

import re

from . import store

_WOORDEN = {"tien": 10, "honderd": 100, "duizend": 1000}
_REGEL = re.compile(r"afgerond op (\d+|tien|honderd|duizend)[- ]?tallen", re.IGNORECASE)

ONBEKEND = (
    "De CBS-tabelbeschrijving kon niet worden opgehaald: of de aantallen afgerond zijn is onbekend. "
    "Presenteer sommen en verschillen daarom niet als exact."
)


def uit_beschrijving(tekst: str) -> int | None:
    """De afrondingseenheid die de tabelbeschrijving noemt; None als ze er geen noemt."""
    if not (m := _REGEL.search(tekst or "")):
        return None
    eenheid = m.group(1).lower()
    return int(eenheid) if eenheid.isdigit() else _WOORDEN[eenheid]


def noot(eenheid: int) -> str:
    return (
        f"De aantallen zijn door CBS afgerond op {eenheid}-tallen: een som, verschil of percentage "
        "daarvan is niet exact. Gebruik waar het kan een gepubliceerd totaal."
    )


def van_key(key: str) -> str | None:
    """De noot voor de data achter `key`, ook voor een selectie daaruit."""
    known = store.meta(key)
    return noot(known.afronding) if known and known.afronding else None
