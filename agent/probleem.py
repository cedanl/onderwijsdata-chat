"""Een controleprobleem heeft twee lezers: het model en de gebruiker (#215).

Het model krijgt in de herkansing de volledige tekst, met wat het moet doen. De
gebruiker ziet onder de kaart alleen de melding: wat er niet klopt, zonder
"Noem ..." of "Selecteer ...". Een Probleem is een str (de volledige tekst), dus
de herkansing, logs en bestaande vergelijkingen blijven werken.

Een controle die zelf faalt, mag het antwoord niet vervangen (#392): `veilig`
logt de fout onder een fout-ID en gaat door zonder die controle.
"""

from collections.abc import Callable, Iterable

from core.errors import log_interne_fout


class Probleem(str):
    melding: str

    def __new__(cls, melding: str, opdracht: str = ""):
        probleem = super().__new__(cls, f"{melding} {opdracht}".strip())
        probleem.melding = melding
        return probleem


def meldingen(problemen: list[str]) -> list[str]:
    """Wat de gebruiker van de problemen ziet, zonder dubbele."""
    return list(dict.fromkeys(getattr(p, "melding", p) for p in problemen))


def veilig(controle: Callable[..., Iterable[str]], *args) -> list[str]:
    """De problemen van een controle; leeg als de controle zelf een fout geeft."""
    try:
        return list(controle(*args))
    except Exception as exc:
        log_interne_fout(exc, f"controle {getattr(controle, '__name__', controle)}")
        return []
