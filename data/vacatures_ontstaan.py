"""Ontstane vacatures per jaar en beroep uit CBS 85081NED (#1227), landelijk, voor de chat.

Besluit #1221: naast de openstaande vacatures per provincie en bedrijfstak (CBS 83599NED, data/vacatures_cbs.py) geeft
de chat de vacatures per beroep uit CBS-tabel 85081NED "Ontstane vacatures; beroepenindeling ROA-CBS 2014 (BRC 2014),
SBI 2008": open OData, licentie CC BY 4.0, per jaar sinds 2018, alleen landelijk.

- Een stroom, geen stand: het aantal vacatures dat in het jaar ontstond (de som van de vier kwartalen), niet hoeveel er
  op één moment openstonden. Daarom staat het naast 83599NED en vervangt het die niet.
- Eén lading (`_tabel`, met de TTL van `actualiteit`): de eenheid uit DataProperties, de beroepen via
  `client.dimension`, de status per jaar uit de Perioden-dimensie (`client.get`), de cijfers via `client.data` met een
  `$filter` op alle economische activiteiten (A-U): de bedrijfstak doet hier niet mee.
- De eenheid komt uit de metadata van de tabel (`Unit` van de meetwaarde), niet uit deze code: "x 1 000" is een aantal
  in duizendtallen (64,3 → 64.300), "aantal" een gewoon aantal; een andere eenheid is een fout, geen gok.
- De BRC 2014 kent beroepsklassen (twee cijfers, "07 Technische beroepen") en daaronder beroepssegmenten (drie cijfers,
  "072 Vakspecialisten natuur en techniek"); het segment hoort bij de klasse met dezelfde eerste twee cijfers. CBS kort
  lange namen af met "..."; zo staan ze hier ook.
- Voorlopig: een jaar dat CBS in de Perioden-dimensie "Voorlopig" (of "Nader voorlopig") noemt.
- Een lege of ontbrekende cel is "geen gegevens" (None), nooit 0: CBS publiceert veel segmenten en sommige klassen niet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from onderwijsbronnen.cbs import client

from core import actualiteit, brongebruik

DATASET = "85081NED"
TITEL = "Ontstane vacatures; beroepenindeling ROA-CBS 2014 (BRC 2014), SBI 2008"
LICENTIE = "CC BY 4.0"
API_URL = f"https://opendata.cbs.nl/ODataApi/odata/{DATASET}"
# De tabel in StatLine, voor de bronlink: daar leest een mens haar, met toelichting.
STATLINE_URL = f"https://opendata.cbs.nl/#/CBS/nl/dataset/{DATASET}/table"
GEEN_GEGEVENS = "geen gegevens"
VOORLOPIG = "voorlopig"
DEFINITIEF = "definitief"
TOTAAL = "totaal"
KLASSE = "klasse"
SEGMENT = "segment"

SBI = "BedrijfstakkenBranchesSBI2008"
BEROEP = "Beroepenindeling"
PERIODEN = "Perioden"
MEETWAARDE = "OntstaneVacatures_1"
SBI_TOTAAL = "T001081"  # A-U Alle economische activiteiten
FILTER = f"{SBI} eq '{SBI_TOTAAL}'"
# De eenheden die deze code kent, zonder spaties en in kleine letters, met hun factor naar een aantal.
EENHEDEN = {"x1000": 1000, "aantal": 1}
_BEROEPSCODE = re.compile(r"^(\d{2,3})\s+(.+)$")
_AFGEKORT = "..."


@dataclass(frozen=True)
class Jaar:
    code: str  # "2025JJ00"
    titel: str  # "2025"
    voorlopig: bool

    @property
    def status(self) -> str:
        return VOORLOPIG if self.voorlopig else DEFINITIEF


@dataclass(frozen=True)
class Beroep:
    sleutel: str  # de sleutel van CBS: "A000239"
    code: str  # "07", "072"; leeg voor het totaal
    naam: str  # "Technische beroepen", zoals CBS hem schrijft (ook afgekort)
    niveau: str  # TOTAAL, KLASSE of SEGMENT

    @property
    def label(self) -> str:
        return f"{self.code} {self.naam}" if self.code else self.naam

    @property
    def klasse(self) -> str | None:
        """De code van de beroepsklasse waar een segment onder valt ("07" bij "072"); None voor het totaal."""
        return self.code[:2] if self.code else None


@dataclass(frozen=True)
class Waarde:
    """Het aantal ontstane vacatures in één jaar; None is "geen gegevens", nooit 0."""

    jaar: Jaar
    vacatures: int | None

    @property
    def status(self) -> str:
        return GEEN_GEGEVENS if self.vacatures is None else self.jaar.status


@dataclass(frozen=True)
class _Tabel:
    jaren: tuple[Jaar, ...]  # in de volgorde van CBS, van oud naar nieuw
    beroepen: tuple[Beroep, ...]  # in de volgorde van CBS: het totaal, dan elke klasse met haar segmenten
    waarden: dict[tuple[str, str], float]  # (beroep, jaar) → in de eenheid van CBS; een lege cel staat er niet in
    eenheid: str  # zoals CBS haar noemt: "x 1 000"
    factor: int  # van de eenheid naar een aantal


def eenheidsfactor(eenheid: str) -> int:
    """De factor van de CBS-eenheid naar een aantal: "x 1 000" → 1000, "aantal" → 1; een andere eenheid is een fout."""
    sleutel = re.sub(r"\s+", "", eenheid or "").lower()
    if sleutel not in EENHEDEN:
        raise ValueError(f"{DATASET}: onbekende eenheid {eenheid!r} voor {MEETWAARDE}")
    return EENHEDEN[sleutel]


def _eenheid(properties: list[dict]) -> str:
    eigen = next((p for p in properties if str(p.get("Key") or "").strip() == MEETWAARDE), None)
    if eigen is None:
        raise ValueError(f"{DATASET}: geen meetwaarde {MEETWAARDE} in DataProperties")
    return str(eigen.get("Unit") or "").strip()


def _beroep(sleutel: str, titel: str) -> Beroep:
    if not (gevonden := _BEROEPSCODE.match(titel)):
        return Beroep(sleutel, "", titel, TOTAAL)
    code, naam = gevonden.groups()
    return Beroep(sleutel, code, naam, KLASSE if len(code) == 2 else SEGMENT)


@actualiteit.Lading
def _tabel() -> _Tabel:
    eenheid = _eenheid(client.properties(DATASET))
    factor = eenheidsfactor(eenheid)
    beroepen = tuple(_beroep(k, t) for k, t in client.dimension(DATASET, BEROEP).items())
    jaren = tuple(
        Jaar(str(r["Key"]).strip(), str(r["Title"]).strip(), "voorlopig" in str(r.get("Status") or "").lower())
        for r in client.get(DATASET, PERIODEN)
    )
    waarden = {
        (str(r[BEROEP]), str(r[PERIODEN])): float(r[MEETWAARDE])
        for r in client.data(DATASET, **{"$filter": FILTER})
        if r.get(MEETWAARDE) is not None and str(r.get(SBI)) == SBI_TOTAAL
    }
    if not waarden:
        raise ValueError(f"{DATASET}: geen cijfers voor alle economische activiteiten")
    tabel = _Tabel(jaren, beroepen, waarden, eenheid, factor)
    brongebruik.meld(
        {
            "bron": "CBS",
            "dataset": DATASET,
            "titel": TITEL,
            "url": STATLINE_URL,
            "licentie": LICENTIE,
            "laatste_periode": jaren[-1].titel if jaren else None,
            "voorlopig_perioden": [j.titel for j in jaren if j.voorlopig],
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return tabel


def jaren() -> tuple[Jaar, ...]:
    return _tabel().jaren


def eenheid() -> str:
    """De eenheid van de meetwaarde zoals CBS haar noemt ("x 1 000")."""
    return _tabel().eenheid


def beroepen(niveau: str | None = None) -> list[Beroep]:
    """De beroepen van de BRC 2014 in de volgorde van CBS; met `niveau` alleen de klassen of de segmenten."""
    return [b for b in _tabel().beroepen if niveau is None or b.niveau == niveau]


def totaal() -> Beroep:
    return next(b for b in _tabel().beroepen if b.niveau == TOTAAL)


def segmenten(klasse: Beroep) -> list[Beroep]:
    """De beroepssegmenten onder een beroepsklasse."""
    return [b for b in beroepen(SEGMENT) if b.klasse == klasse.code]


def klasse_van(segment: Beroep) -> Beroep | None:
    return next((b for b in beroepen(KLASSE) if b.code == segment.klasse), None)


def _naam(tekst: str) -> str:
    return " ".join(tekst.removesuffix(_AFGEKORT).split()).casefold()


def zoek(tekst: str) -> Beroep | None:
    """Een beroep bij code ("07", "072"), label of naam ("Technische beroepen"); bij een afgekorte naam van CBS ook het
    begin ervan. Anders een naamdeel dat bij precies één beroep past; None als geen of meer beroepen passen."""
    gezocht = _naam(str(tekst))
    if not gezocht:
        return None
    kandidaten = [b for b in _tabel().beroepen if b.niveau != TOTAAL]
    for past in (
        lambda b: gezocht in (b.code, _naam(b.label), _naam(b.naam)),
        lambda b: b.naam.endswith(_AFGEKORT) and gezocht.startswith(_naam(b.naam)),
        lambda b: gezocht in _naam(b.naam),
    ):
        if len(gevonden := [b for b in kandidaten if past(b)]) == 1:
            return gevonden[0]
        if gevonden:
            return None
    return None


def waarden(beroep: Beroep) -> list[Waarde]:
    """Het aantal ontstane vacatures per jaar, van oud naar nieuw; een jaar zonder cijfer is "geen gegevens"."""
    tabel = _tabel()

    def aantal(jaar: Jaar) -> int | None:
        cel = tabel.waarden.get((beroep.sleutel, jaar.code))
        return None if cel is None else round(cel * tabel.factor)

    return [Waarde(jaar, aantal(jaar)) for jaar in tabel.jaren]
