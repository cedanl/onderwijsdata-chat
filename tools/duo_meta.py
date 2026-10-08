"""Wat een DUO-dataset telt, uit de riodata-catalogus (#172, #369).

De sectie 'Selectie' van de DUO-beschrijving zegt wat er geteld wordt (bijv. p01:
hoofdinschrijvingen als natuurlijke personen; p03: hoofd- én neveninschrijvingen).
Zonder die definitie verwisselt het model datasets met verschillende telling zonder
het te merken. De package parset die sectie en de publicatieregels (aantallen 1-4
gepubliceerd als 4) bij het bouwen van de catalogus: geen CKAN-aanroep tijdens het
gesprek, en de tekst hoort bij de gepinde catalogusversie.
"""

import re
from functools import cache

from riodata import catalog as _rio_catalog

from . import kleine_aantallen


@cache
def _records() -> dict[str, dict]:
    return {r["_ckan_id"]: r for r in _rio_catalog(source="duo") if r.get("_ckan_id")}


def record(dataset_id: str) -> dict:
    """Het catalogusrecord van een DUO-dataset; leeg als de dataset er niet in staat."""
    return _records().get(dataset_id, {})


# Hoe een selectietekst een onderwijstype noemt. DUO kopieerde de po-tekst ('Leerlingen met een
# bekostigde inschrijving in het basisonderwijs') naar o.a. voprognoses (#402).
_ONDERWIJSTYPE_TERMEN = {
    "PO": ("basisonderwijs", "basisschool", "basisscholen"),
    "SO": ("speciaal onderwijs", "speciaal basisonderwijs", "speciale (basis)scholen"),
    "VO": ("voortgezet onderwijs", "voortgezet speciaal onderwijs"),
    "MBO": ("mbo", "middelbaar beroepsonderwijs"),
    "HO": ("hoger onderwijs", "hbo", "wo"),
}


def _selectie(entry: dict) -> str | None:
    """De selectiesectie op één regel; DUO's <br> wordt een spatie, de chat toont geen HTML (#402)."""
    selectie = (entry.get("_teldefinitie") or {}).get("selectie")
    return " ".join(re.sub(r"<br\s*/?>", " ", selectie, flags=re.IGNORECASE).split()) if selectie else None


def _genoemde_typen(tekst: str) -> set[str]:
    laag = tekst.lower()
    return {
        type_
        for type_, termen in _ONDERWIJSTYPE_TERMEN.items()
        if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", laag) for term in termen)
    }


def _typen(typen: set[str]) -> str:
    return ", ".join(f"{_ONDERWIJSTYPE_TERMEN[t][0]} ({t})" for t in sorted(typen))


def ander_onderwijstype(entry: dict) -> str | None:
    """De melding als de selectietekst alleen over een ander onderwijstype gaat dan het bestand; anders None."""
    eigen: set[str] = set(entry.get("onderwijstype") or ())
    if not (tekst := _selectie(entry)) or not eigen or not eigen <= _ONDERWIJSTYPE_TERMEN.keys():
        return None  # geen type, of 'Allen', 'Arbeidsmarkt' e.d.: niets om tegen te toetsen
    genoemd = _genoemde_typen(tekst)
    if not genoemd or genoemd & eigen:
        return None
    return (
        f"De DUO-beschrijving van dit bestand gaat over {_typen(genoemd)}, het bestand is {_typen(eigen)}. "
        "Die tekst is daarom niet gebruikt; noem geen teldefinitie."
    )


def teldefinitie(entry: dict) -> str | None:
    """De selectiesectie, op één regel; None als er geen is of als hij over een ander onderwijstype gaat."""
    return None if ander_onderwijstype(entry) else _selectie(entry)


def publicatieregels(entry: dict) -> list[dict]:
    """Regels als 'aantallen 1-4 gepubliceerd als 4', met de bronpassage.

    Naast de -1-sentinel, niet ervoor in de plaats: 4 is een gepubliceerde waarde,
    geen lege cel.
    """
    return [
        {
            "maat": regel.get("maat"),
            "bereik": regel["bereik"],
            "gepubliceerd_als": regel["gepubliceerd_als"],
            "bronpassage": regel.get("bronpassage"),
        }
        for regel in entry.get("_publicatieregels") or []
        if "bereik" in regel and "gepubliceerd_als" in regel
    ]


def beschrijving_onvolledig(entry: dict) -> bool:
    """De package kon de beschrijving niet (volledig) lezen: ontbrekende regels zijn dan onbekend."""
    status = (entry.get("_notes_provenance") or {}).get("parse_status")
    return status is not None and status != "ok"


def metadata(entry: dict, profiel: dict | None = None, geladen: bool = False) -> dict:
    """De velden die get_duo_data en dataset_details meegeven; alleen wat er is.

    De publicatieregel uit de beschrijving blijft altijd staan. Is de data geladen
    (`geladen`), dan komen ernaast het waargenomen `profiel` van het bestand en de
    conflictstatus, met een melding per oorzaak (#407, CH-31).
    """
    velden: dict = {}
    if definitie := teldefinitie(entry):
        velden["teldefinitie"] = definitie
    elif melding := ander_onderwijstype(entry):
        velden["teldefinitie_niet_gebruikt"] = melding
    if regels := publicatieregels(entry):
        velden["publicatieregels"] = regels
        if geladen:
            status, melding = kleine_aantallen.beoordeling(profiel)
            velden["publicatieregel_status"] = status
            if profiel is not None:
                velden["publicatieregel_waargenomen"] = profiel
            if melding:
                velden["publicatieregel_melding"] = melding
    if beschrijving_onvolledig(entry):
        velden["metadata_onbekend"] = (
            "De DUO-beschrijving is niet volledig te lezen: teldefinitie en publicatieregels kunnen "
            "ontbreken. Noem ze niet als ze hier niet staan."
        )
    return velden


KOLOMMEN_STEEKPROEF = (
    "Waarden en bereik in _kolommen komen uit een steekproef van het bestand: voorbeelden, "
    "geen volledige dekking van jaren of waarden. get_duo_data geeft per kolom het bereik, "
    "de unieke waarden en het aantal -1-cellen van het hele bestand."
)


def kolomdekking(entry: dict) -> dict:
    """Wat dataset_details over de catalogusvoorbeelden zegt (#362): steekproef, en van wanneer."""
    velden: dict = {"kolommen_steekproef": KOLOMMEN_STEEKPROEF} if entry.get("_kolommen") else {}
    if gewijzigd := (entry.get("_notes_provenance") or {}).get("metadata_modified"):
        velden["catalogus_bron_gewijzigd"] = gewijzigd[:10]
    return velden
