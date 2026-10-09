"""Een controleprobleem heeft twee lezers: het model en de gebruiker (#215).

Het model krijgt in de herkansing de volledige tekst, met wat het moet doen. De
gebruiker ziet onder de kaart alleen de melding: wat er niet klopt, zonder
"Noem ..." of "Selecteer ...". Een Probleem is een str (de volledige tekst), dus
de herkansing, logs en bestaande vergelijkingen blijven werken.

Een controle die zelf faalt, mag het antwoord niet vervangen (#392): `veilig`
logt de fout onder een fout-ID en gaat door. Stil akkoord is het niet (#419): de
gebruiker ziet dat het antwoord op dat punt niet gecontroleerd is. Dat probleem is
zacht (er is niets fout bevonden) en geeft geen herkansing (het model kan het niet
herstellen).

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
    niet_gecontroleerd: bool = False
    controle: str | None = None  # welke controle het vond: voor het log en de afvuurfrequentie (CH-01)

    def __new__(cls, melding: str, opdracht: str = ""):
        probleem = super().__new__(cls, f"{melding} {opdracht}".strip())
        probleem.melding = melding
        return probleem


def meldingen(problemen: list[str]) -> list[str]:
    """Wat de gebruiker van de problemen ziet, zonder dubbele."""
    return list(dict.fromkeys(getattr(p, "melding", p) for p in problemen))


def niet_gecontroleerd(fout_id: str) -> Probleem:
    """Een controle kon niet draaien: zacht, want er is niets fout bevonden, maar ook niets getoetst."""
    probleem = Probleem(
        f"Op één punt niet gecontroleerd: een controle kon niet draaien (fout-ID {fout_id}), "
        "dus daar is de tekst niet aan de data getoetst."
    )
    probleem.niet_gecontroleerd = True
    return probleem


def _van(probleem, controle: str) -> Probleem:
    """Het probleem als Probleem, met de naam van de controle die het vond."""
    if not isinstance(probleem, Probleem):
        probleem = Probleem(str(probleem))
    if probleem.controle is None:
        probleem.controle = controle
    return probleem


def veilig(controle: Callable[..., Iterable[T]], *args) -> list[Probleem]:
    """De problemen van een controle; kan de controle zelf niet draaien, dan één niet-gecontroleerd-probleem."""
    naam = getattr(controle, "__name__", str(controle))
    try:
        return [_van(p, naam) for p in controle(*args)]
    except Exception as exc:
        return [niet_gecontroleerd(log_interne_fout(exc, f"controle {naam}"))]


def herstelbare(problemen: Iterable[str]) -> list[str]:
    """De problemen waar een herkansing van het model iets aan kan doen."""
    return [p for p in problemen if not getattr(p, "niet_gecontroleerd", False)]


def hard(problemen: Iterable[str]) -> list[Probleem]:
    """Dezelfde problemen, gemarkeerd als hard: blijven ze, dan wordt het antwoord ingehouden.

    Een niet-gecontroleerd-probleem blijft zacht: een mislukte controle is geen bevinding.
    """
    gemarkeerd: list[Probleem] = []
    for p in problemen:
        if isinstance(p, Probleem) and p.niet_gecontroleerd:
            gemarkeerd.append(p)
            continue
        probleem = str.__new__(Probleem, p)
        probleem.melding = getattr(p, "melding", p)
        probleem.controle = getattr(p, "controle", None)
        probleem.hard = True
        gemarkeerd.append(probleem)
    return gemarkeerd


def harde(problemen: Iterable[str]) -> list[str]:
    return [p for p in problemen if getattr(p, "hard", False)]


def controlenamen(problemen: Iterable[str]) -> list[str]:
    """Welke controles afgingen, voor het log: een melding kan antwoordtekst citeren, een naam niet (#475)."""
    return sorted({str(getattr(p, "controle", None)) for p in problemen})


def uitkomsten(controles: Iterable[str], problemen: Iterable[str]) -> dict[str, str]:
    """Per controle wat ze gaf: hard, zacht, niet gecontroleerd of ok; voor het log per antwoord (CH-01)."""
    per_controle: dict[str, list] = {naam: [] for naam in controles}
    for p in problemen:
        per_controle.setdefault(str(getattr(p, "controle", None)), []).append(p)

    def uitkomst(gevonden: list) -> str:
        if any(getattr(p, "hard", False) for p in gevonden):
            return "hard"
        if any(not getattr(p, "niet_gecontroleerd", False) for p in gevonden):
            return "zacht"
        return "niet gecontroleerd" if gevonden else "ok"

    return {naam: uitkomst(gevonden) for naam, gevonden in per_controle.items()}
