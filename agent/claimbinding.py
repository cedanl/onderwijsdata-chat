"""Bij welke selectie hoort een getal uit de tekst? (CH-07, CH-08, #433, #434)

Een getal kan als meetwaarde in meer selecties staan: 10.000 bij instelling A én bij B.
De citatie nam de eerste toolstap met dat getal, en de ondergrens gold alleen als élke
selectie met dat getal er een had. De volgorde van de stappen bepaalde zo de betekenis.

Hier beslist de zin waarin het getal staat. Elke kandidaat heeft kenmerken: de waarden
van zijn rij (instelling, jaar, ...) en zijn maat. Een kandidaat wint als de zin er meer
van noemt dan van elke andere. Zijn de kandidaten niet te onderscheiden, dan is er geen
binding, tenzij `voorkeur` er een aanwijst (de bronhiërarchie van agent/citaties.py).
Kandidaten met dezelfde betekenis (maat en rij) tellen als één, zodat dezelfde cel in een
laadstap en een selectie geen twijfel geeft. De volgorde doet er niet toe.
"""

import re
from collections.abc import Callable, Hashable, Iterable, Sequence
from typing import TypeVar

from tools.kolomlabel import kolomlabel

from .meetwaarden import Meetwaarde

T = TypeVar("T")


def kenmerken(waarde: Meetwaarde) -> frozenset[str]:
    """Wat een zin over deze meetwaarde kan noemen: de waarden van haar rij en haar maat."""
    cellen = {cel.split(": ", 1)[-1].strip() for cel in waarde.selectie}
    return frozenset(c for c in (*cellen, kolomlabel(waarde.maat)) if c)


def betekenis(waarde: Meetwaarde) -> Hashable:
    return (waarde.maat, waarde.selectie)


def _noemt(zin: str, kenmerk: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(kenmerk)}(?!\w)", zin, re.IGNORECASE) is not None


def kies(
    kandidaten: Sequence[T],
    sleutel: Callable[[T], Hashable],
    kenmerk: Callable[[T], Iterable[str]],
    zin: str,
    voorkeur: Callable[[list[T]], T | None] | None = None,
) -> T | None:
    """De ene kandidaat die de zin aanwijst; None bij twijfel of zonder kandidaat.

    Wijst de zin er niet één aan, dan kiest `voorkeur` uit de gelijk geëindigde kandidaten.

    Bij gelijke betekenis (`sleutel`) blijft de eerste staan: de betekenis hangt niet van
    de volgorde af, alleen welke stap ernaar verwijst.
    """
    uniek: dict[Hashable, T] = {}
    for k in kandidaten:
        uniek.setdefault(sleutel(k), k)
    if len(uniek) <= 1:
        return next(iter(uniek.values()), None)
    scores = {s: sum(_noemt(zin, w) for w in set(kenmerk(k))) for s, k in uniek.items()}
    beste = max(scores.values())
    winnaars = [s for s, score in scores.items() if score == beste]
    if beste > 0 and len(winnaars) == 1:
        return uniek[winnaars[0]]
    return voorkeur([uniek[s] for s in winnaars]) if voorkeur else None
