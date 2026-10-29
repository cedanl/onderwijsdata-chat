"""De rapporttitel uit code: de vraag van de gebruiker, niet een titel van het model (#416, CH-09).

Vijf keer hetzelfde rapport gaf vijf titels ("Instroom HU", "Eerstejaars Hogeschool Utrecht
2024/25", ...). De vraag staat vast; de titel volgt haar, met de ingestelde instelling erachter.
"""

from core import persoonsgegevens

_MAX_TEKENS = 80
_AFKAPPING = "…"
_SLOTTEKENS = "?!.: \t\n"
# De titel staat in het werkboek, de export, de browsertab en de geschiedenis: nooit met een BSN,
# e-mailadres of telefoonnummer uit de vraag erin (#478).
TITEL_ZONDER_PERSOONSGEGEVENS = "Rapport (persoonsgegevens weggelaten)"


# De onderzoeksvraag die de gebruiker bevestigde (#750) staat voluit in het rapport, ook zonder persoonsgegevens.
VRAAG_ZONDER_PERSOONSGEGEVENS = "Onderzoeksvraag weggelaten: ze bevatte persoonsgegevens."


def rapportvraag(vraag: str) -> str:
    """De bevestigde onderzoeksvraag zoals het rapport haar toont: één regel, zonder BSN, e-mailadres of telefoonnummer."""
    tekst = " ".join((vraag or "").split())
    return VRAAG_ZONDER_PERSOONSGEGEVENS if persoonsgegevens.bevat(tekst) else tekst


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
    tekst = TITEL_ZONDER_PERSOONSGEGEVENS if persoonsgegevens.bevat(tekst) else _ingekort(tekst[0].upper() + tekst[1:])
    instelling = " ".join((instelling or "").split())
    if instelling and instelling.casefold() not in tekst.casefold():
        return f"{tekst} – {instelling}"
    return tekst
