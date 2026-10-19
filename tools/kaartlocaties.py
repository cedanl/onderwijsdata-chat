"""Kaartlocaties: van de waarden in een locatiekolom naar de feature-id's van de GeoJSON (#628).

De kaart (`create_choropleth_map`) tekent tegen een GeoJSON waarvan de feature-id's CBS-codes zijn
(PV26, GM0344, CR17). CBS-tabellen hebben die codes, maar DUO en elke `query_data`-groepering op een
naamkolom hebben namen ("Utrecht", "'S-GRAVENHAGE"). Hier gaan beide naar dezelfde code, wordt het
niveau afgeleid uit wat past (niet alleen uit het voorvoegsel) en komt een waarde die nergens past naar
boven in plaats van als lege kaart met een succesmelding.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import relaties

# De volgorde is ook de voorkeur bij gelijke dekking: de lijst "Utrecht, Groningen" is een lijst provincies.
NIVEAUS = ("provincie", "gemeente", "corop")
_VOORVOEGSEL = {"PV": "provincie", "GM": "gemeente", "CR": "corop"}
_CODE = re.compile(r"^(PV|GM|CR)\d{2,4}$")
_ZONDER_TOEVOEGING = re.compile(r"\s*\([^)]*\)\s*$")  # 'hengelo (o)' → 'hengelo'
_VOORBEELDEN = 3
_GENOEMD = 8


class Geweigerd(ValueError):
    """De kaart kan niet getekend worden; de tekst is de melding voor het model."""


@dataclass(frozen=True)
class Locaties:
    niveau: str
    code_van: dict[str, str]  # de waarde zoals ze in de kolom staat → de feature-id
    onbekend: tuple[str, ...]  # waarden die niet op de kaart staan, in volgorde van voorkomen


def sleutel(naam: str) -> str:
    """Spelling-onafhankelijk: hoofdletters, apostrofs en punten tellen niet ('S-GRAVENHAGE = 's-Gravenhage, HENGELO (O) = Hengelo (O.))."""
    tekst = str(naam).replace("’", "'").casefold().replace(".", "")
    return re.sub(r"\s+", " ", tekst).strip().lstrip("'")


class _Gebied:
    """De features van één niveau: welke id's er zijn en onder welke naam."""

    def __init__(self, niveau: str, geojson: dict):
        self.niveau = niveau
        features = [f for f in geojson.get("features", []) if f.get("id")]
        self.ids = {str(f["id"]).upper() for f in features}
        self.namen: dict[str, str] = {}
        zonder_toevoeging: dict[str, list[str]] = {}
        for f in features:
            if naam := (f.get("properties") or {}).get("statnaam"):
                self.namen.setdefault(sleutel(naam), str(f["id"]))
                zonder_toevoeging.setdefault(_ZONDER_TOEVOEGING.sub("", sleutel(naam)), []).append(str(f["id"]))
        # DUO schrijft 'HENGELO' waar CBS 'Hengelo (O.)' heeft; alleen als één gebied zo heet, anders is het een gok.
        self.kort = {k: ids[0] for k, ids in zonder_toevoeging.items() if len(ids) == 1}

    def code(self, waarde: str) -> str | None:
        if waarde.upper() in self.ids:
            return waarde.upper()
        if code := self.namen.get(sleutel(waarde)) or self.kort.get(sleutel(waarde)):
            return code
        if self.niveau == "provincie":
            code = relaties.norm_provincie(waarde)  # 'Friesland' staat in de GeoJSON als 'Fryslân'
        elif self.niveau == "gemeente" and (nummer := relaties.norm_gemeente(waarde)):
            code = f"GM{nummer}"  # DUO schrijft het gemeentenummer: 344 of '344.0'
        else:
            code = None
        return code if code and code.upper() in self.ids else None


def _voorvoegsel_niveau(waarden: list[str]) -> str | None:
    for waarde in waarden:
        if m := _CODE.match(waarde.strip().upper()):
            return _VOORVOEGSEL[m.group(1)]
    return None


def _voorbeelden(waarden: list[str]) -> str:
    return ", ".join(f"'{w}'" for w in waarden[:_VOORBEELDEN])


def _dekking(gebied: _Gebied, waarden: list[str]) -> dict[str, str]:
    return {w: c for w in waarden if (c := gebied.code(w))}


def _beste(waarden: list[str], laad: Callable[[str], dict]) -> tuple[_Gebied, dict[str, str]]:
    """Het niveau waar de meeste waarden op passen; stopt zodra één niveau alles dekt."""
    beste: tuple[_Gebied, dict[str, str]] | None = None
    for niveau in NIVEAUS:
        gebied = _Gebied(niveau, laad(niveau))
        gevonden = _dekking(gebied, waarden)
        if beste is None or len(gevonden) > len(beste[1]):
            beste = (gebied, gevonden)
        if len(gevonden) == len(waarden):
            break
    assert beste is not None
    return beste


def vertaal(waarden: list[str], level: str, laad: Callable[[str], dict]) -> Locaties:
    """De feature-id per waarde, het niveau en wat niet op de kaart staat; `Geweigerd` zonder één treffer."""
    waarden = list(dict.fromkeys(waarden))
    niveau = level if level != "auto" else _voorvoegsel_niveau(waarden)
    if niveau:
        gebied = _Gebied(niveau, laad(niveau))
        gevonden = _dekking(gebied, waarden)
    else:
        gebied, gevonden = _beste(waarden, laad)
    if not gevonden:
        voorbeeld = f"bijv. {_voorbeelden(waarden)}"
        if level == "auto":
            raise Geweigerd(
                f"Geen van de {len(waarden)} locaties is te herkennen als provincie, gemeente of COROP-gebied "
                f"({voorbeeld}). Gebruik namen of CBS-codes (PV20, GM0344, CR01)."
            )
        raise Geweigerd(
            f"Geen van de {len(waarden)} locaties past bij niveau '{level}' ({voorbeeld}). "
            "Kies het niveau waar de waarden bij horen, of laat level op 'auto'."
        )
    return Locaties(gebied.niveau, gevonden, tuple(w for w in waarden if w not in gevonden))


def melding_onbekend(locaties: Locaties, totaal: int) -> str:
    """Wat er niet op de kaart staat, voor het model; leeg als alles past."""
    if not locaties.onbekend:
        return ""
    genoemd = ", ".join(locaties.onbekend[:_GENOEMD]) + (", …" if len(locaties.onbekend) > _GENOEMD else "")
    return f" {len(locaties.onbekend)} van {totaal} locaties staan niet op de kaart: {genoemd}."
