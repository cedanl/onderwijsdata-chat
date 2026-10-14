"""Relatielaag, stap 1: wat hangt aan wat tussen CBS, DUO en RIO, als tool in plaats van een gok (#63).

De kennis bestond al, verspreid: het instellingsregister (`data/instellingen.py`: naam, alias,
BRIN-code, provincie en arbeidsmarktregio uit DUO-adressen), de CBS-gebiedsindeling
(`data/arbeidsmarktregio.py`: gemeente → arbeidsmarktregio), de periodespelling per bron
(`tools/periode.py`) en de CBS-regiocodes. Het model kon er niet naar vragen en verzon joins
of zei "geen data". Hier staan de sleutels die bronnen delen (connectoren), hoe hun waarden
naar elkaar vertalen (GM0344 ↔ 344, 2021SJ00 ↔ 2021) en wat eraan hangt.

`relatie(data_key)` zegt per sleutelkolom van een geladen tabel wat eraan hangt en hoeveel
waarden het register of de indeling kent. `relatie(data_key, andere_key)` noemt de kolommen
die beide tabellen als dezelfde sleutel dragen, met kardinaliteit en overlap: kandidaten voor
een koppeling. De tool koppelt zelf niets; dat blijft een expliciete stap (query_data of
run_analysis). Elke uitkomst draagt `basis` en `confidence`: handmatig vastgelegd is 1.0.
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from data import arbeidsmarktregio, instellingen

from . import fouten, periode, store

logger = logging.getLogger(__name__)

HANDMATIG = "handmatig"
GEDETECTEERD = "gedetecteerd"
# Zoveel waarden hoogstens per kolom genormaliseerd voor dekking en overlap; genoeg voor elke bron in de chat.
_MAX_WAARDEN = 200_000

# CBS-regiocodes van de provincies (CBS-gebiedsindeling); DUO schrijft de naam.
PROVINCIES = {
    "PV20": "Groningen",
    "PV21": "Friesland",
    "PV22": "Drenthe",
    "PV23": "Overijssel",
    "PV24": "Flevoland",
    "PV25": "Gelderland",
    "PV26": "Utrecht",
    "PV27": "Noord-Holland",
    "PV28": "Zuid-Holland",
    "PV29": "Zeeland",
    "PV30": "Noord-Brabant",
    "PV31": "Limburg",
}
_PROVINCIE_NAAR_CODE = {naam.lower(): code for code, naam in PROVINCIES.items()}
_PROVINCIE_NAAR_CODE["fryslân"] = "PV21"
_GEMEENTECODE = re.compile(r"^GM(\d{4})$")
_PROVINCIECODE = re.compile(r"^PV\d{2}$")


def _tekst(v) -> str | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    tekst = str(v).strip()
    return tekst or None


def norm_code(v) -> str | None:
    """Een BRIN- of opleidingscode: gestript, hoofdletters; 21pk en 21PK zijn dezelfde instelling."""
    tekst = _tekst(v)
    return tekst.upper() if tekst else None


def norm_naam(v) -> str | None:
    tekst = _tekst(v)
    return tekst.lower() if tekst else None


def norm_gemeente(v) -> str | None:
    """Gemeente als vier cijfers: CBS 'GM0344', DUO 344 of '344.0' worden '0344'."""
    tekst = _tekst(v)
    if tekst is None:
        return None
    if m := _GEMEENTECODE.match(tekst.upper()):
        return m.group(1)
    try:
        return f"{int(float(tekst)):04d}"
    except ValueError:
        return None


def norm_provincie(v) -> str | None:
    """Provincie als CBS-code: 'Utrecht' en 'PV26' zijn dezelfde provincie; onbekend blijft None."""
    tekst = _tekst(v)
    if tekst is None:
        return None
    if _PROVINCIECODE.match(tekst.upper()):
        return tekst.upper() if tekst.upper() in PROVINCIES else None
    return _PROVINCIE_NAAR_CODE.get(tekst.lower())


def norm_schooljaar(v) -> str | None:
    """Schooljaar als startjaar: 2021, '2021/2022', '2021/22' en '2021SJ00' zijn 2021; een kalenderjaarcode niet."""
    tekst = _tekst(v)
    if tekst is None:
        return None
    if periode.is_periodecode(tekst):
        jaar = periode.startjaar("cbs", tekst)
        return str(jaar) if jaar is not None else None
    jaar = periode.startjaar_van_spelling(tekst)
    if jaar is None:
        try:
            jaar = int(float(tekst))
        except ValueError:
            return None
    return str(jaar) if 1900 <= jaar <= 2100 else None


@dataclass(frozen=True)
class Connector:
    """Een sleutel die bronnen delen: de kolomnamen waaronder hij voorkomt en hoe zijn waarden vertalen."""

    naam: str
    kolommen: frozenset[str]  # hoofdletterongevoelig vergeleken
    bronnen: tuple[str, ...]
    koppelt_aan: tuple[str, ...]  # wat eraan hangt, met de basis
    normaliseer: Callable[[Any], str | None]
    confidence: float  # 1.0: codes met een vaste vertaling; lager: namen, spelling kan verschillen
    waardepatroon: re.Pattern | None = None  # herkent de sleutel aan de waarden, zoals CBS RegioS


CONNECTOREN: tuple[Connector, ...] = (
    Connector(
        "instellingscode",
        frozenset({"INSTELLINGSCODE_ACTUEEL", "INSTELLINGSCODE", "BRIN", "BRINNUMMER", "BRIN_NUMMER"}),
        ("duo",),
        (
            "naam, sector, provincie en arbeidsmarktregio via het instellingsregister "
            "(DUO-adressen plus CBS-gebiedsindeling; aliassen handmatig)",
            "RIO: bestuur, instellingen en vestigingen op naam via get_rio_instelling",
        ),
        norm_code,
        1.0,
    ),
    Connector(
        "instellingsnaam",
        frozenset({"INSTELLINGSNAAM_ACTUEEL", "INSTELLINGSNAAM"}),
        ("duo", "rio"),
        ("instellingscode via het instellingsregister (naam of alias, hoofdletterongevoelig)",),
        norm_naam,
        0.8,
    ),
    Connector(
        "gemeente",
        frozenset({"GEMEENTENUMMER", "GEMEENTECODE", "GEMEENTE_CODE"}),
        ("duo", "cbs"),
        (
            "arbeidsmarktregio via de CBS-gebiedsindeling (data/arbeidsmarktregio.py)",
            "CBS RegioS als 'GM' plus vier cijfers (GM0344 is gemeente 344)",
        ),
        norm_gemeente,
        1.0,
        _GEMEENTECODE,
    ),
    Connector(
        "gemeentenaam",
        frozenset({"GEMEENTENAAM"}),
        ("duo", "cbs"),
        ("gemeentenummer via dezelfde tabel, als die beide kolommen heeft; spelling kan per bron verschillen",),
        norm_naam,
        0.8,
    ),
    Connector(
        "provincie",
        frozenset({"PROVINCIENAAM", "PROVINCIE INSTELLING", "PROVINCIE"}),
        ("duo", "cbs"),
        ("CBS RegioS als 'PV' plus twee cijfers (PV26 is Utrecht), vaste lijst van twaalf",),
        norm_provincie,
        1.0,
        _PROVINCIECODE,
    ),
    Connector(
        "schooljaar",
        frozenset({"STUDIEJAAR", "STUDIEJAAR_LABEL", "JAAR", "DIPLOMAJAAR", "PERIODEN"}),
        ("duo", "cbs"),
        ("CBS Perioden als '<startjaar>SJ00', DUO als startjaar of label 2021/2022 (tools/periode.py)",),
        norm_schooljaar,
        1.0,
    ),
    Connector(
        "erkende_opleiding",
        frozenset({"ERKENDEOPLEIDINGSCODE", "OPLEIDINGSCODE_ACTUEEL", "BEROEPSOPLEIDING CODE"}),
        ("duo", "rio"),
        ("RIO opleidingserkenningen (erkendeopleidingscode); CROHO voor ho, crebo voor mbo: controleer de overlap",),
        norm_code,
        0.8,
    ),
    Connector(
        "opleidingseenheid",
        frozenset({"OPLEIDINGSEENHEIDCODE"}),
        ("duo", "rio"),
        ("RIO opleidingen, opleidingsfasen, -groepen en -onderdelen (opleidingseenheidcode)",),
        norm_code,
        1.0,
    ),
    Connector(
        "aangeboden_opleiding",
        frozenset({"AANGEBODEN_OPLEIDINGCODE", "AANGEBODENOPLEIDINGCODE"}),
        ("duo", "rio"),
        ("RIO aangeboden opleidingen en cohorten (aangebodenOpleidingcode)",),
        norm_code,
        1.0,
    ),
)
_OP_NAAM = {kolom.upper(): c for c in CONNECTOREN for kolom in c.kolommen}


def _waarden(reeks: pd.Series, connector: Connector) -> list[str]:
    """De genormaliseerde waarden van een kolom, zonder lege; begrensd."""
    uit = (connector.normaliseer(v) for v in reeks.head(_MAX_WAARDEN).tolist())
    return [w for w in uit if w is not None]


def connector_van(kolom: str, reeks: pd.Series) -> Connector | None:
    """De connector van een kolom: op naam, anders op de waarden (CBS RegioS met GM- of PV-codes)."""
    if (c := _OP_NAAM.get(str(kolom).strip().upper())) is not None:
        return c
    tekst = reeks.dropna().astype(str).str.strip().str.upper()
    if tekst.empty:
        return None
    for c in CONNECTOREN:
        if c.waardepatroon is not None and tekst.str.fullmatch(c.waardepatroon.pattern).all():
            return c
    return None


def _dekking(connector: Connector, waarden: list[str]) -> dict | None:
    """Hoeveel van de waarden het register of de indeling kent; None als er geen naslag is."""
    uniek = set(waarden)
    if not uniek:
        return None
    if connector.naam == "instellingscode":
        try:
            bekend = {str(i.get("instellingscode") or "").upper() for i in instellingen.get_all()}
        except Exception as e:  # het register laadt over het netwerk; zonder register geen dekking, geen gok
            logger.warning("relatie: instellingsregister niet beschikbaar: %s", type(e).__name__)
            return None
        return {"naslag": "instellingsregister", "bekend": len(uniek & bekend), "van": len(uniek)}
    if connector.naam == "gemeente":
        bekend = set(arbeidsmarktregio.gemeenten())
        return {"naslag": "arbeidsmarktregio-indeling", "bekend": len(uniek & bekend), "van": len(uniek)}
    if connector.naam == "provincie":
        return {"naslag": "CBS-provinciecodes", "bekend": len(uniek & set(PROVINCIES)), "van": len(uniek)}
    return None


@dataclass(frozen=True)
class Sleutel:
    kolom: str
    connector: Connector
    waarden: list[str]

    def als_dict(self) -> dict:
        uit = {
            "kolom": self.kolom,
            "sleutel": self.connector.naam,
            "bronnen": list(self.connector.bronnen),
            "koppelt_aan": list(self.connector.koppelt_aan),
            "basis": HANDMATIG,
            "confidence": self.connector.confidence,
            "uniek": len(set(self.waarden)),
        }
        if (dekking := _dekking(self.connector, self.waarden)) is not None:
            uit["dekking"] = dekking
        return uit


def sleutels(df: pd.DataFrame) -> list[Sleutel]:
    """De sleutelkolommen van een tabel, in kolomvolgorde."""
    gevonden = ((str(kolom), connector_van(str(kolom), df[kolom])) for kolom in df.columns)
    return [Sleutel(kolom, c, _waarden(df[kolom], c)) for kolom, c in gevonden if c is not None]


def _kardinaliteit(links: list[str], rechts: list[str]) -> str:
    een_links = len(links) == len(set(links))
    een_rechts = len(rechts) == len(set(rechts))
    return {
        (True, True): "one_to_one",
        (True, False): "one_to_many",
        (False, True): "many_to_one",
        (False, False): "many_to_many",
    }[(een_links, een_rechts)]


def _pct(deel: int, geheel: int) -> float:
    return round(100 * deel / geheel, 1) if geheel else 0.0


def koppelingen(links_key: str, links: list[Sleutel], rechts_key: str, rechts: list[Sleutel]) -> list[dict]:
    """Kolomparen die dezelfde sleutel dragen, met kardinaliteit en overlap van de genormaliseerde waarden."""
    uit = []
    for a in links:
        for b in rechts:
            if a.connector is not b.connector:
                continue
            la, lb = set(a.waarden), set(b.waarden)
            gedeeld = len(la & lb)
            uit.append(
                {
                    "links": {"data_key": links_key, "kolom": a.kolom},
                    "rechts": {"data_key": rechts_key, "kolom": b.kolom},
                    "sleutel": a.connector.naam,
                    "type": _kardinaliteit(a.waarden, b.waarden),
                    "overlap": {
                        "gedeeld": gedeeld,
                        "links_in_rechts_pct": _pct(gedeeld, len(la)),
                        "rechts_in_links_pct": _pct(gedeeld, len(lb)),
                    },
                    "basis": GEDETECTEERD if a.kolom.upper() != b.kolom.upper() else HANDMATIG,
                    "confidence": a.connector.confidence,
                }
            )
    return sorted(uit, key=lambda k: (-k["overlap"]["gedeeld"], k["sleutel"]))


def _tabel(data_key: str) -> pd.DataFrame | str:
    df = store.get(data_key)
    return df if isinstance(df, pd.DataFrame) else fouten.onbekende_key(data_key)


def relatie(data_key: str, andere_key: str | None = None) -> str:
    """Wat aan de sleutelkolommen van een tabel hangt, en met `andere_key` de koppelkandidaten tussen twee.

    Koppelt niets: de kandidaten gaan naar het log en naar het model, de koppeling zelf is een eigen stap.
    """
    df = _tabel(data_key)
    if isinstance(df, str):
        return df
    eigen = sleutels(df)
    uit: dict = {
        "data_key": data_key,
        "sleutels": [s.als_dict() for s in eigen],
        "zonder_sleutel": [str(k) for k in df.columns if k not in {s.kolom for s in eigen}],
    }
    if not eigen:
        uit["melding"] = "Geen bekende sleutelkolom (instellingscode, gemeente, provincie, schooljaar, opleidingscode)."
    if andere_key is not None:
        ander = _tabel(andere_key)
        if isinstance(ander, str):
            return ander
        kandidaten = koppelingen(data_key, eigen, andere_key, sleutels(ander))
        uit["koppelingen"] = kandidaten
        if not kandidaten:
            uit["melding_koppeling"] = (
                "Geen gedeelde sleutel tussen de twee tabellen. Koppel niet op een kolom die alleen op naam lijkt; "
                "zoek een tabel met een gedeelde sleutel of vraag per bron apart."
            )
        # Kandidaten in het log, geen waarden (#475): alleen welke sleutels en hoeveel overlap.
        logger.info(
            "RELATIE kandidaten=%d %s",
            len(kandidaten),
            " ".join(f"{k['sleutel']}:{k['type']}:{k['overlap']['gedeeld']}" for k in kandidaten),
        )
    return json.dumps(uit, ensure_ascii=False, separators=(",", ":"), default=str)
