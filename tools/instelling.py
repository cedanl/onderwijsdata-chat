"""Instellingen in de vraag en in de data, in code in plaats van door het model (#143).

Het model koos zelf een instellingscode en koos één keer 30TX (Aeres Hogeschool)
voor Hogeschool Utrecht (25DW). Welke instelling de vraag noemt, volgt uit de
namen in de geladen data en de vaste afkortingen; welke een selectie bevat, uit
de codekolom.
"""

import re

import pandas as pd

from data.instellingen import ALIASSEN

# DUO: ho-bestanden gebruiken de actuele code en naam, mbo-bestanden de gewone.
_KOLOMPAREN = {
    "INSTELLINGSCODE_ACTUEEL": "INSTELLINGSNAAM_ACTUEEL",
    "INSTELLINGSCODE": "INSTELLINGSNAAM",
}


def codekolom(kolommen) -> str | None:
    return next((code for code, naam in _KOLOMPAREN.items() if code in kolommen and naam in kolommen), None)


def dekking(df: pd.DataFrame, kolom: str | None) -> tuple[str, ...] | None:
    """De instellingscodes in `df`; () bij een lege selectie, None als onbekend."""
    if not kolom or kolom not in df.columns:
        return None
    return tuple(sorted(str(c) for c in df[kolom].dropna().unique()))


def namen(df: pd.DataFrame, kolom: str) -> dict[str, str]:
    """Code → naam zoals de brondata die noemt."""
    paar = df[[kolom, _KOLOMPAREN[kolom]]].dropna().drop_duplicates(kolom)
    return {str(code): str(naam) for code, naam in paar.itertuples(index=False)}


def _is_afkorting(alias: str) -> bool:
    # HU, HvA, TU Delft: geen losse woorden als "Wageningen" of "Radboud", die ook
    # een plaats of iets anders kunnen zijn.
    return sum(c.isupper() for c in alias) >= 2


def genoemde(vraag: str, bekende: dict[str, str]) -> set[str]:
    """Codes van de instellingen uit `bekende` (code → naam) die de vraag noemt.

    Een volledige naam telt ongeacht hoofdletters; een afkorting alleen letterlijk
    en als los woord. Een langere naam gaat voor: "Universiteit Utrecht" is geen
    treffer voor een kortere naam die erin zou zitten.
    """
    per_naam = {naam.lower(): code for code, naam in bekende.items()}
    patronen = [(re.compile(rf"\b{re.escape(naam)}\b", re.IGNORECASE), code) for naam, code in per_naam.items()]
    for naam, aliassen in ALIASSEN.items():
        if (code := per_naam.get(naam.lower())) is not None:
            patronen += [(re.compile(rf"(?<!\w){re.escape(a)}(?!\w)"), code) for a in aliassen if _is_afkorting(a)]

    treffers = sorted(
        ((m.start(), m.end(), code) for patroon, code in patronen for m in patroon.finditer(vraag)),
        key=lambda t: t[0] - t[1],  # langste eerst
    )
    bezet: list[tuple[int, int]] = []
    gevonden: set[str] = set()
    for start, eind, code in treffers:
        if any(start < e and s < eind for s, e in bezet):
            continue
        bezet.append((start, eind))
        gevonden.add(code)
    return gevonden
