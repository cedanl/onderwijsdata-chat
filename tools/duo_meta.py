"""Wat een DUO-dataset telt, uit de riodata-catalogus (#172, #369).

De sectie 'Selectie' van de DUO-beschrijving zegt wat er geteld wordt (bijv. p01:
hoofdinschrijvingen als natuurlijke personen; p03: hoofd- én neveninschrijvingen).
Zonder die definitie verwisselt het model datasets met verschillende telling zonder
het te merken. De package parset die sectie en de publicatieregels (aantallen 1-4
gepubliceerd als 4) bij het bouwen van de catalogus: geen CKAN-aanroep tijdens het
gesprek, en de tekst hoort bij de gepinde catalogusversie.
"""

from functools import cache

from riodata import catalog as _rio_catalog


@cache
def _records() -> dict[str, dict]:
    return {r["_ckan_id"]: r for r in _rio_catalog(source="duo") if r.get("_ckan_id")}


def record(dataset_id: str) -> dict:
    """Het catalogusrecord van een DUO-dataset; leeg als de dataset er niet in staat."""
    return _records().get(dataset_id, {})


def teldefinitie(entry: dict) -> str | None:
    """De selectiesectie, op één regel; None als de beschrijving er geen heeft."""
    selectie = (entry.get("_teldefinitie") or {}).get("selectie")
    return " ".join(selectie.split()) if selectie else None


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


def metadata(entry: dict) -> dict:
    """De velden die get_duo_data en dataset_details meegeven; alleen wat er is."""
    velden: dict = {}
    if definitie := teldefinitie(entry):
        velden["teldefinitie"] = definitie
    if regels := publicatieregels(entry):
        velden["publicatieregels"] = regels
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
