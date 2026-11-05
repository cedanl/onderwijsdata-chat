"""Eén ID-contract voor alle bronnen: `bron:id` (#912).

Elk catalogusrecord heeft één getypeerde sleutel, bijvoorbeeld `cbs:85423NED`, `duo:p01hoinges` of
`rio:aangeboden-opleidingen`. Dit is de enige plek die zegt bij welke bron een ID hoort:

- `BronId.parse(tekst, register)` accepteert elke vorm die in opgeslagen gegevens staat (nulmeting #909): met
  voorvoegsel (`cbs:`, `cbs_`, `rio/`, `duo:`), zonder voorvoegsel, en in elke hoofdletterspelling. Het resultaat
  heeft de spelling van de catalogus: CBS schrijft `85423NED` naast `80040ned`, dus hoofdletters zijn niet te raden.
- Een kale ID die bij meer dan één bron past, is een fout met de opties erbij (`AmbigueBronId`), nooit een stille
  keuze; een onbekende ID is `OnbekendBronId`.
- `BronId.normaliseer(tekst, register)` is `str(BronId.parse(...))`.

Het `Register` kent per bron de ID's uit de catalogus; de bovenlaag (`onderwijsbronnen.register()`) bouwt het uit de
catalogusrecords van elke bron. De kern zelf kent alleen de namen van de bronnen, geen data.

Bewust buiten dit contract: BRIN- en bestuursnummers (#728). Die identificeren een instelling, geen dataset.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Alle bronnen, in de volgorde van de samengevoegde catalogus (CBS eerst, dan RIO, DUO en de rest; UNL sinds #936).
BRONNEN = ("cbs", "rio", "duo", "roa", "uwv", "inspectie", "sbb", "unl")

# Welk scheidingsteken na de bronnaam een voorvoegsel is. CBS ook `_` (`cbs_85423ned`, zoals een model het spelt);
# bij de andere bronnen niet, want een DUO-naam kan zelf met `duo_` of `duo-` beginnen.
_TEKENS = {"cbs": ":/_"}
_STANDAARD_TEKENS = ":/"
_VOORVOEGSEL = re.compile(r"^(?P<bron>[A-Za-z]+)(?P<teken>[:/_])\s*(?P<rest>.+)$")


class BronIdFout(LookupError):
    """Basis voor fouten bij het herleiden van een ID."""


class OnbekendBronId(BronIdFout):
    """Geen bron kent dit ID."""


class AmbigueBronId(BronIdFout, ValueError):
    """Een kale ID die bij meer dan één bron past; `opties` noemt ze als `bron:id`."""

    def __init__(self, bericht: str, opties: list[str]):
        super().__init__(bericht)
        self.opties = opties


@dataclass(frozen=True, order=True)
class BronId:
    bron: str
    id: str

    def __str__(self) -> str:
        return f"{self.bron}:{self.id}"

    @classmethod
    def parse(cls, tekst: str, register: Register) -> BronId:
        """Het `BronId` achter elke ID-vorm; `OnbekendBronId` of `AmbigueBronId` als dat niet eenduidig kan."""
        schoon = str(tekst).strip()
        if m := _VOORVOEGSEL.match(schoon):
            bron = m["bron"].lower()
            if bron in register.bronnen and m["teken"] in _TEKENS.get(bron, _STANDAARD_TEKENS):
                if gevonden := register.zoek(bron, m["rest"].strip()):
                    return gevonden
        # Kaal, of een voorvoegsel dat niet klopt: misschien hoort het hele ID zelf bij een bron (een DUO-naam die met
        # `cbs_` begint, bijvoorbeeld). Anders volgt de fout hieronder.
        kandidaten = register.kandidaten(schoon)
        if len(kandidaten) == 1:
            return kandidaten[0]
        if kandidaten:
            opties = [str(k) for k in kandidaten]
            raise AmbigueBronId(f"'{schoon}' past bij {opties}; gebruik het volledige ID", opties)
        raise OnbekendBronId(schoon)

    @classmethod
    def normaliseer(cls, tekst: str, register: Register) -> str:
        return str(cls.parse(tekst, register))


class Register:
    """De ID's per bron, hoofdletterongevoelig op te zoeken, in de spelling van de catalogus."""

    def __init__(self, ids_per_bron: Mapping[str, Iterable[str]]):
        onbekend = set(ids_per_bron) - set(BRONNEN)
        if onbekend:
            raise ValueError(f"onbekende bron(nen) {sorted(onbekend)}; kies uit {BRONNEN}")
        self.bronnen = tuple(b for b in BRONNEN if b in ids_per_bron)
        self._per_bron: dict[str, dict[str, BronId]] = {}
        self._kaal: dict[str, list[BronId]] = {}
        for bron in self.bronnen:
            eigen = self._per_bron.setdefault(bron, {})
            for id_ in ids_per_bron[bron]:
                bron_id = BronId(bron, id_)
                if id_.lower() in eigen:
                    # Twee records van één bron met hetzelfde ID (in een andere spelling): ook dat is dubbel.
                    self._kaal.setdefault(id_.lower(), []).append(bron_id)
                    continue
                eigen[id_.lower()] = bron_id
                self._kaal.setdefault(id_.lower(), []).append(bron_id)

    def zoek(self, bron: str, id_: str) -> BronId | None:
        return self._per_bron.get(bron, {}).get(id_.strip().lower())

    def kandidaten(self, id_: str) -> list[BronId]:
        return list(self._kaal.get(id_.strip().lower(), []))

    def dubbel(self) -> dict[str, list[str]]:
        """De ID's die bij meer dan één record horen (in één of meer bronnen); leeg als elk ID uniek is."""
        return {sleutel: [str(b) for b in ids] for sleutel, ids in self._kaal.items() if len(ids) > 1}

    def __iter__(self):
        for bron in self.bronnen:
            yield from self._per_bron[bron].values()

    def __len__(self) -> int:
        return sum(len(ids) for ids in self._per_bron.values())


def bron_van_sleutel(sleutel: str) -> str:
    """De bron van een opgeslagen datasleutel (`duo:p01hoinges:4`, `cbs:85423NED:1e45b6cf`, `analysis:…`).

    Het voorvoegsel tot de eerste `:`; een bron in kleine letters. Een voorvoegsel dat geen bron is (`analysis`, een
    eigen berekening) blijft zoals het is: dat is geen bron, maar de chat noemt het zo (nulmeting #909).
    """
    voorvoegsel = str(sleutel).split(":", 1)[0]
    return voorvoegsel.lower() if voorvoegsel.lower() in BRONNEN else voorvoegsel
