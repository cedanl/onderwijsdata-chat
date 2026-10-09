"""De rapporttitel uit code: de vraag van de gebruiker, niet een titel van het model (#416, CH-09).

Vijf keer hetzelfde rapport gaf vijf titels ("Instroom HU", "Eerstejaars Hogeschool Utrecht
2024/25", ...). De vraag staat vast; de titel volgt haar, met de ingestelde instelling erachter.
"""

_MAX_TEKENS = 80
_AFKAPPING = "…"
_SLOTTEKENS = "?!.: \t\n"


def _ingekort(tekst: str) -> str:
    """Hoogstens _MAX_TEKENS tekens, afgebroken op een woordgrens, met een beletselteken."""
    if len(tekst) <= _MAX_TEKENS:
        return tekst
    kort = tekst[: _MAX_TEKENS - len(_AFKAPPING) + 1]
    # Valt de grens midden in een woord, dan gaat dat woord eraf; een te lang woord wordt afgekapt.
    kort = kort.rsplit(" ", 1)[0] if " " in kort else kort[:-1]
    return kort.rstrip(_SLOTTEKENS + ",;") + _AFKAPPING


def rapporttitel(vraag: str, instelling: str | None) -> str:
    """De vraag als titel: één regel, zonder slotteken, met hoofdletter, met de instelling als de vraag haar niet noemt."""
    tekst = " ".join((vraag or "").split()).rstrip(_SLOTTEKENS)
    if not tekst:
        return "Rapport"
    tekst = _ingekort(tekst[0].upper() + tekst[1:])
    instelling = " ".join((instelling or "").split())
    if instelling and instelling.casefold() not in tekst.casefold():
        return f"{tekst} – {instelling}"
    return tekst
