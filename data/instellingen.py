from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from riodata import duo

from core import actualiteit
from core.logging_util import foutkenmerk
from data import arbeidsmarktregio

logger = logging.getLogger(__name__)

# Maps instellingscode → {provincie, arbeidsmarktregio} via DUO address data.
# HO uses adressen_ho (instellingenho.csv); MBO uses adressen_mbo (instellingenmbo.csv).
# The arbeidsmarktregio comes from the address's gemeente (CBS indeling, the 35 regions of
# UWV and ROA), not from DUO's RPA-GEBIED NAAM: an older indeling ROA does not know (#454).
# Opgebouwd en ververst samen met het register hieronder (#901): de regiovergelijking legt die twee naast elkaar, en
# een adresbestand dat niet laadde bleef anders tot de pod herstartte ontbreken.
_ADRES_CACHE: dict[str, dict] | None = None

# Wat het adres van een instelling wel en niet zegt (#744). DUO kent één adres per BRIN, dat van de hoofdvestiging:
# Zone.college (31JC, Lochem) staat niet onder Doetinchem, al geeft het er 22 opleidingen. Een filter op de plaats,
# gemeente of provincie van een mbo-instelling neemt daarom ook de instellingen met een onderwijslocatie in dat gebied
# mee (tools/regiolocaties.py). Het model krijgt de twee zinnen mee waar het het adres leest: de kolomdefinitie en het
# profiel.
HOOFDVESTIGING = "Het adres is dat van de hoofdvestiging: DUO kent één adres per instelling (BRIN), geen nevenlocaties."
REGIO_VIA_LOCATIES = (
    "Vergelijk je mbo-instellingen per instelling met een filter op de plaats, gemeente, provincie of "
    "arbeidsmarktregio van de instelling, dan neemt de app ook de instellingen mee met een onderwijslocatie in dat "
    "gebied (RIO) en noemt ze in een vaste regel onder het antwoord; hun studentaantallen gelden per instelling, niet "
    "per locatie. Een totaal over instellingen heen blijft bij de hoofdvestiging."
)

# Handgemaakte referentielijsten: wanneer elk voor het laatst is bijgewerkt en
# waarvandaan (#316). Pas de datum aan bij elke wijziging aan een lijst;
# tests/test_referentielijsten.py bewaakt dit en de botsingen tussen de lijsten.
REFERENTIELIJSTEN: dict[str, dict[str, str]] = {
    "ALIASSEN": {"bijgewerkt": "2026-10-19", "bron": "handmatig: gangbare afkortingen per instelling"},
    "SRAM_ORGS": {
        "bijgewerkt": "2026-09-08",
        "bron": "SURF, Institutions using SRAM (servicedesk.surf.nl/wiki/spaces/IAM/pages/74226143)",
    },
    "DOMEINEN": {"bijgewerkt": "2026-09-26", "bron": "handmatig: e-maildomeinen van de instellingen"},
}

ALIASSEN: dict[str, list[str]] = {
    # WO
    "Vrije Universiteit Amsterdam": ["VU", "Vrije Universiteit", "VU Amsterdam"],
    "Universiteit van Amsterdam": ["UvA"],
    "Erasmus Universiteit Rotterdam": ["EUR", "Erasmus"],
    "Rijksuniversiteit Groningen": ["RUG"],
    "Universiteit Twente": ["UT"],
    "Universiteit Utrecht": ["UU"],
    "Universiteit Leiden": ["UL", "Leiden University"],
    "Universiteit Maastricht": ["UM"],
    "Technische Universiteit Delft": ["TU Delft"],
    "Technische Universiteit Eindhoven": ["TU/e", "TU Eindhoven"],
    "Wageningen University": ["WUR", "Wageningen"],
    "Radboud Universiteit Nijmegen": ["Radboud", "RU"],
    "Tilburg University": ["UvT", "Tilburg"],
    "Open Universiteit Nederland": ["OU", "Open Universiteit"],
    # HBO
    "Hogeschool van Amsterdam": ["HvA"],
    "Hogeschool Utrecht": ["HU"],
    "Hogeschool Rotterdam": ["HR"],
    "De Haagse Hogeschool": ["HHS", "Haagse"],
    "Hogeschool Inholland": ["Inholland"],
    "Hanzehogeschool Groningen": ["Hanze"],
    "Fontys Hogeschool": ["Fontys"],
    "Saxion Hogeschool": ["Saxion"],
    "Avans Hogeschool": ["Avans"],
    "Hogeschool van Arnhem en Nijmegen": ["HAN"],
    "Christelijke Hogeschool Windesheim": ["Windesheim"],
    "NHL Stenden Hogeschool": ["NHL Stenden", "NHL", "Stenden"],
    "Zuyd Hogeschool": ["Zuyd"],
    "Hogeschool Leiden": ["HL"],
    "Breda University of Applied Sciences": ["BUas", "NHTV"],
    "HZ University of Applied Sciences": ["HZ"],
    "Codarts, Hogeschool voor de Kunsten": ["Codarts"],
    "Hogeschool voor de Kunsten Utrecht": ["HKU"],
    # MBO
    "ROC van Amsterdam": ["ROCvA"],
    "ROC Midden Nederland": ["ROC MN"],
    "ROC Mondriaan": ["Mondriaan"],
    "ROC van Twente": ["RvT"],
    "ROC van Flevoland": ["ROC Flevoland"],
    "Alfa-college": ["Alfa"],
    "Deltion College": ["Deltion"],
    "Summa College": ["Summa"],
    "Grafisch Lyceum R'dam": ["GLR"],
    "Zadkine": ["Zadkine Rotterdam"],
    "ROC Graafschap College": ["Graafschap College", "Graafschap"],
}


# SRAM short-name → canonical instelling name, from SURF's "Institutions
# using SRAM" (https://servicedesk.surf.nl/wiki/spaces/IAM/pages/74226143).
# These appear in the SRAM OIDC `eduperson_entitlement` (urn:mace:surf.nl:sram:group:<orgname>:...).
# Only include instellingen that exist in the DUO registry (mapped by name/alias).
SRAM_ORGS: dict[str, str] = {
    "ahk": "Amsterdam University of the Arts",
    "avans": "Avans Hogeschool",
    "buas": "Breda University of Applied Sciences",
    "eur": "Erasmus Universiteit Rotterdam",
    "fontys": "Fontys Hogeschool",
    "han": "Hogeschool van Arnhem en Nijmegen",
    "hz": "HZ University of Applied Sciences",
    "hanze": "Hanzehogeschool Groningen",
    "hhs": "De Haagse Hogeschool",
    "hro": "Hogeschool Rotterdam",
    "hszuyd": "Zuyd Hogeschool",
    "hu": "Hogeschool Utrecht",
    "hva": "Hogeschool van Amsterdam",
    "inholland": "Hogeschool Inholland",
    "leidenuniv": "Universiteit Leiden",
    "leiden": "Hogeschool Leiden",
    "maastricht": "Universiteit Maastricht",
    "mondriaan": "ROC Mondriaan",
    "rocmn": "ROC Midden Nederland",
    "rocva": "ROC van Amsterdam",
    "rocvt": "ROC van Twente",
    "rocflevoland": "ROC van Flevoland",
    "nhlstenden": "NHL Stenden Hogeschool",
    "ou": "Open Universiteit Nederland",
    "ru": "Radboud Universiteit Nijmegen",
    "rug": "Rijksuniversiteit Groningen",
    "saxion": "Saxion Hogeschool",
    "talland": "Talland College",
    "tudelft": "Technische Universiteit Delft",
    "tue": "Technische Universiteit Eindhoven",
    "uu": "Universiteit Utrecht",
    "uva": "Universiteit van Amsterdam",
    "utwente": "Universiteit Twente",
    "uvt": "Tilburg University",
    "vu": "Vrije Universiteit Amsterdam",
    "windesheim": "Christelijke Hogeschool Windesheim",
    "wur": "Wageningen University",
}


# Email domain → canonical instelling name. Curated starter map; extend/verify
# as needed. Domains are matched exactly (case-insensitive) on the part after
# the "@" of the user's SRAM email / voperson_external_affiliation / email.
DOMEINEN: dict[str, list[str]] = {
    "Vrije Universiteit Amsterdam": ["vu.nl"],
    "Universiteit van Amsterdam": ["uva.nl"],
    "Erasmus Universiteit Rotterdam": ["eur.nl"],
    "Rijksuniversiteit Groningen": ["rug.nl"],
    "Universiteit Twente": ["utwente.nl"],
    "Universiteit Utrecht": ["uu.nl"],
    "Universiteit Leiden": ["leidenuniv.nl"],
    "Universiteit Maastricht": ["maastrichtuniversity.nl", "unimaas.nl"],
    "Technische Universiteit Delft": ["tudelft.nl"],
    "Technische Universiteit Eindhoven": ["tue.nl"],
    "Wageningen University": ["wur.nl"],
    "Radboud Universiteit Nijmegen": ["ru.nl"],
    "Tilburg University": ["tilburguniversity.edu", "uvt.nl"],
    "Open Universiteit Nederland": ["ou.nl"],
    "Amsterdam University of the Arts": ["ahk.nl"],
    "Hogeschool van Amsterdam": ["hva.nl"],
    "Avans Hogeschool": ["avans.nl"],
    "Hogeschool Utrecht": ["hu.nl"],
    "Hogeschool Rotterdam": ["hogeschoolrotterdam.nl", "hro.nl"],
    "De Haagse Hogeschool": ["hhs.nl"],
    "Hogeschool Inholland": ["inholland.nl"],
    "Hanzehogeschool Groningen": ["hanze.nl"],
    "Fontys Hogeschool": ["fontys.nl"],
    "Saxion Hogeschool": ["saxion.nl"],
    "Hogeschool van Arnhem en Nijmegen": ["han.nl"],
    "Christelijke Hogeschool Windesheim": ["windesheim.nl"],
    "NHL Stenden Hogeschool": ["nhlstenden.nl", "nhl.nl", "stenden.com"],
    "Zuyd Hogeschool": ["zuyd.nl"],
    "Hogeschool Leiden": ["hsleiden.nl"],
    "Breda University of Applied Sciences": ["buas.nl"],
    "HZ University of Applied Sciences": ["hz.nl"],
    "Talland College": ["talland.nl"],
    "ROC van Amsterdam": ["rocva.nl"],
    "ROC Midden Nederland": ["rocmn.nl"],
    "ROC van Twente": ["rocvantwente.nl"],
    "ROC van Flevoland": ["rocvanflevoland.nl"],
    "ROC Mondriaan": ["rocmondriaan.nl"],
}


# Het register, gebouwd uit live DUO-bestanden: na actualiteit.TTL opnieuw (#873), zodat een nieuwe, gefuseerde of
# hernoemde instelling niet pas na een herstart bekend is. `_opgehaald_op` is het moment van de laatste opbouw waarin
# elke bron laadde; None zolang er alleen een onvolledige was. `_geprobeerd_op` is de laatste poging: mislukt het
# herladen, dan blijft het oude register staan en volgt pas na _HERPOGING een nieuwe poging, niet bij elke aanroep.
_cache: list[dict] | None = None
_alias_lookup: dict[str, str] | None = None
_opgehaald_op: datetime | None = None
_geprobeerd_op: datetime | None = None
_HERPOGING = timedelta(hours=1)
_opbouw = threading.Lock()


def get_adres_lookup() -> dict[str, dict]:
    """{instellingscode: {provincie, arbeidsmarktregio, plaatsnaam, bevoegd_gezag}}, van dezelfde opbouw als het
    register: na actualiteit.TTL opnieuw, en na een mislukt adresbestand na _HERPOGING (#901)."""
    get_all()
    return _ADRES_CACHE or {}


def _build_adres_lookup() -> tuple[dict[str, dict], list[str]]:
    """{instellingscode: adres} uit de DUO-adresbestanden, en de bestanden die niet laadden."""
    lookup: dict[str, dict] = {}
    mislukt: list[str] = []
    for resource in ("adressen_ho", "adressen_mbo"):  # HO eerst: een code in beide houdt het HO-adres
        try:
            df = duo.load(resource, 1)
        except Exception as e:
            mislukt.append(f"{resource}/1")
            logger.warning("adres-lookup: %s niet beschikbaar: %s", resource, foutkenmerk(e))
            logger.debug("adres-lookup: %s niet beschikbaar", resource, exc_info=True)
            continue
        for _, row in df.iterrows():
            code = str(row.get("INSTELLINGSCODE") or "").strip()
            if code and code not in lookup:
                lookup[code] = _adres(row)
    return lookup, mislukt


def _adres(row) -> dict:
    return {
        "provincie": str(row.get("PROVINCIE") or "").strip() or None,
        "arbeidsmarktregio": arbeidsmarktregio.van_gemeente(row.get("GEMEENTENUMMER")),
        "plaatsnaam": str(row.get("PLAATSNAAM") or "").strip().upper() or None,
        # Het bestuur: de sleutel naar de Inspectie-oordelen per bevoegd gezag (#749).
        "bevoegd_gezag": _nummer(row.get("BEVOEGD GEZAG NUMMER")),
    }


def _nummer(waarde) -> int | None:
    try:
        getal = float(waarde)
    except (TypeError, ValueError):
        return None
    return int(getal) if getal == getal and getal.is_integer() else None


def _apply_sram_mappings(result: dict[str, dict]) -> dict[str, dict]:
    """Merge SRAM short names into aliassen and email domains into domeinen.

    Matches SRAM_ORGS/DOMEINEN targets against registry names and existing
    aliases by exact (case-insensitive) lookup, so a mismatch never produces a
    bogus prefilled instelling — it simply stays unmapped.
    """
    lookup: dict[str, dict] = {}
    for naam, inst in result.items():
        lookup.setdefault(naam.lower(), inst)
        for alias in inst.get("aliassen", []):
            lookup.setdefault(alias.lower(), inst)

    for short, target in SRAM_ORGS.items():
        inst = lookup.get(target.lower())
        if inst and short not in inst["aliassen"]:
            inst["aliassen"].append(short)

    for target, doms in DOMEINEN.items():
        inst = lookup.get(target.lower())
        if inst:
            inst["domeinen"] = sorted(set(inst.get("domeinen", []) + (doms or [])))
    return result


# De bestanden waar het register uit komt, in volgorde: een naam die al in een eerder bestand stond, houdt dat type.
_REGISTERBRONNEN = (
    ("p01hoinges", 0, "hbo", "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL"),
    ("p01hoinges", 1, "wo", "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL"),
    ("mbo-studenten-per-instelling", 0, "mbo", "INSTELLINGSCODE", "INSTELLINGSNAAM"),
)


def _voeg_toe(result: dict[str, dict], naam: str, code: str, soort: str, adres: dict[str, dict]) -> None:
    """Een instelling in het register, of een volgende code bij een naam die er al staat.

    DUO kent een instelling soms onder meer codes (Curio: 21CY en 25LX). `instellingscode` blijft de eerste, die van
    het adres en de regio; `instellingscodes` heeft ze allemaal, zodat elke code de instelling vindt (#929).
    """
    if naam in result:
        if code not in result[naam]["instellingscodes"]:
            result[naam]["instellingscodes"].append(code)
        return
    loc = adres.get(code, {})
    result[naam] = {
        "naam": naam,
        "type": soort,
        "aliassen": ALIASSEN.get(naam, []),
        "instellingscode": code,
        "instellingscodes": [code],
        "provincie": loc.get("provincie"),
        "arbeidsmarktregio": loc.get("arbeidsmarktregio"),
        "domeinen": [],
    }


def _build_registry() -> tuple[list[dict], dict[str, dict], list[str]]:
    """Het register, de adressen, en de DUO-bestanden die niet laadden (leeg als alles volledig is)."""
    adres, mislukt = _build_adres_lookup()
    result: dict[str, dict] = {}

    for dataset, resource, soort, code_col, naam_col in _REGISTERBRONNEN:
        try:
            df = duo.load(dataset, resource)
            for _, grp in df.groupby(code_col):
                _voeg_toe(result, grp[naam_col].iloc[0], str(grp[code_col].iloc[0]), soort, adres)
        except Exception as e:
            mislukt.append(f"{dataset}/{resource}")
            logger.warning(
                "registry: %s-instellingen (%s/%s) niet beschikbaar: %s", soort, dataset, resource, foutkenmerk(e)
            )
            logger.debug("registry: %s-instellingen (%s/%s) niet beschikbaar", soort, dataset, resource, exc_info=True)

    _apply_sram_mappings(result)
    return sorted(result.values(), key=lambda x: x["naam"].lower()), adres, mislukt


def _herladen_nodig() -> bool:
    """Is het register er niet, of ouder dan de TTL (of onvolledig) en de laatste poging lang genoeg geleden?"""
    if _cache is None:
        return True
    oud = _opgehaald_op is None or actualiteit.verlopen(_opgehaald_op)
    return oud and (_geprobeerd_op is None or actualiteit.nu() - _geprobeerd_op >= _HERPOGING)


def _herlaad() -> None:
    """Bouw het register opnieuw op; laadt een bron niet, dan blijft een bestaand register staan (#873)."""
    global _cache, _alias_lookup, _ADRES_CACHE, _opgehaald_op, _geprobeerd_op
    instellingen, adres, mislukt = _build_registry()
    _geprobeerd_op = actualiteit.nu()
    if _cache is not None and mislukt:
        logger.warning(
            "registry: herladen mislukt voor %s; het register van %s blijft staan, nieuwe poging over %s",
            ", ".join(mislukt),
            _opgehaald_op.isoformat(timespec="minutes") if _opgehaald_op else "een onvolledige opbouw",
            _HERPOGING,
        )
        return
    _cache, _alias_lookup, _ADRES_CACHE = instellingen, None, adres
    _opgehaald_op = None if mislukt else _geprobeerd_op


def get_all() -> list[dict]:
    """Alle instellingen uit DUO, alfabetisch; na actualiteit.TTL opnieuw opgebouwd (#873).

    Herlaadt een andere aanroep al, dan krijgt deze het bestaande register in plaats van te wachten.
    """
    if not _herladen_nodig():
        return _cache or []
    if not _opbouw.acquire(blocking=_cache is None):
        return _cache or []
    try:
        if _herladen_nodig():  # een andere aanroep kan net klaar zijn
            _herlaad()
    finally:
        _opbouw.release()
    return _cache or []


def _get_alias_lookup() -> dict[str, str]:
    global _alias_lookup
    instellingen = get_all()  # herlaadt het register na de TTL, en leegt dan ook deze lookup (#873)
    if _alias_lookup is None:
        lookup: dict[str, str] = {}
        for inst in instellingen:
            lookup[inst["naam"].lower()] = inst["naam"]
            for alias in inst["aliassen"]:
                lookup[alias.lower()] = inst["naam"]
        # De instellingscodes (BRIN) ook, maar een naam of alias die zo heet gaat voor (#929).
        for inst in instellingen:
            for code in inst["instellingscodes"]:
                lookup.setdefault(code.lower(), inst["naam"])
        _alias_lookup = lookup
    return _alias_lookup


# "de VU", "het Deltion": een lidwoord vóór de naam of alias hoort niet bij de sleutel; een naam die zelf
# met een lidwoord begint ("De Haagse Hogeschool") blijft eerst als geheel geprobeerd (#631).
_LIDWOORDEN = ("de ", "het ")


def _canoniek(naam: str) -> str | None:
    """De registernaam bij een naam, alias of instellingscode (hoofdletterongevoelig, lidwoord ervoor mag); None als
    onbekend."""
    lookup = _get_alias_lookup()
    sleutel = " ".join(naam.split()).lower()
    if sleutel in lookup:
        return lookup[sleutel]
    for lidwoord in _LIDWOORDEN:
        if sleutel.startswith(lidwoord) and sleutel[len(lidwoord) :] in lookup:
            return lookup[sleutel[len(lidwoord) :]]
    return None


def resolve_alias(naam: str) -> str:
    return _canoniek(naam) or naam


def instellingsprofiel(naam: str) -> dict | None:
    """Sector, provincie, arbeidsmarktregio en instellingscode van een profielinstelling (#448).

    Alleen een exacte naam, alias of instellingscode, hoofdletterongevoelig: een deel van een naam geeft
    niets, want een gegokte regio is erger dan geen regio. Onbekend → None.

    De regio is die van het instellingsadres in DUO ("Adressen van instellingen": één adres
    per instelling, geen vestigingen). Een instelling met vestigingen in meer provincies
    (Fontys, Inholland, NHL Stenden) krijgt de provincie en de arbeidsmarktregio van dat adres;
    de arbeidsmarktregio volgt uit de gemeente, in de namen van UWV en ROA (#454).
    Zonder adres blijven provincie en arbeidsmarktregio None.
    """
    canoniek = _canoniek(naam)
    inst = next((i for i in get_all() if i["naam"] == canoniek), None)
    if inst is None:
        return None
    return {
        "naam": inst["naam"],
        "sector": inst["type"],
        "provincie": inst["provincie"],
        "arbeidsmarktregio": inst["arbeidsmarktregio"],
        "instellingscode": inst["instellingscode"],
    }
