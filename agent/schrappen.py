"""Alleen de zinnen met een ongedekt getal schrappen, in plaats van het hele antwoord in te houden (#619).

Blijft na de herkansing alleen dit soort probleem over (een getal dat niet in de opgehaalde data staat,
meestal eigen rekenwerk in een lang antwoord), dan hield de app het antwoord in en kreeg de gebruiker niets.
Hier gaat code verder: ze haalt de zinnen en tabelrijen met zo'n getal uit de tekst, toetst de rest opnieuw
en meldt eerlijk dat er iets is weggelaten. Houdt de rest de controle niet, of valt er meer weg dan blijft,
dan blijft het bij inhouden.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace

from .binding import segmenten_met_scheiding
from .loop import LoopResult
from .probleem import Probleem, harde

GESCHRAPT = (
    "Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten. "
    "Stel de vraag opnieuw, of preciezer, voor die cijfers."
)
# Er blijft minstens zoveel over als er wegvalt: anders is het geen antwoord meer maar een restant.
_MAX_WEG = 0.5


def zonder_ongedekte_zinnen(
    result: LoopResult,
    check: Callable[[str, list[str]], list[str]],
    getalcontrole: Callable[[str, list[str]], Sequence[str]],
) -> LoopResult:
    """Het resultaat zonder de zinnen met een ongedekt getal, als dat het antwoord goed genoeg maakt.

    Alleen als elk hard probleem zo'n getal is, er niet meer wegvalt dan blijft en `check` op de overgebleven
    tekst niets hards meer vindt. Anders blijft het resultaat zoals het was en houdt de app het antwoord in.
    """
    harde_problemen = harde(result.problems)
    getallen = {getattr(p, "getal", None) for p in harde_problemen}
    if not harde_problemen or None in getallen or not result.text.strip():
        return result
    delen = segmenten_met_scheiding(result.text)
    weg = [
        zin.strip() != ""
        and bool(getallen & {getattr(p, "getal", None) for p in getalcontrole(zin, result.tool_results)})
        for zin, _ in delen
    ]
    inhoud = sum(1 for zin, _ in delen if zin.strip())
    if not any(weg) or sum(weg) > inhoud * _MAX_WEG:
        return result
    rest = "".join(zin + scheiding for (zin, scheiding), valt in zip(delen, weg, strict=True) if not valt).strip()
    if not rest:
        return result
    problemen = check(rest, result.tool_results)
    if harde(problemen):
        return result
    geschrapt = Probleem(GESCHRAPT)
    geschrapt.controle = "zinnen_schrappen"
    return replace(result, text=rest, problems=[*problemen, geschrapt])
