"""Schooljaren: van de vraag naar de broncode en terug (#187).

Een schooljaar heet naar zijn startjaar: 2025/26 is CBS-periode 2025SJ00 en
DUO STUDIEJAAR 2025 (peildatum 1 oktober 2025). Het model vertaalde dat zelf en
koos daarbij soms het jaar ervoor; hier gebeurt het in code, op één plek.
"""

import re

import pandas as pd

# 2025/26, 2025-2026, 2025/'26, 2025–26. Een los "2025" is dubbelzinnig en telt niet.
_SCHOOLJAAR = re.compile(r"(?<!\d)(20\d{2})\s*[/\-–]\s*'?(\d{4}|\d{2})(?!\d)")
_CBS_SCHOOLJAAR = re.compile(r"^(\d{4})SJ\d{2}$")
_DUO_PERIODEKOLOMMEN = ("STUDIEJAAR", "JAAR")


def gevraagde_schooljaren(tekst: str) -> set[int]:
    """Startjaren van de schooljaren die de tekst eenduidig noemt."""
    jaren: set[int] = set()
    for start, eind in _SCHOOLJAAR.findall(tekst):
        begin = int(start)
        volgend = begin + 1 if len(eind) == 4 else (begin + 1) % 100
        if int(eind) == volgend:
            jaren.add(begin)
    return jaren


def label(startjaar: int) -> str:
    return f"{startjaar}/{(startjaar + 1) % 100:02d}"


def labels(startjaren) -> list[str]:
    return [label(j) for j in startjaren or ()]


def broncode(bron: str, startjaar: int) -> str:
    """Hoe de bron dit schooljaar noemt, voor in een foutmelding aan het model."""
    return f"{startjaar}SJ00" if bron == "cbs" else f"STUDIEJAAR={startjaar}"


def startjaar(bron: str, waarde) -> int | None:
    """Startjaar van een periodewaarde; None als het geen schooljaar is (bijv. CBS-kalenderjaar)."""
    if bron == "cbs":
        match = _CBS_SCHOOLJAAR.match(str(waarde).strip())
        return int(match.group(1)) if match else None
    try:
        return int(float(waarde))
    except (TypeError, ValueError):
        return None


def duo_periodekolom(kolommen) -> str | None:
    return next((k for k in _DUO_PERIODEKOLOMMEN if k in kolommen), None)


def dekking(df: pd.DataFrame, bron: str, kolom: str | None) -> tuple[int, ...] | None:
    """De schooljaren (startjaren) in `df`; () bij een lege selectie, None als onbekend."""
    if not kolom or kolom not in df.columns:
        return None
    if df.empty:
        return ()
    jaren = {startjaar(bron, v) for v in df[kolom].dropna().unique()} - {None}
    return tuple(sorted(jaren)) if jaren else None
