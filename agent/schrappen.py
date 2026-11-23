"""Alleen de zinnen met een ongedekt getal schrappen, in plaats van het hele antwoord in te houden (#619).

Blijft na de herkansing alleen dit soort probleem over (een getal dat niet in de opgehaalde data staat,
meestal eigen rekenwerk in een lang antwoord), dan hield de app het antwoord in en kreeg de gebruiker niets.
Hier gaat code verder: ze haalt de zinnen en tabelrijen met zo'n getal uit de tekst, toetst de rest opnieuw
en meldt eerlijk dat er iets is weggelaten. Houdt de rest de controle niet, of valt er meer weg dan blijft,
dan blijft het bij inhouden.

Dat laatste geldt ook per tabel (#976). Een tabel van twaalf hogescholen waarvan elf rijen wegvielen, stond onder een
conclusie "bij 12 hogescholen": de rest van het antwoord sprak de tabel tegen. Een tabel die meer rijen verliest dan
ze houdt, is een restant; dan houdt de app het antwoord in, met de meldingen erbij.

Een antwoord is ook een restant als er geen inhoudszin overblijft (#1107): alleen een `Bron:`-regel, een Bronnen-sectie
of kopjes zeggen niets, en de bronregel van een tabel die de data niet had, wijst dan een verkeerde bron aan.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import replace

from .binding import segmenten_met_scheiding
from .loop import LoopResult
from .probleem import Probleem, harde

_OPNIEUW = "Stel de vraag opnieuw, of preciezer, voor die cijfers."
GESCHRAPT = f"Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten. {_OPNIEUW}"
# Hoeveel rijen de melding bij naam noemt; daarna "en N andere".
_MAX_GENOEMD = 5
# Er blijft minstens zoveel over als er wegvalt: anders is het geen antwoord meer maar een restant.
_MAX_WEG = 0.5
# De scheidingsrij onder de kop van een markdowntabel: |---|:--:|.
_SCHEIDINGSRIJ = re.compile(r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?$")
# "Bron: CBS, …", "Bronnen:" of "**Bronnen**" (een regel die met het woord begint, ook als opsommingsitem of kop).
_BRONREGEL = re.compile(r"^\W*bron(?:nen)?\b", re.IGNORECASE)
# Alleen het woord: de kop van een Bronnen-sectie, waaronder de bronnen als lijst staan.
_BRONNENKOP = re.compile(r"^\W*bron(?:nen)?\W*$", re.IGNORECASE)


def _bronregels_samen(delen: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Een `Bron:`-regel is één segment: de puntkomma's en punten erin splitsen hem niet (#1107)."""
    samen: list[tuple[str, str]] = []
    for zin, scheiding in delen:
        if samen and _BRONREGEL.match(samen[-1][0]) and "\n" not in samen[-1][1]:
            samen[-1] = (samen[-1][0] + samen[-1][1] + zin, scheiding)
        else:
            samen.append((zin, scheiding))
    return samen


def _inhoudszinnen(delen: Sequence[tuple[str, str]]) -> list[bool]:
    """Per segment: is het inhoud? Geen lege regel, kopje, `Bron:`-regel of regel in een Bronnen-sectie (#1107)."""
    inhoud: list[bool] = []
    in_bronnen = False
    for zin, _ in delen:
        regel = zin.strip()
        if _BRONNENKOP.match(regel):
            in_bronnen = True
        elif regel.startswith("#"):
            in_bronnen = False
        inhoud.append(bool(regel) and not regel.startswith("#") and not in_bronnen and not _BRONREGEL.match(regel))
    return inhoud


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


def _rijnaam(rij: str) -> str:
    """De eerste cel van een tabelrij ("2025/26" bij `| 2025/26 | 7.530 |`): waaraan de lezer de rij herkent."""
    return rij.strip().strip("|").split("|")[0].strip()


def _geschrapt(delen: Sequence[tuple[str, str]], weg: Sequence[bool]) -> Probleem:
    """De melding dat er iets is weggelaten: zinnen, of ook tabelrijen, en welke rijen (#1099).

    Een rij die stil verdwijnt, laat bij een jaartabel het nieuwste jaar ontbreken terwijl de tekst erboven dat jaar
    nog noemt. Alleen zinnen: de melding blijft de vaste tekst.
    """
    valt = [zin for (zin, _), is_weg in zip(delen, weg, strict=True) if is_weg]
    rijen = [_rijnaam(zin) for zin in valt if zin.strip().startswith("|")]
    if not rijen:
        return Probleem(GESCHRAPT)
    genoemd = [naam or "?" for naam in rijen[:_MAX_GENOEMD]]
    rest = len(rijen) - len(genoemd)
    rijtekst = ", ".join(genoemd) + (f" en {rest} andere" if rest else "")
    soort = "Tabelrijen" if len(rijen) == len(valt) else "Zinnen en tabelrijen"
    return Probleem(
        f"{soort} met een getal dat niet in de opgehaalde data staat, zijn weggelaten (rij: {rijtekst}). {_OPNIEUW}"
    )


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
    delen = _bronregels_samen(segmenten_met_scheiding(result.text))
    weg = [
        zin.strip() != ""
        and bool(getallen & {getattr(p, "getal", None) for p in getalcontrole(zin, result.tool_results)})
        for zin, _ in delen
    ]
    inhoud = sum(1 for zin, _ in delen if zin.strip())
    if not any(weg) or sum(weg) > inhoud * _MAX_WEG or _tabelrestant(delen, weg):
        return result
    blijft = [
        (deel, is_inhoud) for deel, valt, is_inhoud in zip(delen, weg, _inhoudszinnen(delen), strict=True) if not valt
    ]
    if not any(is_inhoud for _, is_inhoud in blijft):
        return result
    rest = "".join(zin + scheiding for (zin, scheiding), _ in blijft).strip()
    problemen = check(rest, result.tool_results)
    if harde(problemen):
        return result
    geschrapt = _geschrapt(delen, weg)
    geschrapt.controle = "zinnen_schrappen"
    return replace(result, text=rest, problems=[*problemen, geschrapt])
