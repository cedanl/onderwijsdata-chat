"""Openstaande vacatures per provincie en SBI-sectie uit CBS 83599NED (#1223), voor de arbeidsmarktdashboards.

Besluit #1221: de dashboards stappen voor vacatureaanbod en matchscore over van UWV Open Match (een momentopname van
mei 2023, die UWV niet meer bijwerkt) naar CBS-tabel 83599NED "Openstaande vacatures; SBI 2008, regio": open OData,
licentie CC BY 4.0, per kwartaal sinds 2011, per provincie en per sectie van de Standaard Bedrijfsindeling.

- Eén lading voor de 12 provincies en alle kwartalen (`_tabel`, met de TTL van `actualiteit`): de dimensies via
  `client.dimension`, de status per periode uit de Perioden-dimensie (`client.get`), de cijfers via `client.data` met
  een `$filter` op de provincies.
- CBS geeft de vacatures in duizendtallen met één decimaal; hier staan ze als aantal (34,4 → 34.400).
- Per provincie en sectie het laatste kwartaal en het gemiddelde van de laatste `GEMIDDELD_OVER` kwartalen, elk met
  zijn perioden. Het laatste kwartaal is het jongste kwartaal waarin de tabel cijfers heeft, voor elke provincie
  hetzelfde.
- Voorlopig: een periode die CBS in de Perioden-dimensie "Voorlopig" noemt (#1097). Een gemiddelde is voorlopig als
  één van zijn kwartalen dat is. De voorlopige kwartalen gaan mee in de melding voor het bronblok (data/bronblok.py).
- Een lege of ontbrekende cel is "geen gegevens" (`vacatures` None), nooit 0; een gemiddelde over een kwartaal zonder
  cijfer ook, want een gemiddelde over minder kwartalen is een ander getal.
- Een vacature telt bij de bedrijfstak van de werkgever, niet bij het beroep: een verpleegkundige in een fabriek telt
  bij C Industrie. De koppeling van secties aan onderwijssectoren staat in data/sbi_koppeling.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from onderwijsbronnen.cbs import client

from core import actualiteit, brongebruik

DATASET = "83599NED"
TITEL = "Openstaande vacatures; SBI 2008, regio"
LICENTIE = "CC BY 4.0"
API_URL = f"https://opendata.cbs.nl/ODataApi/odata/{DATASET}"
# De tabel in StatLine, voor de bronlink: daar leest een mens haar, met toelichting.
STATLINE_URL = f"https://opendata.cbs.nl/#/CBS/nl/dataset/{DATASET}/table"
GEMIDDELD_OVER = 4  # kwartalen in het gemiddelde van de matchscore
GEEN_GEGEVENS = "geen gegevens"
VOORLOPIG = "voorlopig"
DEFINITIEF = "definitief"

_SBI = "BedrijfstakkenBranchesSBI2008"
_REGIO = "RegioS"
_PERIODEN = "Perioden"
_MEETWAARDE = "OpenstaandeVacatures_1"
_PER = 1000  # de eenheid van de meetwaarde: x 1000
_PROVINCIES = "substringof('PV',RegioS)"  # de regiocodes van de provincies beginnen met PV, de landsdelen met LD
_PROVINCIE_ACHTER = " (PV)"
_TOTAAL = "A-U"  # alle economische activiteiten
_STATUS_VOORLOPIG = "Voorlopig"
# De Friese provincie heet bij CBS Fryslân; DUO en een gebruiker schrijven ook Friesland.
_PROVINCIE_ALIAS = {"friesland": "fryslân", "fryslan": "fryslân"}


@dataclass(frozen=True)
class Periode:
    code: str  # "2026KW03"
    titel: str  # "2026 3e kwartaal"
    voorlopig: bool


@dataclass(frozen=True)
class Waarde:
    """Het aantal openstaande vacatures over één of meer kwartalen; None is "geen gegevens", nooit 0."""

    perioden: tuple[Periode, ...]
    vacatures: int | None

    @property
    def voorlopig(self) -> bool:
        return any(p.voorlopig for p in self.perioden)

    @property
    def status(self) -> str:
        if self.vacatures is None:
            return GEEN_GEGEVENS
        return VOORLOPIG if self.voorlopig else DEFINITIEF

    def als_dict(self) -> dict:
        return {
            "periode": periodetekst(self.perioden),
            "perioden": [p.titel for p in self.perioden],
            "vacatures": self.vacatures,
            "voorlopig": self.voorlopig,
            "status": self.status,
        }


@dataclass(frozen=True)
class Sectie:
    """Eén SBI-sectie (of het totaal A-U) in een provincie: het laatste kwartaal en het gemiddelde."""

    code: str  # "C", of "A-U" voor het totaal
    naam: str  # "Industrie"
    laatste: Waarde
    gemiddelde: Waarde

    @property
    def label(self) -> str:
        return f"{self.code} {self.naam}"


@dataclass(frozen=True)
class Provinciestand:
    provincie: str  # zoals CBS haar spelt, zonder "(PV)"
    laatste: Periode
    gemiddeld_over: tuple[Periode, ...]
    totaal: Sectie
    secties: tuple[Sectie, ...]  # A t/m S, in de volgorde van CBS


@dataclass(frozen=True)
class _Tabel:
    perioden: tuple[Periode, ...]  # in de volgorde van CBS, van oud naar nieuw
    secties: dict[str, tuple[str, str]]  # sleutel → (code, naam)
    provincies: dict[str, str]  # sleutel → naam
    waarden: dict[tuple[str, str, str], float]  # (regio, sbi, periode) → duizendtallen; een lege cel staat er niet in
    laatste: int  # index in `perioden` van het jongste kwartaal met cijfers


def _provincienaam(naam: str) -> str:
    sleutel = " ".join(naam.split()).lower()
    return _PROVINCIE_ALIAS.get(sleutel, sleutel)


def _sectie(titel: str) -> tuple[str, str]:
    """ "C Industrie" → ("C", "Industrie"); "A-U Alle economische activiteiten" → ("A-U", …)."""
    code, _, naam = titel.partition(" ")
    return code, naam


def periodetekst(perioden: tuple[Periode, ...] | list[Periode]) -> str:
    """ "2026 3e kwartaal", of voor een gemiddelde "2025 4e kwartaal t/m 2026 3e kwartaal"."""
    if not perioden:
        return ""
    if len(perioden) == 1:
        return perioden[0].titel
    return f"{perioden[0].titel} t/m {perioden[-1].titel}"


def kwartaal_einde(code: str) -> str | None:
    """De laatste dag van een kwartaal ("2026KW03" → "2026-09-30"): de stand van de openstaande vacatures."""
    try:
        jaar, kwartaal = int(code[:4]), int(code[-2:])
    except ValueError:
        return None
    if code[4:6] != "KW" or not 1 <= kwartaal <= 4:
        return None
    begin_volgend = date(jaar + kwartaal // 4, kwartaal % 4 * 3 + 1, 1)
    return (begin_volgend - timedelta(days=1)).isoformat()


@actualiteit.Lading
def _tabel() -> _Tabel:
    secties = {k: _sectie(t) for k, t in client.dimension(DATASET, _SBI).items()}
    provincies = {
        k: t.removesuffix(_PROVINCIE_ACHTER) for k, t in client.dimension(DATASET, _REGIO).items() if t.endswith("(PV)")
    }
    perioden = tuple(
        Periode(str(r["Key"]).strip(), str(r["Title"]).strip(), str(r.get("Status") or "").strip() == _STATUS_VOORLOPIG)
        for r in client.get(DATASET, _PERIODEN)
    )
    waarden = {
        (str(r[_REGIO]), str(r[_SBI]), str(r[_PERIODEN])): float(r[_MEETWAARDE])
        for r in client.data(DATASET, **{"$filter": _PROVINCIES})
        if r.get(_MEETWAARDE) is not None
    }
    met_cijfers = {periode for (_, _, periode) in waarden}
    laatste = max((i for i, p in enumerate(perioden) if p.code in met_cijfers), default=-1)
    if laatste < 0:
        raise ValueError(f"{DATASET}: geen cijfers voor de provincies")
    tabel = _Tabel(perioden, secties, provincies, waarden, laatste)
    brongebruik.meld(
        {
            "bron": "CBS",
            "dataset": DATASET,
            "titel": TITEL,
            "url": STATLINE_URL,
            "licentie": LICENTIE,
            "laatste_periode": perioden[laatste].titel,
            "gemiddeld_over": [p.titel for p in _venster(tabel)],
            # De kwartalen die de dashboards tonen: het gemiddelde, dat eindigt met het laatste kwartaal.
            "voorlopig_perioden": [p.titel for p in _venster(tabel) if p.voorlopig],
            "peildatum": kwartaal_einde(perioden[laatste].code),
            "opgehaald_op": actualiteit.nu().isoformat(),
        }
    )
    return tabel


def _venster(tabel: _Tabel) -> tuple[Periode, ...]:
    """De laatste GEMIDDELD_OVER kwartalen, tot en met het laatste kwartaal met cijfers."""
    return tabel.perioden[max(tabel.laatste - GEMIDDELD_OVER + 1, 0) : tabel.laatste + 1]


def _aantal(tabel: _Tabel, regio: str, sbi: str, perioden: tuple[Periode, ...]) -> int | None:
    """Het gemiddelde aantal over `perioden`; None als één kwartaal geen cijfer heeft of het venster te kort is."""
    cellen = [tabel.waarden.get((regio, sbi, p.code)) for p in perioden]
    if not cellen or any(c is None for c in cellen):
        return None
    return round(sum(c for c in cellen if c is not None) / len(cellen) * _PER)


def provincies() -> list[str]:
    return sorted(_tabel().provincies.values())


def stand(provincie: str) -> Provinciestand | None:
    """De vacatures in één provincie, per SBI-sectie en in totaal; None voor een provincie die CBS niet kent."""
    tabel = _tabel()
    regio = next((k for k, naam in tabel.provincies.items() if _provincienaam(naam) == _provincienaam(provincie)), None)
    if regio is None:
        return None
    laatste = (tabel.perioden[tabel.laatste],)
    venster = _venster(tabel)
    if len(venster) < GEMIDDELD_OVER:
        venster = ()  # minder kwartalen dan het gemiddelde vraagt: geen gemiddelde

    def sectie(sleutel: str) -> Sectie:
        code, naam = tabel.secties[sleutel]
        return Sectie(
            code=code,
            naam=naam,
            laatste=Waarde(laatste, _aantal(tabel, regio, sleutel, laatste)),
            gemiddelde=Waarde(venster, _aantal(tabel, regio, sleutel, venster)),
        )

    totaal = next((k for k, (code, _) in tabel.secties.items() if code == _TOTAAL), None)
    if totaal is None:
        raise ValueError(f"{DATASET}: geen totaal {_TOTAAL} in {_SBI}")
    return Provinciestand(
        provincie=tabel.provincies[regio],
        laatste=laatste[0],
        gemiddeld_over=venster,
        totaal=sectie(totaal),
        secties=tuple(sectie(k) for k, (code, _) in tabel.secties.items() if len(code) == 1),
    )
