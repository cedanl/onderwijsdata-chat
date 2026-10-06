"""Een bronkolomnaam als leesbaar label voor grafiekassen en legenda (#405, audit 14 §3.7).

Zelfde regel als de tabelkop in de frontend (``frontend/src/components/KolomKop.jsx``, #222):
alleen namen in de vorm HOOFDLETTERS_MET_UNDERSCORE worden zinsnotatie, afkortingen blijven
in hoofdletters. Wie de regel of de afkortingen wijzigt, wijzigt beide.
"""

import re

_BRONKOLOM = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

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


def kolomlabel(kop: str) -> str:
    if not _BRONKOLOM.fullmatch(kop):
        return kop
    # Een afgeleide labelkolom (STUDIEJAAR_LABEL, #240) heet naar wat hij toont.
    woorden = kop.removesuffix("_LABEL").split("_")
    return " ".join(
        w if w in _AFKORTINGEN else (w.capitalize() if i == 0 else w.lower()) for i, w in enumerate(woorden)
    )
