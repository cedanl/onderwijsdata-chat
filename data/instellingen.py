from __future__ import annotations

import logging

from riodata import duo

logger = logging.getLogger(__name__)

# Maps instellingscode → {provincie, arbeidsmarktregio} via DUO address data.
# HO uses adressen_ho (instellingenho.csv); MBO uses adressen_mbo (instellingenmbo.csv).
# RPA-GEBIED NAAM is the official UWV arbeidsmarktregio name (35 regions).
_ADRES_CACHE: dict[str, dict] | None = None

ALIASSEN: dict[str, list[str]] = {
    # WO
    "Vrije Universiteit Amsterdam": ["VU", "Vrije Universiteit"],
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
    # MBO
    "ROC van Amsterdam": ["ROCvA"],
    "ROC Midden Nederland": ["ROC MN"],
    "ROC Mondriaan": ["Mondriaan"],
    "ROC van Twente": ["RvT"],
    "Alfa-college": ["Alfa"],
    "Deltion College": ["Deltion"],
    "Summa College": ["Summa"],
    "Grafisch Lyceum R'dam": ["GLR"],
    "Zadkine": ["Zadkine Rotterdam"],
}


# SRAM short-name → canonical instelling name, from SURF's "Institutions
# using SRAM" (https://servicedesk.surf.nl/wiki/spaces/IAM/pages/74226143).
# These appear in the SRAM OIDC `eduperson_entitlement` (urn:mace:surf.nl:sram:group:<orgname>:...).
# Only include instellingen that exist in the DUO registry (mapped by name/alias).
SRAM_ORGS: dict[str, str] = {
    "ahk": "Amsterdam University of the Arts",
    "avans": "Avans Hogeschool",
    "han": "Hogeschool van Arnhem en Nijmegen",
    "hanze": "Hanzehogeschool Groningen",
    "hhs": "De Haagse Hogeschool",
    "hro": "Hogeschool Rotterdam",
    "hszuyd": "Zuyd Hogeschool",
    "hu": "Hogeschool Utrecht",
    "hva": "Hogeschool van Amsterdam",
    "inholland": "Hogeschool Inholland",
    "leidenuniv": "Universiteit Leiden",
    "nhlstenden": "NHL Stenden Hogeschool",
    "ou": "Open Universiteit Nederland",
    "ru": "Radboud Universiteit Nijmegen",
    "rug": "Rijksuniversiteit Groningen",
    "saxion": "Saxion Hogeschool",
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
    "Hogeschool van Amsterdam": ["hva.nl"],
    "Hogeschool Utrecht": ["hu.nl"],
    "Hogeschool Rotterdam": ["hogeschoolrotterdam.nl", "hro.nl"],
    "De Haagse Hogeschool": ["hhs.nl"],
    "Hogeschool Inholland": ["inholland.nl"],
    "Hanzehogeschool Groningen": ["hanze.nl"],
    "Fontys Hogeschool": ["fontys.nl"],
    "Saxion Hogeschool": ["saxion.nl"],
    "Hogeschool van Arnhem en Nijmegen": ["han.nl"],
    "Christelijke Hogeschool Windesheim": ["windesheim.nl"],
    "NHL Stenden Hogeschool": ["nhlstenden.nl"],
    "Zuyd Hogeschool": ["zuyd.nl"],
    "Hogeschool Leiden": ["hsleiden.nl"],
    "Breda University of Applied Sciences": ["buas.nl"],
    "HZ University of Applied Sciences": ["hz.nl"],
}


def _extract_domain(email: str | None) -> str | None:
    """Return the lowercase domain part of an email address, else None."""
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].strip().lower() or None


def sram_org_to_instelling(short: str | None) -> str | None:
    """Map an SRAM short name (from entitlement) to a canonical instelling name."""
    if not short:
        return None
    return SRAM_ORGS.get(short.strip().lower())


def instelling_for_email(email_or_domein: str | None) -> str | None:
    """Map an email address or domain to a canonical instelling name."""
    domein = _extract_domain(email_or_domein) or (email_or_domein and email_or_domein.strip().lower())
    if not domein:
        return None
    for naam, doms in DOMEINEN.items():
        if domein in doms:
            return naam
    return None


_cache: list[dict] | None = None
_alias_lookup: dict[str, str] | None = None


def get_adres_lookup() -> dict[str, dict]:
    """Return {instellingscode: {provincie, arbeidsmarktregio}} — cached."""
    global _ADRES_CACHE
    if _ADRES_CACHE is None:
        _ADRES_CACHE = _build_adres_lookup()
    return _ADRES_CACHE


def _build_adres_lookup() -> dict[str, dict]:
    """Return {instellingscode: {provincie, arbeidsmarktregio, plaatsnaam}} from DUO address data."""
    lookup: dict[str, dict] = {}

    try:
        df = duo.load("adressen_ho", 1)
        for _, row in df.iterrows():
            code = str(row.get("INSTELLINGSCODE") or "").strip()
            if code:
                lookup[code] = {
                    "provincie": str(row.get("PROVINCIE") or "").strip() or None,
                    "arbeidsmarktregio": str(row.get("RPA-GEBIED NAAM") or "").strip() or None,
                    "plaatsnaam": str(row.get("PLAATSNAAM") or "").strip().upper() or None,
                }
    except Exception:
        logger.warning("adres-lookup: adressen_ho niet beschikbaar", exc_info=True)

    try:
        df = duo.load("adressen_mbo", 1)
        for _, row in df.iterrows():
            code = str(row.get("INSTELLINGSCODE") or "").strip()
            if code and code not in lookup:
                lookup[code] = {
                    "provincie": str(row.get("PROVINCIE") or "").strip() or None,
                    "arbeidsmarktregio": str(row.get("RPA-GEBIED NAAM") or "").strip() or None,
                    "plaatsnaam": str(row.get("PLAATSNAAM") or "").strip().upper() or None,
                }
    except Exception:
        logger.warning("adres-lookup: adressen_mbo niet beschikbaar", exc_info=True)

    return lookup


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


def _build_registry() -> list[dict]:
    adres = _build_adres_lookup()
    result: dict[str, dict] = {}

    try:
        df_hbo = duo.load("p01hoinges", 0)
        for _, grp in df_hbo.groupby("INSTELLINGSCODE_ACTUEEL"):
            naam = grp["INSTELLINGSNAAM_ACTUEEL"].iloc[0]
            code = str(grp["INSTELLINGSCODE_ACTUEEL"].iloc[0])
            loc = adres.get(code, {})
            result[naam] = {
                "naam": naam, "type": "hbo", "aliassen": ALIASSEN.get(naam, []),
                "instellingscode": code,
                "provincie": loc.get("provincie"),
                "arbeidsmarktregio": loc.get("arbeidsmarktregio"),
                "domeinen": [],
            }
    except Exception:
        logger.warning("registry: HBO-instellingen (p01hoinges/0) niet beschikbaar", exc_info=True)

    try:
        df_wo = duo.load("p01hoinges", 1)
        for _, grp in df_wo.groupby("INSTELLINGSCODE_ACTUEEL"):
            naam = grp["INSTELLINGSNAAM_ACTUEEL"].iloc[0]
            code = str(grp["INSTELLINGSCODE_ACTUEEL"].iloc[0])
            if naam not in result:
                loc = adres.get(code, {})
                result[naam] = {
                    "naam": naam, "type": "wo", "aliassen": ALIASSEN.get(naam, []),
                    "instellingscode": code,
                    "provincie": loc.get("provincie"),
                    "arbeidsmarktregio": loc.get("arbeidsmarktregio"),
                    "domeinen": [],
                }
    except Exception:
        logger.warning("registry: WO-instellingen (p01hoinges/1) niet beschikbaar", exc_info=True)

    try:
        df_mbo = duo.load("mbo-studenten-per-instelling", 0)
        for _, grp in df_mbo.groupby("INSTELLINGSCODE"):
            naam = grp["INSTELLINGSNAAM"].iloc[0]
            code = str(grp["INSTELLINGSCODE"].iloc[0])
            if naam not in result:
                loc = adres.get(code, {})
                result[naam] = {
                    "naam": naam, "type": "mbo", "aliassen": ALIASSEN.get(naam, []),
                    "instellingscode": code,
                    "provincie": loc.get("provincie"),
                    "arbeidsmarktregio": loc.get("arbeidsmarktregio"),
                    "domeinen": [],
                }
    except Exception:
        logger.warning("registry: MBO-instellingen niet beschikbaar", exc_info=True)

    _apply_sram_mappings(result)
    return sorted(result.values(), key=lambda x: x["naam"].lower())


def get_all() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = _build_registry()
    return _cache


def _get_alias_lookup() -> dict[str, str]:
    global _alias_lookup
    if _alias_lookup is None:
        lookup: dict[str, str] = {}
        for inst in get_all():
            lookup[inst["naam"].lower()] = inst["naam"]
            for alias in inst["aliassen"]:
                lookup[alias.lower()] = inst["naam"]
        _alias_lookup = lookup
    return _alias_lookup


def resolve_alias(naam: str) -> str:
    return _get_alias_lookup().get(naam.lower(), naam)
