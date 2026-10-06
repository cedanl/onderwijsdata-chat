"""Een controleprobleem heeft twee lezers: het model en de gebruiker (#215).

Het model krijgt in de herkansing de volledige tekst, met wat het moet doen. De
gebruiker ziet onder de kaart alleen de melding: wat er niet klopt, zonder
"Noem ..." of "Selecteer ...". Een Probleem is een str (de volledige tekst), dus
de herkansing, logs en bestaande vergelijkingen blijven werken.

Een controle die zelf faalt, mag het antwoord niet vervangen (#392): `veilig`
logt de fout onder een fout-ID en gaat door zonder die controle.

Een probleem is hard of zacht (#207, besluit optie C). Hard: het antwoord geeft een
getal of feit dat niet bij de data hoort (getal zonder bron, afgekapte data,
verkeerd jaar of verkeerde instelling). Blijft dat na de herkansing, dan houdt de
app het antwoord in. Zacht (label, teleenheid, woordkeuze): het antwoord blijft,
met een waarschuwing.
"""

from collections.abc import Callable, Iterable
from typing import TypeVar

from core.errors import log_interne_fout

T = TypeVar("T")

# Wat de gebruiker ziet in plaats van een antwoord met een hard probleem; de meldingen staan eronder.
INGEHOUDEN = (
    "Dit antwoord is ingehouden: het klopte na controle niet met de opgehaalde data. "
    "Hieronder staat wat er niet klopte. Stel de vraag opnieuw, of preciezer."
)


class Probleem(str):
    melding: str
    hard: bool = False

    def __new__(cls, melding: str, opdracht: str = ""):
        probleem = super().__new__(cls, f"{melding} {opdracht}".strip())
        probleem.melding = melding
        return probleem


def meldingen(problemen: list[str]) -> list[str]:
    """Wat de gebruiker van de problemen ziet, zonder dubbele."""
    return list(dict.fromkeys(getattr(p, "melding", p) for p in problemen))


def veilig(controle: Callable[..., Iterable[T]], *args) -> list[T]:
    """De problemen van een controle; leeg als de controle zelf een fout geeft."""
    try:
        return list(controle(*args))
    except Exception as exc:
        log_interne_fout(exc, f"controle {getattr(controle, '__name__', controle)}")
        return []


def hard(problemen: Iterable[str]) -> list[Probleem]:
    """Dezelfde problemen, gemarkeerd als hard: blijven ze, dan wordt het antwoord ingehouden."""
    gemarkeerd = []
    for p in problemen:
        probleem = str.__new__(Probleem, p)
        probleem.melding = getattr(p, "melding", p)
        probleem.hard = True
        gemarkeerd.append(probleem)
    return gemarkeerd


def harde(problemen: list[str]) -> list[str]:
    return [p for p in problemen if getattr(p, "hard", False)]
