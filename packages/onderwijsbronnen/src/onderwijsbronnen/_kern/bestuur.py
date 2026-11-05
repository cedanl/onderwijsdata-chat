"""Het bestuursnummer (bevoegd gezag) als één sleutel, hoe een bron het ook schrijft (#935, onderzoek #725).

Hetzelfde bestuur staat in elke bron anders: DUO's adressenbestanden geven een getal (`40597`), het jaardocument een
float (`40597.0`), de Inspectie formuletekst (`="00008"`), de verantwoording uit XBRL en RIO tekst van vijf tekens met
voorloopnullen (`00008`). Eén bestuur staat in XBRL niet als bestuur: 40833 heeft drie verantwoordingen, één per
BRIN, als `40833-25LR`, `40833-25PZ` en `40833-30RM`. Dat suffix hoort bij de sleutel (`brin`): de drie rijen zijn
aparte eenheden, die je nooit optelt of middelt.

`rio_code` is de vorm van RIO (vijf tekens). RIO zoekt op die code een erkenning, en die hoeft geen bestuur te zijn:
`00009` geeft de A&O groep, niet het bestuur van de Universiteit Utrecht (#725, #728). Een lookup in RIO controleert
dus zelf het type; de sleutel zegt alleen welk nummer het is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Het nummer met hooguit vijf cijfers, een staart `.0` van een float, en het BRIN-suffix van een XBRL-eenheid.
_SLEUTEL = re.compile(r"(?P<nummer>\d{1,5})(?:\.0+)?(?:-(?P<brin>\d{2}[A-Z0-9]{2}))?")
_OPMAAK = re.compile(r'[="\'\s]')


@dataclass(frozen=True, order=True)
class Bestuurssleutel:
    """Een bestuur (`nummer`), of één verantwoordingseenheid ervan (`brin`, alleen bij XBRL-suffixen)."""

    nummer: int
    brin: str | None = None

    @property
    def rio_code(self) -> str:
        """Het nummer zoals RIO en XBRL het schrijven: vijf tekens met voorloopnullen."""
        return f"{self.nummer:05d}"

    @property
    def bestuur(self) -> Bestuurssleutel:
        """Het bestuur zelf, zonder eenheid."""
        return Bestuurssleutel(self.nummer)

    def __str__(self) -> str:
        return f"{self.rio_code}-{self.brin}" if self.brin else self.rio_code

    @classmethod
    def parse(cls, waarde) -> Bestuurssleutel | None:
        """De sleutel achter elke schrijfwijze; None als `waarde` geen bestuursnummer is.

        `40597`, `40597.0`, `"40597"`, `="00008"` en `00008` zijn nummers; `40833-25LR` houdt zijn BRIN. Een bool, een
        float met decimalen of tekst met andere tekens is geen nummer.
        """
        if waarde is None or isinstance(waarde, bool):
            return None
        if isinstance(waarde, int):
            return cls(waarde) if 0 <= waarde < 100_000 else None
        if isinstance(waarde, float):
            return cls.parse(int(waarde)) if waarde.is_integer() else None
        m = _SLEUTEL.fullmatch(_OPMAAK.sub("", str(waarde)).upper())
        return cls(int(m["nummer"]), m["brin"]) if m else None
