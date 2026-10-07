"""Een bronkolom en haar codes als leesbare tekst voor grafiekassen en legenda (#405, #418).

Een titel uit de bron gaat voor: CBS geeft per kolom een titel in DataProperties
(MboStudenten_1 is 'Mbo-studenten'), zie ``cbs.kolomtitels``. Zonder titel volgt de naam
dezelfde regel als de tabelkop in de frontend (``frontend/src/components/KolomKop.jsx``,
#222): HOOFDLETTERS_MET_UNDERSCORE en losse woorden in hoofdletters vanaf vier letters
worden zinsnotatie, afkortingen blijven in hoofdletters. Wie de regel of de afkortingen
wijzigt, wijzigt beide.
"""

import re
from collections.abc import Mapping

from .duo import OPLEIDINGSVORM_DATASETS, OPLEIDINGSVORMEN

# Kortere woorden in hoofdletters zijn meestal codes (VT, MAN): die blijven staan.
_BRONKOLOM = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|[A-Z]{4,}")
# De labelkolom naast een code: STUDIEJAAR_LABEL (DUO, #240), Perioden_label (CBS, #163).
_LABELKOLOM = re.compile(r"(.+)_(?:LABEL|label)")

_AFKORTINGEN = frozenset(
    {
        "AOC",
        "BBL",
        "BOL",
        "BRIN",
        "CBS",
        "CREBO",
        "CROHO",
        "DUO",
        "HBO",
        "HO",
        "ID",
        "ISAT",
        "MBO",
        "RIO",
        "ROC",
        "VO",
        "WO",
    }
)

# DUO schrijft geslacht in hoofdletters; dat zijn woorden, geen codes.
_GESLACHT = {"MAN": "Man", "VROUW": "Vrouw", "ONBEKEND": "Onbekend"}


def kolomlabel(kop: str, titels: Mapping[str, str] | None = None) -> str:
    titels = titels or {}
    if kop in titels:
        return titels[kop]
    # Een labelkolom heet naar wat hij toont: de titel of naam van haar code.
    if m := _LABELKOLOM.fullmatch(kop):
        return titels.get(m.group(1)) or kolomlabel(m.group(1))
    if not _BRONKOLOM.fullmatch(kop):
        return kop
    woorden = kop.split("_")
    return " ".join(
        w if w in _AFKORTINGEN else (w.capitalize() if i == 0 else w.lower()) for i, w in enumerate(woorden)
    )


def waardelabels(kolom: str | None, dataset: str | None) -> dict[str, str]:
    """Code → woord voor de waarden van `kolom`, alleen waar de bron de betekenis geeft."""
    if kolom == "OPLEIDINGSVORM" and dataset in OPLEIDINGSVORM_DATASETS:
        # Elders betekent OPLEIDINGSVORM iets anders (#371): daar geen vertaling.
        return {code: vorm.capitalize() for code, vorm in OPLEIDINGSVORMEN.items()}
    if kolom == "GESLACHT":
        return _GESLACHT
    return {}


def leesbaar(waarden: list, labels: Mapping[str, str]) -> list:
    """De waarden met hun woord; wat geen label heeft blijft staan."""
    return [labels.get(w, w) if isinstance(w, str) else w for w in waarden]
