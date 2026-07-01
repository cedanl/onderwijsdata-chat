from __future__ import annotations

from riodata import duo

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


_cache: list[dict] | None = None
_alias_lookup: dict[str, str] | None = None


def _build_registry() -> list[dict]:
    result: dict[str, dict] = {}

    try:
        df_hbo = duo.load("p01hoinges", 0)
        for naam in df_hbo["INSTELLINGSNAAM_ACTUEEL"].dropna().unique():
            result[naam] = {"naam": naam, "type": "hbo", "aliassen": ALIASSEN.get(naam, [])}
    except Exception:
        pass

    try:
        df_wo = duo.load("p01hoinges", 1)
        for naam in df_wo["INSTELLINGSNAAM_ACTUEEL"].dropna().unique():
            if naam not in result:
                result[naam] = {"naam": naam, "type": "wo", "aliassen": ALIASSEN.get(naam, [])}
    except Exception:
        pass

    try:
        df_mbo = duo.load("mbo-studenten-per-instelling", 0)
        for naam in df_mbo["INSTELLINGSNAAM"].dropna().unique():
            if naam not in result:
                result[naam] = {"naam": naam, "type": "mbo", "aliassen": ALIASSEN.get(naam, [])}
    except Exception:
        pass

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
