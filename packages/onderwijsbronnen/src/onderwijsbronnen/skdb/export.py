"""De Studiekeuzedatabase (SKDB) van het Landelijk Centrum Studiekeuze lezen uit de dagelijkse export (#957).

De REST-API (`https://api.skdb.nl/v1`, bearer-sleutel) heeft geen filters en geen paginering: elk lijst-endpoint geeft
alles, genest (`/opleidingen` is 20 MB). De export `/export/json` is één ZIP van ongeveer 18 MB met dezelfde gegevens
als platte tabellen (`data/<tabel>.json`); de verkenning van 06-11-2026 vond voor alle lijst-endpoints dezelfde
aantallen en velden. Dit module haalt daarom alleen die ZIP op en leest een tabel pas als iemand erom vraagt:
`studieroutes` alleen is uitgepakt 200 MB.

De sleutel komt uit het argument of uit de omgeving (`STUDIEKEUZEDATABASE_API_KEY`) en staat nooit in een foutmelding.
Er staat geen data van LCSK in deze repo (de leveringsvoorwaarden staan geen doorlevering toe); de tests gebruiken een
synthetische export met dezelfde vorm (`proefbestand`).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from .._kern.versie import VERSIE

API = "https://api.skdb.nl/v1"
EXPORT = f"{API}/export/json"
SLEUTEL_ENV = "STUDIEKEUZEDATABASE_API_KEY"
# Art. 4.1 van de leveringsvoorwaarden (v25.1): de link bij de verplichte zin.
DOCUMENTATIE = "https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/"
LEVERANCIER = "Landelijk Centrum Studiekeuze"
# Art. 4.1 van de Algemene Leveringsvoorwaarden Data (v25.1): deze zin, met een link naar DOCUMENTATIE en het
# versienummer van de data, staat bij elke uiting die op de data steunt.
VERPLICHTE_ZIN = "Er is gebruik gemaakt van de data van Landelijk Centrum Studiekeuze."
USER_AGENT = f"onderwijsbronnen/{VERSIE} (+https://github.com/cedanl/onderwijsdata-chat)"

# De tabellen die elke export moet hebben; ontbreekt er een, dan is de vorm veranderd en komt er geen uitkomst.
VEREIST = frozenset(
    {
        "instellingen",
        "opleidingen",
        "opleidingvormen",
        "studies",
        "studievormen",
        "standaardonderwijsindelingvorm",
        "doorstroombachelormaster",
        "doorstroommbohbo",
        "lotingopleidingendecentraleselecties",
    }
)
# De bestandsnaam in de ZIP is bij één tabel ingekort (31 tekens).
_BESTAND = {"lotingopleidingendecentraleselecties": "lotingopleidingendecentralesele"}
_NAAM = re.compile(r"export-skdb-(?P<versie>\d+(?:\.\d+)+)-.*?(?P<datum>\d{4}-\d{2}-\d{2})")


class SkdbFout(RuntimeError):
    """De export is niet op te halen of heeft niet de vorm die dit module kent; er komt geen uitkomst."""


class GeenSleutel(SkdbFout):
    """Er is geen API-sleutel: niet als argument en niet in de omgeving."""


@dataclass(frozen=True)
class Herkomst:
    """Waar een export vandaan komt: de bestandsnaam van LCSK, met de dataversie en de exportdatum."""

    url: str
    bestand: str
    versie: str | None  # "26.6": het versienummer dat bij de bronvermelding hoort (art. 4.2)
    datum: str | None  # "2026-11-06": de dag van de export
    sha256: str
    opgehaald: str


def sleutel(waarde: str | None = None) -> str:
    """De API-sleutel: het argument, anders de omgeving. Zonder sleutel een `GeenSleutel`."""
    gevonden = (waarde or os.environ.get(SLEUTEL_ENV) or "").strip()
    if not gevonden:
        raise GeenSleutel(f"Geen sleutel voor de Studiekeuzedatabase: zet {SLEUTEL_ENV}.")
    return gevonden


def herkomst(inhoud: bytes, bestand: str, url: str = EXPORT) -> Herkomst:
    """De herkomst van een export uit zijn bestandsnaam (`export-skdb-26.6-api-v1-all-2026-11-06-json.zip`)."""
    gevonden = _NAAM.search(bestand or "")
    return Herkomst(
        url=url,
        bestand=bestand,
        versie=gevonden["versie"] if gevonden else None,
        datum=gevonden["datum"] if gevonden else None,
        sha256=hashlib.sha256(inhoud).hexdigest(),
        opgehaald=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _bestandsnaam(response: httpx.Response) -> str:
    kop = response.headers.get("content-disposition", "")
    gevonden = re.search(r'filename="?([^";]+)"?', kop)
    return gevonden.group(1) if gevonden else ""


def haal_op(api_sleutel: str | None = None, *, timeout: float = 180.0) -> tuple[bytes, Herkomst]:
    """De volledige export als ZIP, met zijn herkomst. Eén request; de sleutel gaat alleen in de header."""
    kop = {"Authorization": f"Bearer {sleutel(api_sleutel)}", "User-Agent": USER_AGENT}
    try:
        response = httpx.get(EXPORT, headers=kop, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as e:
        raise SkdbFout(f"De Studiekeuzedatabase is niet bereikbaar ({type(e).__name__}).") from None
    if response.status_code in (401, 403):
        raise SkdbFout(f"De Studiekeuzedatabase weigert de sleutel (HTTP {response.status_code}).")
    if response.status_code != 200:
        raise SkdbFout(f"De Studiekeuzedatabase gaf HTTP {response.status_code} op de export.")
    return response.content, herkomst(response.content, _bestandsnaam(response))


@dataclass
class Export:
    """Eén export: de ZIP in het geheugen, met een tabel pas gelezen als iemand erom vraagt."""

    inhoud: bytes
    herkomst: Herkomst
    _zip: zipfile.ZipFile = field(init=False, repr=False)
    _gelezen: dict[str, list[dict]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._zip = zipfile.ZipFile(io.BytesIO(self.inhoud))
        except zipfile.BadZipFile:
            raise SkdbFout("De export van de Studiekeuzedatabase is geen ZIP.") from None
        if ontbreekt := sorted(t for t in VEREIST if self._pad(t) not in self._zip.namelist()):
            raise SkdbFout(f"De export mist de tabel(len) {', '.join(ontbreekt)}: de vorm is veranderd.")

    @staticmethod
    def _pad(tabel: str) -> str:
        return f"data/{_BESTAND.get(tabel, tabel)}.json"

    @property
    def tabellen(self) -> list[str]:
        """De tabellen in deze export, met hun volle naam."""
        kort = {v: k for k, v in _BESTAND.items()}
        namen = (n.removeprefix("data/").removesuffix(".json") for n in self._zip.namelist() if n.startswith("data/"))
        return sorted(kort.get(n, n) for n in namen if n not in ("exporttabellen", "exportkolommen"))

    def rijen(self, tabel: str) -> list[dict]:
        """De records van één tabel, zoals LCSK ze levert (een lijst objecten)."""
        if tabel not in self._gelezen:
            pad = self._pad(tabel)
            if pad not in self._zip.namelist():
                raise SkdbFout(f"De tabel '{tabel}' staat niet in de export ({', '.join(self.tabellen)}).")
            rijen = json.loads(self._zip.read(pad))
            if not isinstance(rijen, list):
                raise SkdbFout(f"De tabel '{tabel}' is geen lijst records.")
            self._gelezen[tabel] = rijen
        return self._gelezen[tabel]

    def frame(self, tabel: str):
        """De tabel als pandas-DataFrame (pandas is een optionele afhankelijkheid: `onderwijsbronnen[analyse]`)."""
        import pandas as pd

        return pd.DataFrame(self.rijen(tabel))


def lees(inhoud: bytes, herkomst: Herkomst) -> Export:
    """Een opgehaalde export, gecontroleerd op de vereiste tabellen."""
    return Export(inhoud, herkomst)


def load(tabel: str = "opleidingen", api_sleutel: str | None = None):
    """Eén tabel van de nieuwste export als DataFrame: `skdb.load("opleidingvormen")`."""
    return lees(*haal_op(api_sleutel)).frame(tabel)
