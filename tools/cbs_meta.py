"""Hoe een CBS-tabel telt en afrondt, uit het contract van de CBS-package (#383).

De package leest de TableInfos van CBS offline uit tot een contract: teldefinitie,
afronding ("afgerond op 10-tallen"), additiviteit (hbo + wo is meer dan het
HO-totaal) en definitiebreuken. Het model krijgt alleen de bronpassages, zodat
het die kan citeren in plaats van een som zelf te verklaren. Wat de bron niet
vermeldt, blijft weg.
"""

from onderwijsdata import contract as _contract

_GEVONDEN = "gevonden"


def _passages(sectie: dict) -> list[str]:
    if sectie.get("status") != _GEVONDEN:
        return []
    return sectie.get("passages") or []


def _methodiek(m: dict) -> dict:
    velden = {
        naam: passages
        for naam in ("afronding", "additiviteit", "definitiebreuken")
        if (passages := _passages(m.get(naam) or {}))
    }
    publicatie = m.get("publicatie") or {}
    if publicatie.get("status") == _GEVONDEN and publicatie.get("status_tekst"):
        velden["publicatiestatus"] = publicatie["status_tekst"]
    return velden


def metadata(dataset_id: str) -> dict:
    """De velden die dataset_details voor een CBS-tabel meegeeft; leeg buiten het contract."""
    try:
        record = _contract.get_dataset(dataset_id)
    except _contract.DatasetNietGevonden:
        return {}
    velden: dict = {}
    teldefinitie = record.get("teldefinitie") or {}
    if teldefinitie.get("status") == "supported" and teldefinitie.get("definities"):
        velden["teldefinitie"] = teldefinitie["definities"]
    if methodiek := _methodiek(record.get("methodiek") or {}):
        velden["methodiek"] = methodiek
    return velden
