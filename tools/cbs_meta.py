"""Wat een CBS-tabel telt, dekt en hoe ze afrondt, uit het contract van de CBS-package (#383, #370).

De package leest de TableInfos en DataProperties van CBS offline uit tot een contract:
populatie, teldefinitie, afronding ("afgerond op 10-tallen"), additiviteit (hbo + wo is
meer dan het HO-totaal), definitiebreuken, de periodecodes met hun status, de geografische
dekking en de sectoren in het profiel. Het model krijgt de bronpassages en de codes, zodat
het citeert en kiest in plaats van zelf een som te verklaren of een periode te raden. Wat
de bron niet vermeldt, blijft weg.
"""

from onderwijsdata import contract as _contract

_GEVONDEN = "gevonden"
_SUPPORTED = "supported"
_DEFINITIEF = "Definitief"


def _passages(sectie: dict, status: str = _GEVONDEN) -> list[str]:
    if sectie.get("status") != status:
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


def _periodecode(code: dict) -> str:
    """De titel van een periodecode, met de CBS-status erbij zolang die niet definitief is."""
    titel = str(code.get("titel") or code.get("code"))
    status = code.get("status")
    return f"{titel} ({str(status).lower()})" if status and status != _DEFINITIEF else titel


def _perioden(p: dict) -> dict:
    """Bereik en codes van de tijddimensie: wat get_cbs_data onder 'periode' accepteert, zonder dimensiecall."""
    if p.get("status") != _SUPPORTED:
        return {}
    velden = {k: p[k] for k in ("frequentie", "eerste", "laatste") if p.get(k)}
    codes = p.get("codes") or {}
    if codes.get("status") == _SUPPORTED and codes.get("codes"):
        velden["codes"] = {c["code"]: _periodecode(c) for c in codes["codes"] if c.get("code")}
    return velden


def _geografie(g: dict) -> dict:
    if g.get("status") != _SUPPORTED:
        return {}
    return {k: g[k] for k in ("niveaus", "dekking") if g.get(k)}


def _sectoren(scopeprofiel: dict) -> list[str]:
    return [sector for sector, status in scopeprofiel.items() if status == _SUPPORTED]


def metadata(dataset_id: str) -> dict:
    """De velden die dataset_details voor een CBS-tabel meegeeft; leeg buiten het contract."""
    try:
        record = _contract.get_dataset(dataset_id)
    except _contract.DatasetNietGevonden:
        return {}
    velden: dict = {}
    if populatie := _passages(record.get("populatie") or {}, _SUPPORTED):
        velden["populatie"] = populatie
    if sectoren := _sectoren(record.get("scopeprofiel") or {}):
        velden["sectoren"] = sectoren
    teldefinitie = record.get("teldefinitie") or {}
    if teldefinitie.get("status") == _SUPPORTED and teldefinitie.get("definities"):
        velden["teldefinitie"] = teldefinitie["definities"]
    if methodiek := _methodiek(record.get("methodiek") or {}):
        velden["methodiek"] = methodiek
    if perioden := _perioden(record.get("perioden") or {}):
        velden["perioden"] = perioden
    if geografie := _geografie(record.get("geografie") or {}):
        velden["geografie"] = geografie
    return velden
