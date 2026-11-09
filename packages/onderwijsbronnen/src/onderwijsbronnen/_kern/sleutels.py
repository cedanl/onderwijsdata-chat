"""Koppelsleutels die bronnen delen, met een pure normalisatie per sleutel (#958, relatielaag stap 2).

Eén lijst voor wat eerder op drie plekken stond (de voorvoegsels in `contract`, de connectoren van `relatie` in de chat
en de vrije tekst `combineerbaar_met`): welke canonieke sleutels er zijn, onder welke kolomnamen ze in de bronnen staan
en hoe hun waarden naar één vorm gaan (GM0344 ↔ 344, 2021SJ00 ↔ 2021/2022 ↔ 2021, 30020.0 ↔ 30020, `="00008"` ↔ 8).

Een bron zet per catalogusrecord met `in_record` het veld `_sleutels`: paren `{"kolom", "sleutel"}` in kolomvolgorde.
Eén kolom kan meer sleutels dragen: een CBS-regiokolom met gemeenten én provincies, of ERKENDEOPLEIDINGSCODE (RIO en
DUO), die in het ho de CROHO-code en in het mbo de crebo-code is; `paren` versmalt die laatste naar de sector van de
dataset. Zonder sleutel staat er `_sleutels_reden`, nooit stil een lege lijst.

Puur: geen netwerk en geen data. Of een waarde echt bestaat (een BRIN in het register, een gemeente in de indeling) en
hoeveel twee tabellen overlappen, toetst de chat (`relatie`) op geladen data.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .bestuur import Bestuurssleutel

# CBS-regiocodes van de provincies (CBS-gebiedsindeling); DUO en UWV schrijven de naam.
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
_PROVINCIE_NAAR_CODE = {naam.lower(): code for code, naam in PROVINCIES.items()} | {"fryslân": "PV21"}

# De reden bij een record zonder kolommen in de catalogus: dan is niet te zeggen welke sleutels de bestanden dragen.
GEEN_KOLOMMEN = "Geen kolommen vastgelegd in de catalogus: welke sleutels de bestanden dragen, is niet gecontroleerd."

_GEMEENTECODE = re.compile(r"^GM(\d{4})$")
_PROVINCIECODE = re.compile(r"^PV\d{2}$")
_ARBEIDSMARKTREGIOCODE = re.compile(r"^AM\d{2}$")
_CBS_SCHOOLJAAR = re.compile(r"^(\d{4})SJ\d{2}$")
_CBS_PERIODECODE = re.compile(r"^\d{4}[A-Z]{2}\d{2}$")  # ook kalenderjaar (JJ), kwartaal (KW), maand (MM)
_SCHOOLJAAR = re.compile(r"^(\d{4})\s*[/\-–]\s*'?(\d{4}|\d{2})$")  # 2021/2022, 2021/22, 2015/'16, 2021-2022
_SOI = re.compile(r"^(\d+)")  # 48100 en 48100-HBO-Bachelor: de rubriek is het getal vooraan


def _tekst(waarde) -> str | None:
    if waarde is None or (isinstance(waarde, float) and waarde != waarde):
        return None
    tekst = str(waarde).strip()
    return tekst or None


def norm_code(waarde) -> str | None:
    """Een code (BRIN, opleidingseenheid): gestript en in hoofdletters, 21pk is 21PK. Een code die als getal met lege
    cellen is gelezen (30020.0) is dezelfde code als 30020."""
    if isinstance(waarde, float) and waarde == waarde and waarde.is_integer():
        waarde = int(waarde)
    tekst = _tekst(waarde)
    return tekst.upper() if tekst else None


def norm_opleidingscode(waarde) -> str | None:
    """Een CROHO- of crebo-code: een getal, dus zonder voorloopnullen (04181 is 4181, 30020.0 is 30020)."""
    code = norm_code(waarde)
    return str(int(code)) if code and code.isdigit() else code


def norm_naam(waarde) -> str | None:
    """Een naam: gestript, in kleine letters. Spelling kan per bron verschillen; daarom een lagere confidence."""
    tekst = _tekst(waarde)
    return tekst.lower() if tekst else None


def norm_gemeente(waarde) -> str | None:
    """Gemeente als vier cijfers: CBS 'GM0344', DUO 344, '0344' of '344.0' worden '0344'."""
    tekst = _tekst(waarde)
    if tekst is None:
        return None
    if m := _GEMEENTECODE.match(tekst.upper()):
        return m.group(1)
    try:
        return f"{int(float(tekst)):04d}"
    except ValueError:
        return None


def norm_provincie(waarde) -> str | None:
    """Provincie als CBS-code: 'Utrecht' en 'PV26' zijn dezelfde provincie; onbekend (ook 'BELGIE') blijft None."""
    tekst = _tekst(waarde)
    if tekst is None:
        return None
    if _PROVINCIECODE.match(tekst.upper()):
        return tekst.upper() if tekst.upper() in PROVINCIES else None
    return _PROVINCIE_NAAR_CODE.get(tekst.lower())


def norm_arbeidsmarktregio(waarde) -> str | None:
    """CBS-code 'AM12' in hoofdletters, anders de naam ('Achterhoek' → 'achterhoek'). Code en naam vertalen hier niet
    naar elkaar: daarvoor is een indeling nodig (de chat heeft gemeente → arbeidsmarktregio)."""
    tekst = _tekst(waarde)
    if tekst is None:
        return None
    return tekst.upper() if _ARBEIDSMARKTREGIOCODE.match(tekst.upper()) else tekst.lower()


def _startjaar_uit_paar(start: str, eind: str) -> int | None:
    begin = int(start)
    volgend = begin + 1 if len(eind) == 4 else (begin + 1) % 100
    return begin if int(eind) == volgend else None


def norm_schooljaar(waarde) -> str | None:
    """Schooljaar als startjaar: 2021, '2021/2022', '2021/22' en '2021SJ00' zijn '2021'. Een andere CBS-periode
    (kalenderjaar 2021JJ00) en twee jaren die geen schooljaar vormen (2021/2023) zijn geen schooljaar."""
    tekst = _tekst(waarde)
    if tekst is None:
        return None
    if m := _CBS_SCHOOLJAAR.match(tekst):
        return m.group(1)
    if _CBS_PERIODECODE.match(tekst):
        return None
    if m := _SCHOOLJAAR.match(tekst):
        jaar = _startjaar_uit_paar(m.group(1), m.group(2))
    else:
        try:
            jaar = int(float(tekst))
        except ValueError:
            return None
    return str(jaar) if jaar is not None and 1900 <= jaar <= 2100 else None


def norm_bestuur(waarde) -> str | None:
    """Het bestuursnummer zoals RIO het schrijft ('00008'), via `Bestuurssleutel`; een XBRL-eenheid houdt haar BRIN
    (40833-25LR), want die drie rijen van één bestuur tel je nooit op."""
    sleutel = Bestuurssleutel.parse(waarde)
    return str(sleutel) if sleutel else None


def norm_soi(waarde) -> str | None:
    """De SOI-rubriek als getal: 48100 en '48100-HBO-Bachelor' (SKDB `soiId`) zijn rubriek '48100'."""
    tekst = norm_code(waarde)
    m = _SOI.match(tekst) if tekst else None
    return str(int(m.group(1))) if m else None


@dataclass(frozen=True)
class Sleutel:
    """Een sleutel die bronnen delen: waar hij staat, hoe zijn waarden naar één vorm gaan en hoe zeker dat is."""

    naam: str
    omschrijving: str
    kolommen: frozenset[str]  # in hoofdletters; hoofdletterongevoelig vergeleken
    bronnen: tuple[str, ...]  # de bronnen in dit pakket die hem dragen
    normaliseer: Callable[[object], str | None]
    confidence: float = 1.0  # 1.0: een code met een vaste vertaling; lager: een naam, spelling kan verschillen
    waardepatroon: re.Pattern[str] | None = None  # herkent de sleutel aan de waarden, zoals CBS RegioS
    sectoren: frozenset[str] = frozenset()  # leeg: elke sector; anders versmalt `paren` een kolom met meer sleutels
    op_naam: bool = False  # een naam, geen code: spelling en fusies breken hem; geen sleutel om een koppeling op te plannen


def _k(*namen: str) -> frozenset[str]:
    return frozenset(n.upper() for n in namen)


_ALLE: tuple[Sleutel, ...] = (
    Sleutel(
        "brin",
        "instelling: BRIN-code van vier tekens (21PK); DUO, RIO, SKDB en WOPI",
        # INSTELLINGCODE: de Studiekeuzedatabase; BRINCODE: het WOPI-bestand van UNL.
        _k(
            "INSTELLINGSCODE_ACTUEEL",
            "INSTELLINGSCODE",
            "INSTELLINGCODE",
            "BRIN",
            "BRINNUMMER",
            "BRIN_NUMMER",
            "BRINCODE",
        ),
        ("duo", "skdb", "unl"),
        norm_code,
    ),
    Sleutel(
        "vestiging",
        "vestiging van een instelling: BRIN-code plus twee cijfers (00BH01); de eerste vier tekens zijn de instelling",
        _k("VESTIGINGSCODE"),
        ("duo",),
        norm_code,
    ),
    Sleutel(
        "bestuur",
        "bestuur (bevoegd gezag): bestuursnummer, als RIO het schrijft met vijf tekens (00008)",
        # BEVOEGD GEZAG: de financiële verantwoording uit XBRL (#935).
        _k("BEVOEGD GEZAG NUMMER", "BEVOEGD_GEZAG_NUMMER", "BEVOEGD_GEZAG_CODE", "BEVOEGD GEZAG", "BESTUURSNUMMER"),
        ("duo",),
        norm_bestuur,
    ),
    Sleutel(
        "croho",
        "opleiding in het ho: CROHO-code (30020)",
        # CROHO/MASTER_CROHO: de uitkomst van get_studiekeuze (#957); OPLEIDINGCODE en MASTEROPLEIDINGCODE: de ruwe
        # export (#978). De studiecode van LCSK niet: die is niet altijd een CROHO-code.
        _k(
            "OPLEIDINGSCODE_ACTUEEL",
            "CROHO",
            "MASTER_CROHO",
            "OPLEIDINGCODE",
            "MASTEROPLEIDINGCODE",
            "ERKENDEOPLEIDINGSCODE",
        ),
        ("duo", "rio", "skdb"),
        norm_opleidingscode,
        sectoren=frozenset({"hbo", "wo"}),
    ),
    Sleutel(
        "crebo",
        "opleiding in het mbo: crebo-code (25180)",
        _k("BEROEPSOPLEIDING CODE", "ERKENDE OPLEIDING CODE", "CREBO", "CREBOCODE", "ERKENDEOPLEIDINGSCODE"),
        ("duo", "rio"),
        norm_opleidingscode,
        sectoren=frozenset({"mbo"}),
    ),
    Sleutel(
        "opleidingseenheid",
        "RIO-opleidingseenheid (opleidingseenheidcode)",
        _k("OPLEIDINGSEENHEIDCODE"),
        ("duo", "rio"),
        norm_code,
    ),
    Sleutel(
        "aangeboden_opleiding",
        "RIO-aangeboden opleiding (aangebodenOpleidingcode)",
        _k("AANGEBODEN_OPLEIDINGCODE", "AANGEBODENOPLEIDINGCODE"),
        ("duo", "rio"),
        norm_code,
    ),
    Sleutel(
        "gemeente",
        "gemeente: CBS-gemeentecode (GM0344 is gemeente 344)",
        _k("GEMEENTENUMMER", "GEMEENTECODE", "GEMEENTE_CODE", "GEMEENTENUMMER INSTELLING"),
        ("duo", "cbs", "skdb"),
        norm_gemeente,
        waardepatroon=_GEMEENTECODE,
    ),
    Sleutel(
        "provincie",
        "provincie: CBS-code PV20 tot PV31 of de naam (PV26 is Utrecht)",
        _k("PROVINCIENAAM", "PROVINCIE INSTELLING", "PROVINCIE", "WOONPROVINCIE"),
        ("duo", "cbs", "uwv"),
        norm_provincie,
        waardepatroon=_PROVINCIECODE,
    ),
    Sleutel(
        "arbeidsmarktregio",
        "arbeidsmarktregio van UWV en ROA: CBS-code (AM12) of de naam; niet het RPA-gebied van DUO",
        _k("ARBEIDSMARKTREGIO"),
        ("duo", "cbs"),
        norm_arbeidsmarktregio,
        confidence=0.8,
        waardepatroon=_ARBEIDSMARKTREGIOCODE,
    ),
    Sleutel(
        "schooljaar",
        "schooljaar als startjaar: CBS Perioden '2021SJ00', DUO 2021 of 2021/2022",
        # Niet DIPLOMAJAAR: DUO legt niet vast of dat een kalender- of studiejaar is (CH-41).
        _k("STUDIEJAAR", "STUDIEJAAR_LABEL", "JAAR", "PERIODEN"),
        ("duo", "cbs"),
        norm_schooljaar,
    ),
    Sleutel(
        "soi",
        "SOI-rubriek (Standaard Onderwijsindeling van CBS): het getal vooraan (48100)",
        _k("SOIID", "SOI", "SOI_CODE"),
        ("skdb",),
        norm_soi,
    ),
    Sleutel(
        "roa_opleidingstype",
        "ROA-opleidingstype van een studie ('hbo - ict'): de koppeling van de Studiekeuzedatabase naar ROA",
        _k("ROA_OPLEIDINGSTYPE", "OPLEIDINGTYPE"),
        ("skdb",),
        norm_naam,
        confidence=0.8,
    ),
    Sleutel(
        "instellingsnaam",
        "naam van de instelling; koppel liever op brin",
        _k("INSTELLINGSNAAM_ACTUEEL", "INSTELLINGSNAAM"),
        ("duo", "rio"),
        norm_naam,
        confidence=0.8,
        op_naam=True,
    ),
    Sleutel(
        "gemeentenaam",
        "naam van de gemeente; koppel liever op de gemeentecode",
        _k("GEMEENTENAAM", "GEMEENTE INSTELLING"),
        ("duo", "cbs"),
        norm_naam,
        confidence=0.8,
        op_naam=True,
    ),
)
SLEUTELS: dict[str, Sleutel] = {s.naam: s for s in _ALLE}

_OP_KOLOM: dict[str, tuple[Sleutel, ...]] = {}
for _s in _ALLE:
    for _kolom in sorted(_s.kolommen):
        _OP_KOLOM[_kolom] = (*_OP_KOLOM.get(_kolom, ()), _s)
KOLOMMEN = frozenset(_OP_KOLOM)

# Sectoren in de catalogus (`onderwijstype`); een onbekende waarde ('Allen', 'VO') versmalt niets.
_SECTOREN = {"MBO": {"mbo"}, "HBO": {"hbo"}, "WO": {"wo"}, "HO": {"hbo", "wo"}}


def van_kolom(kolom) -> tuple[Sleutel, ...]:
    """De sleutels die een kolom op naam draagt (hoofdletterongevoelig); () als hij geen sleutel is."""
    return _OP_KOLOM.get(str(kolom).strip().upper(), ())


def normaliseer(sleutel: str, waarde) -> str | None:
    """De waarde in de vorm van `sleutel`; None als ze die vorm niet heeft."""
    return SLEUTELS[sleutel].normaliseer(waarde)


def _sectoren(onderwijstype: Iterable[str] | None) -> set[str]:
    return {s for t in onderwijstype or () for s in _SECTOREN.get(str(t).upper(), ())}


def _versmald(kandidaten: tuple[Sleutel, ...], sectoren: set[str]) -> tuple[Sleutel, ...]:
    """Bij een kolom met meer sleutels alleen die van de sector van de dataset; past er geen, dan alle."""
    if len(kandidaten) < 2 or not sectoren:
        return kandidaten
    passend = tuple(s for s in kandidaten if not s.sectoren or s.sectoren & sectoren)
    return passend or kandidaten


def paren(kolommen: Iterable[str], onderwijstype: Iterable[str] | None = None) -> list[dict]:
    """De sleutelkolommen als `{"kolom", "sleutel"}`, uniek en in kolomvolgorde, op naam.

    `onderwijstype` (zoals in de catalogus: MBO, HBO, WO, HO) versmalt een kolom met meer sleutels: in een mbo-dataset
    is ERKENDEOPLEIDINGSCODE de crebo-code, in een ho-dataset de CROHO-code.
    """
    sectoren = _sectoren(onderwijstype)
    uit: list[dict] = []
    for kolom in kolommen:
        for sleutel in _versmald(van_kolom(kolom), sectoren):
            paar = {"kolom": str(kolom), "sleutel": sleutel.naam}
            if paar not in uit:
                uit.append(paar)
    return uit


def in_record(record: dict, sleutelparen: list[dict], reden: str) -> dict:
    """Het record met `_sleutels`; zonder sleutel ook `_sleutels_reden` (waarom niet), nooit stil leeg."""
    if onbekend := sorted({p["sleutel"] for p in sleutelparen} - set(SLEUTELS)):
        raise ValueError(f"geen canonieke sleutel: {onbekend}; kies uit {sorted(SLEUTELS)}")
    if not sleutelparen and not reden:
        raise ValueError("een record zonder sleutels heeft een reden nodig")
    uit = {**record, "_sleutels": list(sleutelparen)}
    if not sleutelparen:
        uit["_sleutels_reden"] = reden
    return uit


def uit_kolommen(record: dict, kolommen: Iterable[str], reden: str) -> dict:
    """`in_record` met de sleutels uit de kolomnamen, versmald naar het `onderwijstype` van het record."""
    return in_record(record, paren(kolommen, record.get("onderwijstype")), reden)


__all__ = [
    "GEEN_KOLOMMEN",
    "KOLOMMEN",
    "PROVINCIES",
    "SLEUTELS",
    "Sleutel",
    "in_record",
    "norm_arbeidsmarktregio",
    "norm_bestuur",
    "norm_code",
    "norm_gemeente",
    "norm_naam",
    "norm_opleidingscode",
    "norm_provincie",
    "norm_schooljaar",
    "norm_soi",
    "normaliseer",
    "paren",
    "uit_kolommen",
    "van_kolom",
]
