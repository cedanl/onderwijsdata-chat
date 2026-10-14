"""Correcties op DUO-kolombeschrijvingen die in de bron fout of leeg zijn (#451).

De riodata-glossary geeft een kolomnaam één betekenis voor alle bestanden, en DUO's eigen
metadata is op plekken leeg. Zo heette DIPLOMAJAAR in p04hogdipl het jaar van het
vooropleidingsdiploma en was PROVINCIENAAM in de ho-bestanden "Naam van de provincie",
waarna het model de vestiging las als woonplaats. Een correctie gaat voor op riodata, in
get_duo_data én in dataset_details: ze hangt niet af van een herstel bij DUO. Bij de
ho-bestanden zegt de catalogus bovendien dat ze niet over woonplaats of herkomst gaan.

De correcties zelf staan, elk met bron en controledatum, in data/domeinregels.toml (#363):
[[kolomcorrectie]] per kolom en [[herkomst_is_vestiging]] per groep bestanden. Hier staat
alleen hoe ze worden toegepast.
"""

from core.domeinregels import HerkomstIsVestiging

from . import duo_meta


def _correcties(dataset_id: str) -> dict[str, str]:
    """Kolom → gecorrigeerde definitie, voor de kolommen van deze dataset die er een hebben."""
    return {r.kolom: r.definitie for r in duo_meta.regels().kolomcorrecties if dataset_id in r.datasets}


def _herkomstregel(dataset_id: str) -> HerkomstIsVestiging | None:
    return next((r for r in duo_meta.regels().herkomst_is_vestiging if dataset_id in r.datasets), None)


def kolomdefinities(columns: list[str], dataset_id: str) -> dict[str, str]:
    """De correcties voor de kolommen van deze dataset die er een hebben."""
    correcties = _correcties(dataset_id)
    return {kolom: correcties[kolom] for kolom in columns if kolom in correcties}


def _met_kolomcorrecties(entry: dict, dataset_id: str) -> dict:
    correcties = _correcties(dataset_id)
    if not correcties:
        return entry
    return {**entry, "_kolomdefinities": {**(entry.get("_kolomdefinities") or {}), **correcties}}


def _zonder_herkomstsuggestie(entry: dict, dataset_id: str) -> dict:
    if (regel := _herkomstregel(dataset_id)) is None:
        return entry
    vragen = [regel.voorbeeldvragen.get(v, v) for v in entry.get("voorbeeldvragen") or []]
    return {**entry, "voorbeeldvragen": vragen, "niet_geschikt_voor": regel.melding}


def catalogusrecord(entry: dict) -> dict:
    """Het catalogusrecord met de correcties; een record zonder correctie komt ongewijzigd terug."""
    dataset_id = entry.get("_ckan_id") or ""
    return _zonder_herkomstsuggestie(_met_kolomcorrecties(entry, dataset_id), dataset_id)
