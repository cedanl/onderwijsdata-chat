"""Alleen de zinnen met een ongedekt getal schrappen, in plaats van het hele antwoord in te houden (#619).

Blijft na de herkansing alleen dit soort probleem over (een getal dat niet in de opgehaalde data staat,
meestal eigen rekenwerk in een lang antwoord), dan hield de app het antwoord in en kreeg de gebruiker niets.
Hier gaat code verder: ze haalt de zinnen en tabelrijen met zo'n getal uit de tekst, toetst de rest opnieuw
en meldt eerlijk dat er iets is weggelaten. Houdt de rest de controle niet, of valt er meer weg dan blijft,
dan blijft het bij inhouden.

Dat laatste geldt ook per tabel (#976). Een tabel van twaalf hogescholen waarvan elf rijen wegvielen, stond onder een
conclusie "bij 12 hogescholen": de rest van het antwoord sprak de tabel tegen. Een tabel die meer rijen verliest dan
ze houdt, is een restant; dan houdt de app het antwoord in, met de meldingen erbij.
"""

import re
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
# De scheidingsrij onder de kop van een markdowntabel: |---|:--:|.
_SCHEIDINGSRIJ = re.compile(r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?$")


def _tabelrestant(delen: Sequence[tuple[str, str]], weg: Sequence[bool]) -> bool:
    """Verliest een tabel meer datarijen dan ze houdt? De kop (tot en met de scheidingsrij) telt niet mee."""
    tabellen: list[list[bool]] = []  # per tabel: per rij of hij wegvalt
    vorige_is_rij = False
    for (zin, _), valt in zip(delen, weg, strict=True):
        rij = zin.strip()
        if not rij.startswith("|"):
            vorige_is_rij = False
            continue
        if not vorige_is_rij:
            tabellen.append([])
        vorige_is_rij = True
        if _SCHEIDINGSRIJ.match(rij):
            tabellen[-1].clear()  # wat erboven stond was de kop
        else:
            tabellen[-1].append(valt)
    return any(sum(rijen) > len(rijen) * _MAX_WEG for rijen in tabellen)


def zonder_ongedekte_zinnen(
    result: LoopResult,
    check: Callable[[str, list[str]], list[str]],
    getalcontrole: Callable[[str, list[str]], Sequence[str]],
) -> LoopResult:
    """Het resultaat zonder de zinnen met een ongedekt getal, als dat het antwoord goed genoeg maakt.

    Alleen als elk hard probleem zo'n getal is, er niet meer wegvalt dan blijft (in het hele antwoord en per tabel)
    en `check` op de overgebleven tekst niets hards meer vindt. Anders blijft het resultaat zoals het was en houdt de app het antwoord in.
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
    if not any(weg) or sum(weg) > inhoud * _MAX_WEG or _tabelrestant(delen, weg):
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
